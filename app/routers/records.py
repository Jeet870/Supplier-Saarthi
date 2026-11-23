from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app import db
from app.models import Record

router = APIRouter()


class StatusUpdate(BaseModel):
    status: str


@router.get("/api/suppliers", response_model=List[Dict[str, Any]])
def list_suppliers():
    try:
        return db.get_suppliers()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch suppliers: {str(e)}"},
        )


@router.get("/api/products", response_model=List[Dict[str, Any]])
def list_products():
    try:
        return db.get_products()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch products: {str(e)}"},
        )


@router.post("/api/records", status_code=status.HTTP_201_CREATED)
def create_record(record: Record):
    """Save a confirmed delivery discrepancy or supplier promise."""
    try:
        data = record.model_dump()
        saved = db.save_record(data)
        return saved
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Failed to save record: {str(e)}"},
        )


@router.get("/api/timeline/{supplier_id}")
def supplier_timeline(supplier_id: int):
    """Get all records for a supplier, newest first."""
    try:
        return db.get_supplier_timeline(supplier_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch timeline: {str(e)}"},
        )


@router.get("/api/pending")
def list_pending(
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    record_type: Optional[str] = Query(None, description="Filter by record type"),
):
    """Get open/pending records across suppliers."""
    try:
        return db.get_pending_records(supplier_id=supplier_id, record_type=record_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch pending records: {str(e)}"},
        )


@router.patch("/api/records/{record_id}/status")
def update_status(record_id: int, body: StatusUpdate):
    """Update status of a record (e.g. RESOLVED, FULFILLED)."""
    try:
        return db.update_record_status(record_id, body.status)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Failed to update status: {str(e)}"},
        )


@router.get("/api/summary")
def get_summary():
    """Get counts of open deliveries and open promises for the Home dashboard."""
    try:
        return db.get_summary_counts()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"Failed to fetch summary: {str(e)}"},
        )


@router.post("/api/photos")
async def upload_photo(file: UploadFile = File(...)):
    """Upload an evidence photo to Supabase storage and return its public URL."""
    try:
        content = await file.read()
        url = db.upload_photo(
            file_bytes=content,
            filename=file.filename or "photo.jpg",
            content_type=file.content_type or "image/jpeg",
        )
        return {"url": url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Failed to upload photo: {str(e)}"},
        )

