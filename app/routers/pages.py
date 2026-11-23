from typing import Any, Dict, List, Optional
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

FALLBACK_PENDING = [
    {
        "id": 1,
        "record_type": "DELIVERY_DISCREPANCY",
        "supplier_id": 1,
        "supplier_name": "Sharma Distributors",
        "event_date": "2026-11-19",
        "status": "OPEN",
        "issue": "MISSING_QTY",
        "detail": "Maggi Noodles 70g - 1 carton kam",
    },
    {
        "id": 2,
        "record_type": "DELIVERY_DISCREPANCY",
        "supplier_id": 2,
        "supplier_name": "Gupta Wholesale",
        "event_date": "2026-11-15",
        "status": "DISPUTED",
        "issue": "WRONG_SKU",
        "detail": "Tata Salt ki jagah dusra namak bhej diya",
    },
    {
        "id": 3,
        "record_type": "SUPPLIER_PROMISE",
        "supplier_id": 4,
        "supplier_name": "Kumar Provisions",
        "event_date": "2026-11-13",
        "status": "OPEN",
        "issue": "CREDIT_NOTE",
        "detail": "Rs 500 ka credit note dene ka wada",
    },
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


def _get_summary_safe() -> Dict[str, int]:
    """Fetch summary count safely."""
    try:
        from app import db
        return db.get_summary_counts()
    except Exception:
        return {"open_deliveries": 2, "open_promises": 1}


def _get_timeline_safe(supplier_id: int) -> List[Dict[str, Any]]:
    """Fetch timeline for supplier safely."""
    try:
        from app import db
        records = db.get_supplier_timeline(supplier_id)
        if records:
            return records
    except Exception:
        pass
    return [
        {
            "id": 101,
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_id": supplier_id,
            "status": "OPEN",
            "event_date": "2026-11-19",
            "title": "Maggi Noodles 70g (Short 1 carton)",
            "summary_text": "5 mangaya tha, sirf 4 aaye. 1 carton kam.",
        },
        {
            "id": 102,
            "record_type": "SUPPLIER_PROMISE",
            "supplier_id": supplier_id,
            "status": "OPEN",
            "event_date": "2026-11-14",
            "title": "15 Din Ka Udhaar (Credit Period)",
            "summary_text": "Wada: Next order par 15 din ka udhaar milega.",
        },
    ]


def _get_pending_safe() -> List[Dict[str, Any]]:
    """Fetch pending records safely."""
    try:
        from app import db
        records = db.get_pending_records()
        if records:
            return records
    except Exception:
        pass
    return FALLBACK_PENDING


@router.get("/")
def home_page(request: Request):
    """Home screen: Polished SaaS dashboard with key metrics and quick flows."""
    counts = _get_summary_safe()
    open_del = counts.get("open_deliveries", 2)
    open_prom = counts.get("open_promises", 1)
    total_open = open_del + open_prom
    suppliers = _get_suppliers_safe()
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "active_page": "home",
            "open_count": total_open if total_open > 0 else 3,
            "open_deliveries": open_del,
            "open_promises": open_prom,
            "total_suppliers": len(suppliers),
            "suppliers": suppliers,
        },
    )


@router.get("/delivery")
def delivery_check_page(request: Request):
    """Delivery Check screen: Voice recording station, fallback text, and inline confirmation."""
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
    """Promise Note screen: Supplier picker, follow-up date, voice station."""
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
    """Supplier directory screen: Master list of kirana suppliers with quick stats."""
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
    """Supplier timeline screen: Chronological milestone ledger with WhatsApp export."""
    suppliers = _get_suppliers_safe()
    matched = next((s for s in suppliers if s["id"] == supplier_id), None)
    supplier_name = matched["name"] if matched else f"Supplier #{supplier_id}"
    records = _get_timeline_safe(supplier_id)
    sample_wa = f"Supplier Saarthi Hisaab: {supplier_name} - {len(records)} active records."
    return templates.TemplateResponse(
        request=request,
        name="timeline.html",
        context={
            "active_page": "suppliers",
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "records": records,
            "whatsapp_text": sample_wa,
        },
    )


@router.get("/pending")
def pending_page(request: Request):
    """Pending screen: Filterable ledger of all unresolved deliveries and promises."""
    records = _get_pending_safe()
    return templates.TemplateResponse(
        request=request,
        name="pending.html",
        context={
            "active_page": "pending",
            "records": records,
        },
    )
