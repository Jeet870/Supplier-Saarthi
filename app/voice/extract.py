"""Turn a transcript into a DRAFT record.

Flow: transcript -> Groq (JSON) -> Python matches supplier / product names to the
lists -> pydantic checks the shape -> DRAFT record + (maybe) one question to ask.

Nothing here saves to the database. The confirmation ("Haan") is a later step.
"""
import json
import re
import time
from datetime import date
from typing import Optional, Union

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.matching import SUPPLIER_GENERIC_WORDS, match_id
from app.models import PREDEFINED_ISSUES, DeliveryDiscrepancy, SupplierPromise
from app.voice.prompts import build_system_prompt, build_user_prompt

DELIVERY = "DELIVERY_DISCREPANCY"
PROMISE = "SUPPLIER_PROMISE"


class ExtractResult(BaseModel):
    record: Optional[Union[DeliveryDiscrepancy, SupplierPromise]] = None
    clarification_question: Optional[str] = None  # ask this before confirming
    clarification_reason: Optional[str] = None  # a short code, for example SUPPLIER_NOT_IN_LIST
    error: Optional[str] = None  # set when no record could be made
    raw_json: Optional[dict] = None  # what the model returned, for debugging


# ---------- Groq call ----------

def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model reply")
    return json.loads(text[start : end + 1])


def _ask_groq(system_prompt: str, user_prompt: str) -> dict:
    from groq import Groq, RateLimitError, APIStatusError  # imported here so the app still starts if groq is missing

    client = Groq(api_key=settings.GROQ_API_KEY)
    last_error: Exception = ValueError("no attempt made")
    for attempt in range(4):
        try:
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
            return _parse_json(resp.choices[0].message.content)
        except (RateLimitError, APIStatusError) as e:
            status_code = getattr(e, "status_code", None)
            if status_code == 429 or isinstance(e, RateLimitError):
                if attempt < 3:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise ValueError("Thoda ruko, dobara bolo (rate limit). Ek minute baad try karein.")
            raise
        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            time.sleep(0.5)
    raise ValueError(f"model did not return valid JSON: {last_error}")



def _issue_list(line: dict) -> list:
    """All problems of one line as a list of dicts (also reads the old single "issue" field)."""
    raw = line.get("issues") or []
    if not raw and line.get("issue"):
        raw = [{"type": line["issue"]}]
    return [{"type": r} if isinstance(r, str) else dict(r) for r in raw if r]


def clean_issue_type(text) -> Optional[str]:
    """CAPITAL_LETTERS_WITH_UNDERSCORES, at most 32 characters. None if nothing is left."""
    cleaned = re.sub(r"[^A-Z0-9]+", "_", str(text or "").upper()).strip("_")
    return cleaned[:32].strip("_") or None


def merge_same_product(lines: list[dict]) -> list[dict]:
    """The record shape has ONE line per product. If the model gave two lines for the same
    product, join them into one line and lose nothing (numbers, problems and notes are kept)."""
    merged: list[dict] = []
    seen: dict = {}
    for line in lines:
        key = line.get("product_id")
        if key is None and line.get("product_name"):
            key = ("name", " ".join(str(line["product_name"]).lower().split()))
        if key is None or key not in seen:
            merged.append(line)
            if key is not None:
                seen[key] = line
            continue
        base = seen[key]
        for field in ("unit", "expected_qty", "received_qty", "damaged_qty", "shortage_qty", "amount_diff_rs"):
            if base.get(field) is None and line.get(field) is not None:
                base[field] = line[field]
        base["issues"] = _issue_list(base) + _issue_list(line)
        base.pop("issue", None)
        if line.get("note"):
            base["note"] = "; ".join(x for x in [base.get("note"), line["note"]] if x)
    return merged


