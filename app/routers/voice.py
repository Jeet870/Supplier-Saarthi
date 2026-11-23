"""Voice routes.

POST /api/transcribe  audio file in, {"text": "..."} out (Groq Whisper)
POST /api/extract     {"text": "..."} in, a DRAFT record out (see docs/api-contract.md)
"""
from typing import Literal, Optional

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.matching import load_lists
from app.voice.extract import DELIVERY, PROMISE, classify_kind, extract_record

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


def _placeholder_readback(transcript: str) -> str:
    # Task 3A-1 replaces this with the proper read-back sentence.
    return f'Maine suna: "{transcript}". Sahi hai?'


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
        kind = body.kind or classify_kind(text)
    except Exception as e:
        return _error(f"Could not understand the sentence: {e}", 502)

    if kind == "unclear":
        return {
            "kind": "unclear",
            "record": _empty_record(None, text),
            "readback_text": None,
            "clarification": "Samajh nahi aaya. Delivery ki dikkat hai ya supplier ka wada? Dobara bolo.",
        }

    record_type = DELIVERY if kind == "delivery" else PROMISE
    result = extract_record(record_type, text, suppliers, products)
    if result.error:
        return _error(result.error, 502)

    if result.record is None:  # the model could not fill the required part, so we ask back
        return {
            "kind": kind,
            "record": _empty_record(record_type, text),
            "readback_text": None,
            "clarification": result.clarification_question,
        }

    return {
        "kind": kind,
        "record": result.record.model_dump(mode="json"),
        "readback_text": None if result.clarification_question else _placeholder_readback(text),
        "clarification": result.clarification_question,
    }