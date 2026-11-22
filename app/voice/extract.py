"""Turn a transcript into a DRAFT record.

Flow: transcript -> Groq (JSON) -> Python matches supplier / product names to the
lists -> pydantic checks the shape -> DRAFT record + (maybe) one question to ask.

Nothing here saves to the database. The confirmation ("Haan") is a later step.
"""
import json
import re
from datetime import date
from difflib import SequenceMatcher
from typing import Optional, Union

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.models import DeliveryDiscrepancy, SupplierPromise
from app.voice.prompts import build_system_prompt, build_user_prompt

DELIVERY = "DELIVERY_DISCREPANCY"
PROMISE = "SUPPLIER_PROMISE"


class ExtractResult(BaseModel):
    record: Optional[Union[DeliveryDiscrepancy, SupplierPromise]] = None
    clarification_question: Optional[str] = None  # ask this before confirming
    error: Optional[str] = None  # set when no record could be made
    raw_json: Optional[dict] = None  # what the model returned, for debugging


# ---------- Name matching (supplier list / product list) ----------

def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _match_id(spoken: Optional[str], items: list[dict]) -> tuple[Optional[int], Optional[str]]:
    """Return (id, canonical name) of the best match, or (None, None) if unsure."""
    if not spoken or not _norm(spoken):
        return None, None
    n = _norm(spoken)
    scores: list[tuple[float, dict]] = []
    for item in items:
        best = 0.0
        for cand in [item["name"], *(item.get("aliases") or [])]:
            c = _norm(cand)
            if not c:
                continue
            if n == c:
                best = 1.0
                break
            score = SequenceMatcher(None, n, c).ratio()
            if min(len(n), len(c)) >= 4 and (n in c or c in n):
                score = max(score, 0.85)
            best = max(best, score)
        scores.append((best, item))
    scores.sort(key=lambda s: s[0], reverse=True)
    if not scores or scores[0][0] < 0.75:
        return None, None
    if len(scores) > 1 and scores[1][0] >= scores[0][0] - 0.05 and scores[0][0] < 1.0:
        return None, None  # two equally good matches: do not guess
    return scores[0][1]["id"], scores[0][1]["name"]


# ---------- Groq call ----------

def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start : end + 1])


def _ask_groq(system_prompt: str, user_prompt: str) -> dict:
    from groq import Groq  # imported here so the app still starts if groq is missing

    client = Groq(api_key=settings.GROQ_API_KEY)
    last_error: Exception = ValueError("no attempt made")
    for _ in range(2):  # one retry if the reply is not clean JSON
        resp = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_completion_tokens=4096,
            response_format={"type": "json_object"},
        )
        try:
            return _parse_json(resp.choices[0].message.content)
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
    raise ValueError(f"model did not return valid JSON: {last_error}")


# ---------- Main function ----------

def extract_record(
    record_type: str,
    transcript: str,
    suppliers: list[dict],
    products: list[dict],
    today: Optional[date] = None,
) -> ExtractResult:
    """suppliers: [{"id": 1, "name": "Sharma Distributors", "aliases": [...]?}, ...]
    products:  [{"id": 1, "name": "Maggi Noodles 70g", "aliases": ["maggi", ...]?}, ...]
    """
    if record_type not in (DELIVERY, PROMISE):
        return ExtractResult(error=f"Unknown record_type: {record_type}")
    if not transcript or not transcript.strip():
        return ExtractResult(error="Empty transcript")
    if not settings.GROQ_API_KEY:
        return ExtractResult(error="GROQ_API_KEY is empty. Add it to your .env file.")

    today_str = (today or date.today()).isoformat()
    system_prompt = build_system_prompt(record_type, suppliers, products, today_str)
    try:
        data = _ask_groq(system_prompt, build_user_prompt(transcript))
    except Exception as e:  # network, bad key, bad JSON ...
        return ExtractResult(error=f"Groq call failed: {e}")

    question = (data.pop("clarification_question", None) or None)

    # Supplier: match to the list, keep the spoken name if there is no match.
    supplier_id, supplier_name = _match_id(data.get("supplier_name"), suppliers)
    if supplier_id is not None:
        data["supplier_name"] = supplier_name
    data["supplier_id"] = supplier_id

    if record_type == DELIVERY:
        lines = data.get("lines") or []
        for line in lines:
            pid, pname = _match_id(line.get("product_name"), products)
            line["product_id"] = pid
            if pid is not None:
                line["product_name"] = pname
            # Simple arithmetic only: ordered minus received, when both were said.
            if (
                line.get("issue") == "MISSING_QTY"
                and line.get("shortage_qty") is None
                and line.get("expected_qty") is not None
                and line.get("received_qty") is not None
            ):
                diff = line["expected_qty"] - line["received_qty"]
                if diff > 0:
                    line["shortage_qty"] = diff
        if any(not line.get("issue") for line in lines):
            # A line without a clear problem type cannot be saved. Ask instead.
            return ExtractResult(
                clarification_question=question or "Is maal mein kya dikkat thi: kam, kharab, ya galat?",
                raw_json=data,
            )
        data["lines"] = lines
        model = DeliveryDiscrepancy
    else:
        pid, pname = _match_id(data.get("product_name"), products)
        data["product_id"] = pid
        if pid is not None:
            data["product_name"] = pname
        if not data.get("promise_type"):
            # promise_type is required in the record shape, so ask instead of guessing.
            return ExtractResult(
                clarification_question=question or "Supplier ne kya promise kiya tha?",
                raw_json=data,
            )
        model = SupplierPromise

    # These are always set by us, never by the model.
    for key in ("id", "status", "confirmed", "created_at", "photos", "summary_text", "record_type"):
        data.pop(key, None)
    data["transcript"] = transcript.strip()

    try:
        record = model(**data)
    except ValidationError as e:
        return ExtractResult(error=f"Model reply did not fit the record shape: {e}", raw_json=data)

    # One question at a time. Missing supplier and unknown supplier come first.
    if not question:
        if not record.supplier_name:
            question = "Kaun sa supplier tha?"
        elif record.supplier_id is None:
            question = f"'{record.supplier_name}' supplier list mein nahi mila. Kaun sa supplier tha?"
        elif record_type == DELIVERY and not record.lines:
            question = "Delivery mein kya dikkat thi? Kaun sa maal, kitna?"
        elif record_type == PROMISE and record.promise_type is None:
            question = "Supplier ne kya promise kiya tha?"

    return ExtractResult(record=record, clarification_question=question, raw_json=data)


def extract_delivery(transcript, suppliers, products, today=None) -> ExtractResult:
    return extract_record(DELIVERY, transcript, suppliers, products, today)


def extract_promise(transcript, suppliers, products, today=None) -> ExtractResult:
    return extract_record(PROMISE, transcript, suppliers, products, today)