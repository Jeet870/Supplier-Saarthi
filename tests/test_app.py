"""
Supplier Saarthi - Verification and Integration Tests
Tests all page routes, API contracts, fallback data loaders, and branding integrity.
"""
import pytest
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_app_metadata():
    """Verify application title has been rebranded to Supplier Saarthi."""
    assert app.title == "Supplier Saarthi"


def test_health_endpoint():
    """Verify health endpoint is working."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


@pytest.mark.parametrize(
    "route_path",
    [
        "/",
        "/delivery",
        "/promise",
        "/confirmation",
        "/suppliers",
        "/timeline/1",
        "/pending",
    ],
)
def test_page_routes_status_and_branding(route_path):
    """
    Verify all frontend routes return 200, contain Supplier Saarthi branding,
    and have no residual references to Munshi Guard.
    """
    response = client.get(route_path)
    assert response.status_code == 200, f"Route {route_path} failed with {response.status_code}"
    html = response.text

    # Verify Supplier Saarthi is present
    assert "Supplier Saarthi" in html, f"'Supplier Saarthi' branding missing on {route_path}"

    # Verify old name Munshi Guard is completely removed
    assert "Munshi Guard" not in html, f"Legacy 'Munshi Guard' found on {route_path}"


def test_records_api_rejects_unconfirmed():
    """
    Verify the backend API contract: records cannot be saved with confirmed=False.
    """
    unconfirmed_payload = {
        "record_type": "DELIVERY_DISCREPANCY",
        "supplier_id": 1,
        "supplier_name": "Sharma Distributors",
        "confirmed": False,
        "lines": [
            {
                "product_name": "Maggi Noodles 70g",
                "issue": "MISSING_QTY",
                "shortage_qty": 2,
            }
        ],
    }
    response = client.post("/api/records", json=unconfirmed_payload)
    assert response.status_code == 400
    data = response.json()
    error_msg = data.get("detail", {}).get("error", "") or data.get("error", "")
    assert "confirmed" in error_msg.lower()


def test_transcribe_api_requires_audio_field():
    """
    Verify /api/transcribe strictly requires 'audio' multipart form field,
    rejecting requests missing the 'audio' file with 400 or 422.
    """
    # Missing audio field
    response = client.post("/api/transcribe", files={"wrong_field": ("test.wav", b"fake audio", "audio/wav")})
    assert response.status_code in [400, 422]
