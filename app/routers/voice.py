"""STUB version of POST /api/transcribe.

Always returns the same sentence, whatever audio is sent. It lets C build the
mic button now. Replace this whole file with the real version later.
"""
from fastapi import APIRouter, File, UploadFile

router = APIRouter()

STUB_TEXT = "Sharma ji ka Maggi 5 carton mangaya tha, sirf 4 aaye"


@router.post("/api/transcribe")
def transcribe(audio: UploadFile = File(...)):
    return {"text": STUB_TEXT}