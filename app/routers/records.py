from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from app import db

router = APIRouter()


@router.get("/api/suppliers", response_model=List[Dict[str, Any]])
def list_suppliers():
    try:
        return db.get_suppliers()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/api/products", response_model=List[Dict[str, Any]])
def list_products():
    try:
        return db.get_products()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": str(e)})
