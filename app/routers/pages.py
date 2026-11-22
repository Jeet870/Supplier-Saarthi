from typing import Any, Dict, List
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Fallback supplier list for initial UI rendering before database query
FALLBACK_SUPPLIERS = [
    {"id": 1, "name": "Sharma Distributors", "aliases": ["sharma", "sharma ji"]},
    {"id": 2, "name": "Gupta Wholesale", "aliases": ["gupta", "gupta ji"]},
    {"id": 3, "name": "Balaji Traders", "aliases": ["balaji", "balaji ji"]},
    {"id": 4, "name": "Kumar Provisions", "aliases": ["kumar", "kumar ji"]},
]


def _get_suppliers_safe() -> List[Dict[str, Any]]:
    """Fetch suppliers from app.db if available and configured, otherwise use fallback."""
    try:
        from app import db
        suppliers = db.get_suppliers()
        if suppliers:
            return suppliers
    except Exception:
        pass
    return FALLBACK_SUPPLIERS


@router.get("/")
def home_page(request: Request):
    """Home screen: Two large action buttons, summary line, and quick navigation."""
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "active_page": "home",
            "open_count": 3,
        },
    )


@router.get("/delivery")
def delivery_check_page(request: Request):
    """Delivery Check screen: Supplier picker, mic button, transcript box, fallback."""
    suppliers = _get_suppliers_safe()
    return templates.TemplateResponse(
        request=request,
        name="delivery.html",
        context={
            "active_page": "delivery",
            "suppliers": suppliers,
        },
    )


@router.get("/promise")
def promise_note_page(request: Request):
    """Promise Note screen: Supplier picker, follow-up date, mic button, transcript."""
    suppliers = _get_suppliers_safe()
    return templates.TemplateResponse(
        request=request,
        name="promise.html",
        context={
            "active_page": "promise",
            "suppliers": suppliers,
        },
    )


@router.get("/confirmation")
def confirmation_page(request: Request):
    """Confirmation screen: Spoken read-back, editable record fields, Haan/Galat buttons."""
    return templates.TemplateResponse(
        request=request,
        name="confirmation.html",
        context={
            "active_page": "confirmation",
        },
    )


@router.get("/suppliers")
def suppliers_page(request: Request):
    """Supplier list screen: Master list of kirana suppliers."""
    suppliers = _get_suppliers_safe()
    return templates.TemplateResponse(
        request=request,
        name="suppliers.html",
        context={
            "active_page": "suppliers",
            "suppliers": suppliers,
        },
    )


@router.get("/timeline/{supplier_id}")
def timeline_page(request: Request, supplier_id: int):
    """Supplier timeline screen: Deliveries and promises, status chips, WhatsApp sharing."""
    suppliers = _get_suppliers_safe()
    matched = next((s for s in suppliers if s["id"] == supplier_id), None)
    supplier_name = matched["name"] if matched else f"Supplier #{supplier_id}"
    sample_wa = f"Munshi Guard Hisaab: {supplier_name} - 1 open delivery discrepancy, 1 active promise."
    return templates.TemplateResponse(
        request=request,
        name="timeline.html",
        context={
            "active_page": "suppliers",
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "whatsapp_text": sample_wa,
        },
    )


@router.get("/pending")
def pending_page(request: Request):
    """Pending screen: All unresolved deliveries and promises across all suppliers."""
    return templates.TemplateResponse(
        request=request,
        name="pending.html",
        context={
            "active_page": "pending",
        },
    )
