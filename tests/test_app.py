"""
Supplier Saarthi - Verification and Integration Tests (Day 1, 2, and 3)
Tests all page routes, API contracts, photo upload, promise structures,
readback logic, compound utterance support, and branding integrity.
"""
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.voice.readback import build_readback

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


def test_delivery_page_has_photo_and_voice_controls():
    """Verify delivery page includes Day 3 photo controls and voice station elements."""
    response = client.get("/delivery")
    assert response.status_code == 200
    html = response.text
    assert "Bill / Maal ki Photo" in html
    assert "delivery-photo-input" in html
    assert "photo-lightbox" in html
    assert "mic-btn" in html
    assert "recording-timer" in html


def test_timeline_page_has_photo_lightbox():
    """Verify timeline page includes photo lightbox modal."""
    response = client.get("/timeline/1")
    assert response.status_code == 200
    html = response.text
    assert "photo-lightbox" in html
    assert "WhatsApp Share" in html


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


def test_promise_record_validation():
    """Verify promise record validation and rejection when unconfirmed."""
    unconfirmed_promise = {
        "record_type": "SUPPLIER_PROMISE",
        "supplier_id": 1,
        "supplier_name": "Sharma Distributors",
        "promise_type": "DISCOUNT",
        "product_name": "Surf Excel Easy Wash 1kg",
        "value": 5,
        "value_type": "PERCENT",
        "applies_to": "NEXT_ORDER",
        "confirmed": False,
    }
    response = client.post("/api/records", json=unconfirmed_promise)
    assert response.status_code == 400
    data = response.json()
    error_msg = data.get("detail", {}).get("error", "") or data.get("error", "")
    assert "confirmed" in error_msg.lower()


def test_transcribe_api_requires_audio_field():
    """
    Verify /api/transcribe strictly requires 'audio' multipart form field,
    rejecting requests missing the 'audio' file with 400 or 422.
    """
    response = client.post("/api/transcribe", files={"wrong_field": ("test.wav", b"fake audio", "audio/wav")})
    assert response.status_code in [400, 422]


def test_photos_api_requires_file_field():
    """
    Verify /api/photos strictly requires 'file' multipart form field,
    rejecting requests with missing 'file' parameter with 400 or 422.
    """
    response = client.post("/api/photos", files={"wrong_field": ("test.jpg", b"fake image bytes", "image/jpeg")})
    assert response.status_code in [400, 422]


