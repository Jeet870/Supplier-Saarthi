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
