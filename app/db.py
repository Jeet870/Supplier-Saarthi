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

    # If confirmed is true and status was DRAFT, promote to OPEN
    confirmed = record_data.get("confirmed", False)
    status = record_data.get("status", "DRAFT")
    if hasattr(status, "value"):
        status = status.value
    if confirmed and status == "DRAFT":
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

