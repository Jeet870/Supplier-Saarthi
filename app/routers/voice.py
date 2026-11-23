"""Voice routes.

POST /api/transcribe  audio file in, {"text": "..."} out (Groq Whisper)
POST /api/extract     {"text": "..."} in, a DRAFT record, a read-back sentence and a question if needed out
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.matching import load_lists
from app.voice.extract import DELIVERY, PROMISE, classify_kinds, extract_record
from app.voice.readback import build_readback

router = APIRouter()


def _error(message: str, status_code: int = 400) -> JSONResponse:
    """Errors always look like {"error": "short readable message"}."""
    return JSONResponse(status_code=status_code, content={"error": message})


# ======================= POST /api/transcribe =======================

# whisper-large-v3 is the most accurate for Hindi. If it feels slow, try "whisper-large-v3-turbo".
WHISPER_MODEL = "whisper-large-v3"
# None = let Whisper detect the language (good for Hinglish).
WHISPER_LANGUAGE = None
# A short example in the style we want back: Roman letters, Hinglish, our shop words.
STYLE_HINT = (
    "Sharma ji ka Maggi 5 carton mangaya tha, sirf 4 aaye. "
    "Surf Excel, Tata Salt, Parle-G, Aashirvaad atta, carton, packet, kg, Gupta Wholesale."
)
MAX_BYTES = 24 * 1024 * 1024  # Groq's free tier accepts files up to 25 MB

# Groq decides the audio format from the file name, so make sure it ends in a known type.
KNOWN_EXTENSIONS = (".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".opus", ".wav", ".webm")
CONTENT_TYPE_TO_EXT = {
    "audio/webm": ".webm",
    "video/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/m4a": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
}


def _file_name(upload: UploadFile) -> str:
    name = upload.filename or "audio"
    if name.lower().endswith(KNOWN_EXTENSIONS):
        return name
    content_type = (upload.content_type or "").split(";")[0].strip().lower()
    return "audio" + CONTENT_TYPE_TO_EXT.get(content_type, ".webm")


@router.post("/api/transcribe")
def transcribe(audio: UploadFile = File(...)):
    if not settings.GROQ_API_KEY:
        return _error("GROQ_API_KEY is empty. Add it to your .env file.", 500)

    data = audio.file.read()
    if not data:
        return _error("The audio file is empty.")
    if len(data) > MAX_BYTES:
        return _error("Audio is too big. Keep it under 24 MB.", 413)

    from groq import Groq  # imported here so the app still starts if groq is missing

    options = {
        "file": (_file_name(audio), data),
        "model": WHISPER_MODEL,
        "response_format": "json",
        "temperature": 0,
        "prompt": STYLE_HINT,
    }
    if WHISPER_LANGUAGE:
        options["language"] = WHISPER_LANGUAGE

    try:
        result = Groq(api_key=settings.GROQ_API_KEY).audio.transcriptions.create(**options)
    except Exception as e:
        return _error(f"Transcription failed: {e}", 502)

    return {"text": (result.text or "").strip()}


# ======================= POST /api/extract =======================

class ExtractRequest(BaseModel):
    text: str
    # Optional. If the screen already knows (Delivery Check or Promise Note button), send it.
    # If left out, we work out the kind from the sentence.
    kind: Optional[Literal["delivery", "promise"]] = None


def _empty_record(record_type: Optional[str], transcript: str) -> dict:
    """Same keys as a real record, but every value empty, for sentences we could not understand."""
    return {
        "record_type": record_type,
        "supplier_id": None,
        "supplier_name": None,
        "event_date": None,
        "status": None,
        "lines": [],
        "transcript": transcript,
        "photos": [],
        "confirmed": False,
    }


def _item(kind: str, record_type: str, result, text: str) -> dict:
    """One answer: kind, record, readback_text, clarification (+ a short reason code)."""
    if result.record is None:  # the AI could not fill a required part, so we ask back
        return {
            "kind": kind,
            "record": _empty_record(record_type, text),
            "readback_text": None,
            "clarification": result.clarification_question,
            "clarification_reason": result.clarification_reason,
        }
    record = result.record.model_dump(mode="json")
    asking = bool(result.clarification_question)
    return {
        "kind": kind,
        "record": record,
        # Never read back a record that still has an open question.
        "readback_text": None if asking else (build_readback(record) or None),
        "clarification": result.clarification_question,
        "clarification_reason": result.clarification_reason,
    }


@router.post("/api/extract")
def extract(body: ExtractRequest):
    text = (body.text or "").strip()
    if not text:
        return _error("Text is empty. Please say it again.")

    try:
        suppliers, products = load_lists()
    except Exception as e:
        return _error(f"Could not read the supplier and product lists: {e}", 500)

    try:
        kinds = [body.kind] if body.kind else classify_kinds(text)
    except Exception as e:
        return _error(f"Could not understand the sentence: {e}", 502)

    if kinds == ["unclear"]:
        return {
            "kind": "unclear",
            "record": _empty_record(None, text),
            "readback_text": None,
            "clarification": "Samajh nahi aaya. Delivery ki dikkat hai ya supplier ka wada? Dobara bolo.",
            "clarification_reason": "NOTHING_SPECIFIED",
        }

    record_types = [DELIVERY if k == "delivery" else PROMISE for k in kinds]
    with ThreadPoolExecutor(max_workers=len(record_types)) as pool:
        futures = [pool.submit(extract_record, rt, text, suppliers, products) for rt in record_types]
        results = [f.result() for f in futures]

    items = []
    for kind, record_type, result in zip(kinds, record_types, results):
        if result.error:
            return _error(result.error, 502)
        if items and result.record is None:
            continue  # an extra record that could not be filled is dropped, it must not hide the main one
        items.append(_item(kind, record_type, result, text))

    response = dict(items[0])
    if len(items) > 1:
        # One sentence with a delivery problem AND a promise: the first goes on top as always,
        # the rest are listed here in the same shape. Each is confirmed on its own.
        response["additional"] = items[1:]
    return response


# ======================= POST /api/query =======================

class QueryRequest(BaseModel):
    text: str


@router.post("/api/query")
def answer_query(body: QueryRequest):
    """Answer voice questions from shopkeepers about pending deliveries and promises (Task 4A-1)."""
    text = (body.text or "").strip()
    if not text:
        return {"answer_text": "Aapka sawal samajh nahi aaya, dobara bolo.", "records": []}

    try:
        from app.matching import load_lists, match_id
        from app import db
        suppliers, products = load_lists()
    except Exception as e:
        return _error(f"Could not load master data: {e}", 500)

    # 1. Match supplier if spoken
    matched_supplier_id = None
    matched_supplier_name = None
    for word in text.split():
        s_id, s_name = match_id(word, suppliers)
        if s_id:
            matched_supplier_id = s_id
            matched_supplier_name = s_name
            break
    if not matched_supplier_id:
        s_id, s_name = match_id(text, suppliers)
        if s_id:
            matched_supplier_id = s_id
            matched_supplier_name = s_name

    # 2. Check query intent: promises, damages, or general pending
    lower_text = text.lower()
    is_promise_query = any(k in lower_text for k in ["promise", "wada", "vaada", "udhaar", "discount", "free"])
    is_damage_query = any(k in lower_text for k in ["damage", "fata", "kharab", "phata", "toota"])

    record_type = "SUPPLIER_PROMISE" if is_promise_query and not is_damage_query else None

    try:
        records = db.get_pending_records(supplier_id=matched_supplier_id, record_type=record_type)
    except Exception as e:
        return _error(f"Could not query pending records: {e}", 500)

    if is_damage_query:
        records = [
            r for r in records
            if any((l.get("issue") == "DAMAGED" or (l.get("damaged_qty") or 0) > 0) for l in (r.get("lines") or []))
        ]

    # 3. Generate answer_text using Groq LLM with friendly fallback
    answer_text = ""
    if not records:
        if matched_supplier_name:
            answer_text = f"{matched_supplier_name} ka abhi koi pending maal ya wada nahi hai."
        else:
            answer_text = "Abhi koi bhi pending maal ya wada nahi hai. Sab hisaab clear hai."
    else:
        records_summary = []
        for r in records[:5]:
            if r.get("record_type") == "DELIVERY_DISCREPANCY":
                items = [f"{l.get('product_name')} ({l.get('shortage_qty') or l.get('damaged_qty') or ''} {l.get('unit') or ''} {l.get('issue')})" for l in (r.get("lines") or [])]
                records_summary.append(f"{r.get('supplier_name')}: {', '.join(items)}")
            else:
                records_summary.append(f"{r.get('supplier_name')} promise: {r.get('promise_type')} ({r.get('value') or ''} {r.get('value_type') or ''})")

        prompt_user = f"Shopkeeper asked: \"{text}\"\nMatching open records:\n" + "\n".join(f"- {s}" for s in records_summary)
        prompt_sys = (
            "You are Supplier Saarthi voice assistant for Indian kirana shopkeepers. "
            "Answer the question in ONE concise, natural Hindi/Hinglish sentence. "
            "Be direct, polite, state what is pending clearly (naming product/supplier and count). "
            "Do not output markdown, formatting, or quotes."
        )
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            resp = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": prompt_sys},
                    {"role": "user", "content": prompt_user},
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            raw_content = (resp.choices[0].message.content or "").strip().strip('"')
            if raw_content:
                answer_text = raw_content
            else:
                if matched_supplier_name:
                    answer_text = f"{matched_supplier_name} ke {len(records)} items pending hain."
                else:
                    answer_text = f"Total {len(records)} pending items hain."
        except Exception:
            if matched_supplier_name:
                answer_text = f"{matched_supplier_name} ke {len(records)} items pending hain."
            else:
                answer_text = f"Total {len(records)} pending items hain."

    return {
        "answer_text": answer_text,
        "records": records,
    }