def normalize_issues(line: dict) -> None:
    """Clean the problem list of one line: tidy names, join repeats, flag AI-made categories,
    fill quantities that are already known, and set the main issue (the first one)."""
    items: list[dict] = []
    for raw in _issue_list(line):
        issue_type = clean_issue_type(raw.get("type"))
        if not issue_type:
            continue
        existing = next((i for i in items if i["type"] == issue_type), None)
        if existing:  # same category twice: keep one, join the details
            if raw.get("detail") and raw["detail"] != existing.get("detail"):
                existing["detail"] = "; ".join(x for x in [existing.get("detail"), raw["detail"]] if x)
            continue
        qty = raw.get("qty")
        if qty is None and issue_type == "MISSING_QTY":
            qty = line.get("shortage_qty")
        if qty is None and issue_type == "DAMAGED":
            qty = line.get("damaged_qty")
        items.append({
            "type": issue_type,
            "detail": raw.get("detail") or None,
            "qty": qty,
            "custom": issue_type not in PREDEFINED_ISSUES,
        })
    line["issues"] = items
    line["issue"] = items[0]["type"] if items else None


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
    reason = (data.pop("clarification_reason", None) or None)
    if question and not reason:
        reason = "OTHER"
    if not question:
        reason = None

    # Supplier: match to the list, keep the spoken name if there is no match.
    supplier_id, supplier_name = match_id(data.get("supplier_name"), suppliers, SUPPLIER_GENERIC_WORDS)
    if supplier_id is not None:
        data["supplier_name"] = supplier_name
    data["supplier_id"] = supplier_id

    if record_type == DELIVERY:
        lines = data.get("lines") or []
        for line in lines:
            pid, pname = match_id(line.get("product_name"), products)
            line["product_id"] = pid
            if pid is not None:
                line["product_name"] = pname
        lines = merge_same_product(lines)
        for line in lines:
            # Simple arithmetic only: ordered minus received, when both were said.
            if (
                line.get("shortage_qty") is None
                and line.get("expected_qty") is not None
                and line.get("received_qty") is not None
                and line["expected_qty"] > line["received_qty"]
            ):
                line["shortage_qty"] = line["expected_qty"] - line["received_qty"]
        for line in lines:
            normalize_issues(line)
        if any(not line.get("issue") for line in lines):
            # A line without a clear problem type cannot be saved. Ask instead.
            return ExtractResult(
                clarification_question=question or "Is maal mein kya dikkat thi: kam, kharab, ya galat?",
                clarification_reason=reason if question else "ISSUE_UNCLEAR",
                raw_json=data,
            )
        data["lines"] = lines
        model = DeliveryDiscrepancy
    else:
        pid, pname = match_id(data.get("product_name"), products)
        data["product_id"] = pid
        if pid is not None:
            data["product_name"] = pname
        if not data.get("promise_type"):
            # promise_type is required in the record shape, so ask instead of guessing.
            return ExtractResult(
                clarification_question=question or "Supplier ne kya promise kiya tha?",
                clarification_reason=reason if question else "PROMISE_UNCLEAR",
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

    # One question at a time. Order: an unclear number first, then a supplier problem,
    # then any other question from the AI, then a delivery with no problem named.
    supplier_question = supplier_reason = None
    if not record.supplier_name:
        supplier_question, supplier_reason = "Kaun sa supplier tha?", "SUPPLIER_MISSING"
    elif record.supplier_id is None:
        supplier_question = f"'{record.supplier_name}' supplier list mein nahi mila. Kaun sa supplier tha?"
        supplier_reason = "SUPPLIER_NOT_IN_LIST"

    if reason == "AMBIGUOUS_NUMBER" and question:
        pass
    elif supplier_question:
        question, reason = supplier_question, supplier_reason
    elif not question and record_type == DELIVERY and not record.lines:
        question, reason = "Delivery mein kya dikkat thi? Kaun sa maal, kitna?", "ISSUE_UNCLEAR"

    return ExtractResult(
        record=record, clarification_question=question, clarification_reason=reason, raw_json=data
    )


def extract_delivery(transcript, suppliers, products, today=None) -> ExtractResult:
    return extract_record(DELIVERY, transcript, suppliers, products, today)


def extract_promise(transcript, suppliers, products, today=None) -> ExtractResult:
    return extract_record(PROMISE, transcript, suppliers, products, today)


# ---------- What is this sentence about? ----------

CLASSIFY_PROMPT = """You read one sentence a kirana (small grocery) shopkeeper said about a supplier.
The words come from speech-to-text, so they can be Hindi, Hinglish or English.
Decide what the sentence contains and reply with ONE JSON object only: {"kinds": [...]}.
The list can have "delivery", "promise", or both (in the order they are said), or just "unclear".
- delivery: a problem with goods that were delivered (fewer came, damaged, wrong item, wrong price, bad quality, bill does not match).
- promise: the supplier promised something for later (discount, replacement, credit note, free goods, more days to pay, price lock).
- If the sentence has both a delivery problem AND a promise, return ["delivery", "promise"].
- unclear: anything else, or too vague to know (for example "same as last time", or no supplier, goods or promise at all). Return ["unclear"].
Do not guess. When in doubt, return ["unclear"].

EXAMPLES (the names are only for the format)
"Gupta ji ne 3 carton Parle-G kam bheje" -> {"kinds": ["delivery"]}
"Kumar ne bola 500 rupaye ka credit note dega" -> {"kinds": ["promise"]}
"Balaji ke 2 packet atta fate aaye aur woh bola agli baar badal dega" -> {"kinds": ["delivery", "promise"]}
"Wahi same jaisa pichli baar" -> {"kinds": ["unclear"]}"""

# Words that show the supplier promised something. Safety net: if the AI missed a promise
# in a sentence that also has a delivery problem, we still try to extract it.
PROMISE_WORDS = re.compile(
    r"\b(replace|badal\w*|wada|wade|vada|promise|dega|denge|dunga|free|discount|credit note|udhaar|udhar)\b",
    re.IGNORECASE,
)

def classify_kinds(transcript: str) -> list[str]:
    """Return a list like ["delivery"], ["promise"], ["delivery", "promise"] or ["unclear"].
    Raises an error if Groq fails."""
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is empty. Add it to your .env file.")
    data = _ask_groq(CLASSIFY_PROMPT, build_user_prompt(transcript))
    kinds: list[str] = []
    for k in data.get("kinds") or []:
        k = str(k).strip().lower()
        if k in ("delivery", "promise") and k not in kinds:
            kinds.append(k)
    if "delivery" in kinds and "promise" not in kinds and PROMISE_WORDS.search(transcript):
        kinds.append("promise")
    return kinds or ["unclear"]