from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import pages, voice, records

app = FastAPI(title="Supplier Saarthi")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(pages.router)
app.include_router(voice.router)
app.include_router(records.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Format all validation errors into standard Appendix C shape: {'error': '...'}"""
    first_err = exc.errors()[0]
    msg = first_err.get("msg", "Invalid request body")
    loc = " -> ".join(str(l) for l in first_err.get("loc", []))
    return JSONResponse(
        status_code=400,
        content={"error": f"Invalid input at {loc}: {msg}"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ensure all HTTP exceptions use standard Appendix C shape: {'error': '...'}"""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        msg = exc.detail["error"]
    else:
        msg = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": msg},
    )


@app.get("/health")
def health():
    return {"status": "ok"}
