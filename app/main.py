from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import pages, voice, records

app = FastAPI(title="Munshi Guard")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(voice.router)
app.include_router(records.router)


@app.get("/health")
def health():
    return {"status": "ok"}
