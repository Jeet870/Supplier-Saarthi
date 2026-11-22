"""POST /api/transcribe: audio file in, {"text": "..."} out.

Uses Groq's hosted Whisper. Needs GROQ_API_KEY in .env.
"""
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings

router = APIRouter()

# whisper-large-v3 is the most accurate for Hindi. If it feels slow, try "whisper-large-v3-turbo".
WHISPER_MODEL = "whisper-large-v3"
# None = let Whisper detect the language (good for Hinglish).
WHISPER_LANGUAGE = None
# A short example in the style we want back: Roman letters, Hinglish, our shop words.
STYLE_HINT = (
    "Sharma ji ka Maggi 5 carton mangaya tha, sirf 4 aaye. "
    "Surf Excel, Tata Salt, Fortune oil, Aashirvaad atta, carton, packet, kg, Gupta Wholesale."
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
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is empty. Add it to your .env file.")

    data = audio.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The audio file is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio is too big. Keep it under 24 MB.")

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
        raise HTTPException(status_code=502, detail=f"Transcription failed: {e}")

    return {"text": (result.text or "").strip()}