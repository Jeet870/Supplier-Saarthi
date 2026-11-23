import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from app.config import settings

_client: Optional[Client] = None


def get_supabase_client() -> Client:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from environment.")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _client


def get_suppliers() -> List[Dict[str, Any]]:
    """Return all suppliers ordered by name."""
    client = get_supabase_client()
    resp = client.table("suppliers").select("id, name, aliases, created_at").order("name").execute()
    return resp.data or []


def get_products() -> List[Dict[str, Any]]:
    """Return all products ordered by name."""
    client = get_supabase_client()
    resp = client.table("products").select("id, name, aliases, default_unit, created_at").order("name").execute()
    return resp.data or []


def _serialize_for_db(val: Any) -> Any:
    """Helper to convert dates, datetimes, and enums for Supabase."""
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if hasattr(val, "value"):  # Enum support
        return val.value
    if isinstance(val, dict):
        return {k: _serialize_for_db(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_serialize_for_db(v) for v in val]
    return val


def save_record(record_data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new delivery discrepancy or supplier promise into the records table."""
    client = get_supabase_client()

    confirmed = record_data.get("confirmed", False)
    if not confirmed:
        raise ValueError("Only confirmed records can be saved. Please confirm before saving.")

    status = record_data.get("status", "OPEN")
    if hasattr(status, "value"):
        status = status.value
    if status == "DRAFT":
        status = "OPEN"

    record_type = record_data.get("record_type")
    if hasattr(record_type, "value"):
        record_type = record_type.value

    payload: Dict[str, Any] = {
        "record_type": record_type,
        "supplier_id": record_data.get("supplier_id"),
        "supplier_name": record_data.get("supplier_name"),
        "status": status,
        "transcript": record_data.get("transcript", ""),
        "photos": record_data.get("photos") or [],
        "summary_text": record_data.get("summary_text"),
        "confirmed": confirmed,
    }

    if record_data.get("event_date"):
        payload["event_date"] = _serialize_for_db(record_data["event_date"])

    if record_type == "DELIVERY_DISCREPANCY":
        raw_lines = record_data.get("lines") or []
        payload["lines"] = _serialize_for_db(raw_lines)
    elif record_type == "SUPPLIER_PROMISE":
        payload["promise_type"] = _serialize_for_db(record_data.get("promise_type"))
        payload["product_id"] = record_data.get("product_id")
        payload["product_name"] = record_data.get("product_name")
        payload["value"] = record_data.get("value")
        payload["value_type"] = _serialize_for_db(record_data.get("value_type"))
        payload["unit"] = record_data.get("unit")
        payload["applies_to"] = _serialize_for_db(record_data.get("applies_to") or "NONE")
        if record_data.get("follow_up_date"):
            payload["follow_up_date"] = _serialize_for_db(record_data["follow_up_date"])

    # Clean None values for optional columns where appropriate
    resp = client.table("records").insert(payload).execute()
    if not resp.data:
        raise RuntimeError("Failed to insert record into Supabase")
    return resp.data[0]


def get_supplier_timeline(supplier_id: int) -> List[Dict[str, Any]]:
    """Return all records for a supplier, newest first."""
    client = get_supabase_client()
    resp = (
        client.table("records")
        .select("*")
        .eq("supplier_id", supplier_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def get_pending_records(
    supplier_id: Optional[int] = None, record_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return open/unresolved records from pending_records view."""
    client = get_supabase_client()
    query = client.table("pending_records").select("*")

    if supplier_id:
        query = query.eq("supplier_id", supplier_id)
    if record_type:
        query = query.eq("record_type", record_type)

    resp = query.order("created_at", desc=True).execute()
    return resp.data or []


def update_record_status(record_id: int, new_status: str) -> Dict[str, Any]:
    """Update status of a record by ID."""
    client = get_supabase_client()
    resp = (
        client.table("records")
        .update({"status": new_status})
        .eq("id", record_id)
        .execute()
    )
    if not resp.data:
        raise RuntimeError(f"Record with id {record_id} not found or update failed.")
    return resp.data[0]


def get_summary_counts() -> Dict[str, int]:
    """Return counts of open deliveries and open promises for Home screen."""
    client = get_supabase_client()
    open_deliveries = (
        client.table("records")
        .select("id", count="exact")
        .eq("record_type", "DELIVERY_DISCREPANCY")
        .eq("confirmed", True)
        .in_("status", ["OPEN", "DISPUTED"])
        .execute()
    )
    open_promises = (
        client.table("records")
        .select("id", count="exact")
        .eq("record_type", "SUPPLIER_PROMISE")
        .eq("confirmed", True)
        .in_("status", ["OPEN", "PARTLY_FULFILLED"])
        .execute()
    )
    return {
        "open_deliveries": open_deliveries.count or 0,
        "open_promises": open_promises.count or 0,
    }


def upload_photo(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """Upload photo to Supabase storage bucket 'evidence' and return its public URL."""
    client = get_supabase_client()
    clean_filename = filename.replace(" ", "_")
    unique_path = f"{uuid.uuid4().hex[:10]}_{clean_filename}"
    client.storage.from_("evidence").upload(
        path=unique_path,
        file=file_bytes,
        file_options={"content-type": content_type},
    )
    return client.storage.from_("evidence").get_public_url(unique_path)


def reset_demo_data() -> int:
    """Reset database records to the 7 canonical demo story rows (Task 4B-2)."""
    client = get_supabase_client()

    # Fetch suppliers and products map
    sup_rows = client.table("suppliers").select("id, name").execute().data or []
    sup_map = {s["name"]: s["id"] for s in sup_rows}

    prod_rows = client.table("products").select("id, name").execute().data or []
    prod_map = {p["name"]: p["id"] for p in prod_rows}

    # Clear all records
    client.table("records").delete().neq("id", 0).execute()

    demo_records = [
        # D1. Sharma: Surf Excel short by 1 carton (open)
        {
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_id": sup_map.get("Sharma Distributors", 1),
            "supplier_name": "Sharma Distributors",
            "event_date": "2026-11-12",
            "status": "OPEN",
            "transcript": "Sharma Distributors ka Surf Excel 6 mein se 5 carton aaye",
            "summary_text": "Sharma Distributors: Surf Excel 6 carton mangaya, 5 aaye. 1 carton kam.",
            "confirmed": True,
            "created_at": "2026-11-12T10:30:00+05:30",
            "photos": [],
            "lines": [
                {
                    "product_id": prod_map.get("Surf Excel Easy Wash 1kg", 2),
                    "product_name": "Surf Excel Easy Wash 1kg",
                    "unit": "carton",
                    "expected_qty": 6,
                    "received_qty": 5,
                    "damaged_qty": None,
                    "shortage_qty": 1,
                    "issue": "MISSING_QTY",
                    "amount_diff_rs": None,
                    "note": None,
                }
            ],
        },
        # D2. Sharma: promised 15 days credit (open)
        {
            "record_type": "SUPPLIER_PROMISE",
            "supplier_id": sup_map.get("Sharma Distributors", 1),
            "supplier_name": "Sharma Distributors",
            "event_date": "2026-11-14",
            "status": "OPEN",
            "transcript": "Sharma ne 15 din ka udhaar dene ko bola hai",
            "summary_text": "Sharma Distributors ne 15 din ka udhaar dene ka wada kiya.",
            "confirmed": True,
            "created_at": "2026-11-14T11:00:00+05:30",
            "photos": [],
            "promise_type": "CREDIT_PERIOD",
            "product_id": None,
            "product_name": None,
            "value": 15,
            "value_type": "DAYS",
            "unit": None,
            "applies_to": "NONE",
            "follow_up_date": None,
        },
        # D3. Gupta: wrong item sent, Tata Salt (disputed)
        {
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_id": sup_map.get("Gupta Wholesale", 2),
            "supplier_name": "Gupta Wholesale",
            "event_date": "2026-11-15",
            "status": "DISPUTED",
            "transcript": "Gupta ji ne Tata Salt ki jagah dusra namak bhej diya",
            "summary_text": "Gupta Wholesale: Tata Salt ki jagah dusra namak aaya.",
            "confirmed": True,
            "created_at": "2026-11-15T09:45:00+05:30",
            "photos": [],
            "lines": [
                {
                    "product_id": prod_map.get("Tata Salt 1kg", 3),
                    "product_name": "Tata Salt 1kg",
                    "unit": None,
                    "expected_qty": None,
                    "received_qty": None,
                    "damaged_qty": None,
                    "shortage_qty": None,
                    "issue": "WRONG_SKU",
                    "amount_diff_rs": None,
                    "note": None,
                }
            ],
        },
        # D4. Gupta: promised to replace the Tata Salt tomorrow (open, follow-up 20 Nov)
        {
            "record_type": "SUPPLIER_PROMISE",
            "supplier_id": sup_map.get("Gupta Wholesale", 2),
            "supplier_name": "Gupta Wholesale",
            "event_date": "2026-11-15",
            "status": "OPEN",
            "transcript": "Gupta ji ne kaha jo Tata Salt kam aaya woh kal bhej denge",
            "summary_text": "Gupta Wholesale ne Tata Salt badalne ka wada kiya (20 Nov tak).",
            "confirmed": True,
            "created_at": "2026-11-15T09:50:00+05:30",
            "photos": [],
            "promise_type": "REPLACEMENT",
            "product_id": prod_map.get("Tata Salt 1kg", 3),
            "product_name": "Tata Salt 1kg",
            "value": None,
            "value_type": None,
            "unit": None,
            "applies_to": "DATE",
            "follow_up_date": "2026-11-20",
        },
        # D5. Balaji: Parle-G rate Rs 5 too high (resolved)
        {
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_id": sup_map.get("Balaji Traders", 3),
            "supplier_name": "Balaji Traders",
            "event_date": "2026-11-10",
            "status": "RESOLVED",
            "transcript": "Balaji ke bill mein Parle-G ka rate 5 rupaye zyada laga hai",
            "summary_text": "Balaji Traders: Parle-G ka rate bill mein Rs 5 zyada tha.",
            "confirmed": True,
            "created_at": "2026-11-10T12:15:00+05:30",
            "photos": [],
            "lines": [
                {
                    "product_id": prod_map.get("Parle-G Biscuit", 4),
                    "product_name": "Parle-G Biscuit",
                    "unit": None,
                    "expected_qty": None,
                    "received_qty": None,
                    "damaged_qty": None,
                    "shortage_qty": None,
                    "issue": "PRICE_MISMATCH",
                    "amount_diff_rs": 5,
                    "note": None,
                }
            ],
        },
        # D6. Kumar: promised a Rs 500 credit note (open)
        {
            "record_type": "SUPPLIER_PROMISE",
            "supplier_id": sup_map.get("Kumar Provisions", 4),
            "supplier_name": "Kumar Provisions",
            "event_date": "2026-11-13",
            "status": "OPEN",
            "transcript": "Kumar Provisions ne 500 rupaye ka credit note dene ka bola hai",
            "summary_text": "Kumar Provisions ne Rs 500 ka credit note dene ka wada kiya.",
            "confirmed": True,
            "created_at": "2026-11-13T16:20:00+05:30",
            "photos": [],
            "promise_type": "CREDIT_NOTE",
            "product_id": None,
            "product_name": None,
            "value": 500,
            "value_type": "AMOUNT_RS",
            "unit": None,
            "applies_to": "NONE",
            "follow_up_date": None,
        },
        # D7. Balaji: 3 cartons of Parle-G damaged (open)
        {
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_id": sup_map.get("Balaji Traders", 3),
            "supplier_name": "Balaji Traders",
            "event_date": "2026-11-18",
            "status": "OPEN",
            "transcript": "Balaji ke Parle-G ke 3 carton damage the",
            "summary_text": "Balaji Traders: Parle-G ke 3 carton damage aaye.",
            "confirmed": True,
            "created_at": "2026-11-18T10:05:00+05:30",
            "photos": [],
            "lines": [
                {
                    "product_id": prod_map.get("Parle-G Biscuit", 4),
                    "product_name": "Parle-G Biscuit",
                    "unit": "carton",
                    "expected_qty": None,
                    "received_qty": None,
                    "damaged_qty": 3,
                    "shortage_qty": None,
                    "issue": "DAMAGED",
                    "amount_diff_rs": None,
                    "note": None,
                }
            ],
        },
    ]

    insert_resp = client.table("records").insert(demo_records).execute()
    return len(insert_resp.data or [])