def test_photos_api_upload_success_mocked():
    """
    Verify /api/photos successfully uploads and returns public URL format.
    """
    mock_url = "https://mock-supabase.co/storage/v1/object/public/evidence/photo_test123.jpg"
    with patch("app.db.upload_photo", return_value=mock_url):
        response = client.post(
            "/api/photos",
            files={"file": ("bill.jpg", b"fake-jpg-content", "image/jpeg")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("url") == mock_url


def test_records_api_save_with_photos_mocked():
    """
    Verify POST /api/records accepts and persists photo links in payload.
    """
    fake_saved = {
        "id": 42,
        "record_type": "DELIVERY_DISCREPANCY",
        "supplier_id": 1,
        "supplier_name": "Sharma Distributors",
        "status": "OPEN",
        "photos": ["https://mock-supabase.co/photo1.jpg"],
        "confirmed": True,
    }
    with patch("app.db.save_record", return_value=fake_saved):
        payload = {
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_id": 1,
            "supplier_name": "Sharma Distributors",
            "confirmed": True,
            "photos": ["https://mock-supabase.co/photo1.jpg"],
            "lines": [
                {
                    "product_name": "Maggi Noodles 70g",
                    "issue": "MISSING_QTY",
                    "shortage_qty": 1,
                }
            ],
        }
        response = client.post("/api/records", json=payload)
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("id") == 42
        assert "photos" in data
        assert len(data["photos"]) == 1


def test_readback_generator_delivery():
    """Verify Day 3 deterministic readback generation for delivery discrepancy."""
    record = {
        "record_type": "DELIVERY_DISCREPANCY",
        "supplier_name": "Sharma Distributors",
        "lines": [
            {
                "product_name": "Maggi Noodles 70g",
                "unit": "carton",
                "expected_qty": 5,
                "received_qty": 4,
                "shortage_qty": 1,
                "issue": "MISSING_QTY",
            }
        ],
    }
    text = build_readback(record)
    assert text.endswith("Sahi hai?")
    assert "Sharma Distributors" in text
    assert "Maggi Noodles" in text
    assert "kam" in text


def test_readback_generator_promise():
    """Verify Day 3 deterministic readback generation for supplier promise."""
    record = {
        "record_type": "SUPPLIER_PROMISE",
        "supplier_name": "Gupta Wholesale",
        "promise_type": "DISCOUNT",
        "product_name": "Tata Salt 1kg",
        "value": 5,
        "value_type": "PERCENT",
        "applies_to": "NEXT_ORDER",
    }
    text = build_readback(record)
    assert text.endswith("Sahi hai?")
    assert "Gupta Wholesale" in text
    assert "Tata Salt" in text
    assert "5% discount" in text


def test_query_empty_text():
    """Verify Day 4 POST /api/query returns friendly prompt when text is empty."""
    response = client.post("/api/query", json={"text": ""})
    assert response.status_code == 200
    data = response.json()
    assert "dobara bolo" in data.get("answer_text", "")
    assert data.get("records") == []


def test_query_mocked_pending():
    """Verify Day 4 POST /api/query with mocked pending records."""
    fake_suppliers = [{"id": 1, "name": "Sharma Distributors", "aliases": ["sharma"]}]
    fake_products = [{"id": 1, "name": "Maggi Noodles 70g", "aliases": ["maggi"]}]
    fake_records = [
        {
            "id": 101,
            "record_type": "DELIVERY_DISCREPANCY",
            "supplier_name": "Sharma Distributors",
            "lines": [{"product_name": "Maggi Noodles 70g", "shortage_qty": 2, "unit": "carton", "issue": "MISSING_QTY"}],
        }
    ]
    with patch("app.matching.load_lists", return_value=(fake_suppliers, fake_products)), \
         patch("app.db.get_pending_records", return_value=fake_records):
        response = client.post("/api/query", json={"text": "Sharma ka kya pending hai?"})
        assert response.status_code == 200
        data = response.json()
        assert len(data.get("records", [])) == 1
        assert "Sharma" in data.get("answer_text", "")


def test_pending_page_has_voice_query_and_mark_done():
    """Verify Person C Day 4 features on /pending."""
    response = client.get("/pending")
    assert response.status_code == 200
    html = response.text
    assert "pending-mic-btn" in html
    assert "pending-query-input" in html
    assert "btn-mark-done" in html or "Kuch Baqaya Nahi" in html


def test_timeline_page_has_search_and_filters():
    """Verify Person C Day 4 features on /timeline/1."""
    response = client.get("/timeline/1")
    assert response.status_code == 200
    html = response.text
    assert "timeline-search-input" in html
    assert "timeline-tab" in html


def test_patch_status_mocked():
    """Verify Day 4 PATCH /api/records/{id}/status endpoint."""
    with patch("app.db.update_record_status", return_value={"id": 1, "status": "RESOLVED"}):
        response = client.patch("/api/records/1/status", json={"status": "RESOLVED"})
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "RESOLVED"


def test_pwa_service_worker_route():
    """Verify Person C Day 5 Service Worker /sw.js route."""
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers.get("content-type", "")
    assert "supplier-saarthi" in response.text.lower()


def test_pwa_manifest_route():
    """Verify Person C Day 5 PWA manifest /manifest.json route."""
    response = client.get("/manifest.json")
    assert response.status_code == 200
    data = response.json()
    assert data.get("name") == "Supplier Saarthi"
    assert data.get("short_name") == "Saarthi"
    assert data.get("display") == "standalone"


def test_base_template_has_pwa_tags():
    """Verify base template includes PWA manifest link and service worker script."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'rel="manifest"' in html
    assert 'serviceWorker.register' in html



