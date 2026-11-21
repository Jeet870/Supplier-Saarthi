# Route list (agreed on 19 Nov 2026)

## Screens (HTML pages, owned by C in app/routers/pages.py)
GET /                         Home
GET /delivery                 Delivery Check
GET /promise                  Promise Note
GET /suppliers                Supplier list
GET /timeline/{supplier_id}   Supplier Timeline
GET /pending                  Pending

## Data routes (JSON)
GET   /health                       -> {"status": "ok"}                      (B)
GET   /api/suppliers                -> list of suppliers                     (B)
GET   /api/products                 -> list of products                      (B)
GET   /api/summary                  -> {"open_deliveries": n, "open_promises": n}   (B)
POST  /api/transcribe  (audio file) -> {"text": "..."}                       (A)
POST  /api/extract     {"text": ""} -> see the sample below                  (A)
POST  /api/query       {"text": ""} -> {"answer_text": "...", "records": []} (A)
POST  /api/records     (confirmed record) -> saved record with its id        (B)
GET   /api/timeline/{supplier_id}   -> records, newest first                 (B)
GET   /api/pending     ?supplier_id=&record_type=   -> open records          (B)
PATCH /api/records/{id}/status  {"status": "RESOLVED"} -> updated record     (B)
POST  /api/photos      (photo file) -> {"url": "..."}                        (B)
POST  /api/demo/reset               -> {"ok": true}                          (B)

Errors always look like: {"error": "short readable message"}

## Sample answer of POST /api/extract for "Sharma ji ka Maggi 5 carton mangaya tha, sirf 4 aaye":
```json
{
  "kind": "delivery",
  "record": {
    "record_type": "DELIVERY_DISCREPANCY",
    "supplier_id": 1,
    "supplier_name": "Sharma Distributors",
    "event_date": "2026-11-19",
    "status": "DRAFT",
    "lines": [
      {
        "product_id": 1,
        "product_name": "Maggi Noodles 70g",
        "unit": "carton",
        "expected_qty": 5,
        "received_qty": 4,
        "damaged_qty": null,
        "shortage_qty": 1,
        "issue": "MISSING_QTY",
        "amount_diff_rs": null,
        "note": null
      }
    ],
    "transcript": "Sharma ji ka Maggi 5 carton mangaya tha, sirf 4 aaye",
    "photos": [],
    "confirmed": false
  },
  "readback_text": "Sharma Distributors se Maggi 5 carton mangaye the, 4 aaye. 1 carton kam. Sahi hai?",
  "clarification": null
}
```

The field kind is one of delivery, promise, unclear. When the sentence is unclear, record has nulls and clarification holds one short question to ask back.
