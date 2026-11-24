"""Noisy-room accuracy evaluation on 10 realistic kirana utterances (Task 5A-1).

Simulates kirana shop environment with ambient noise, fan hum, conversational fillers,
and phonetic slips.

Usage:
    python scripts/eval_noisy.py
"""
import json
import os
import sys
import time
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

NOISY_SAMPLES = [
    {
        "id": 1,
        "text": "bhai fan bahut tez chal raha hai Sharma ji ka Maggi 5 carton mangaya tha sirf 4 aaye",
        "expected_supplier": "Sharma Distributors",
        "expected_product": "Maggi Noodles 70g",
        "expected_issue": "MISSING_QTY",
    },
    {
        "id": 2,
        "text": "sharma ke yahan se sarf excel ke do packet fate hue aaye the",
        "expected_supplier": "Sharma Distributors",
        "expected_product": "Surf Excel Easy Wash 1kg",
        "expected_issue": "DAMAGED",
    },
    {
        "id": 3,
        "text": "arre suno gupta ji ne tata salt ki jagah dusra namak bhej diya",
        "expected_supplier": "Gupta Wholesale",
        "expected_product": "Tata Salt 1kg",
        "expected_issue": "WRONG_SKU",
    },
    {
        "id": 4,
        "text": "balaji ke bill mein parle g biscuit ka rate 5 rupaye zyada laga diya hai",
        "expected_supplier": "Balaji Traders",
        "expected_product": "Parle-G Biscuit",
        "expected_issue": "PRICE_MISMATCH",
    },
    {
        "id": 5,
        "text": "kumar provisions ke bill mein 20 packet aashirvaad atta likha hai par 18 aaye",
        "expected_supplier": "Kumar Provisions",
        "expected_product": "Aashirvaad Atta 5kg",
        "expected_issue": "MISSING_QTY",
    },
    {
        "id": 6,
        "text": "sharma ka maggi 5 mein se 4 carton aaye aur surf excel ke 2 packet damage the",
        "expected_supplier": "Sharma Distributors",
        "expected_product": "Maggi Noodles 70g",
        "expected_issue": "MISSING_QTY",
    },
    {
        "id": 7,
        "text": "sharma wala surf excel ka ek carton poora bheega hua aaya",
        "expected_supplier": "Sharma Distributors",
        "expected_product": "Surf Excel Easy Wash 1kg",
        "expected_issue": "DAMAGED",
    },
    {
        "id": 8,
        "text": "gupta ji ne 3 carton parle g kam bheje",
        "expected_supplier": "Gupta Wholesale",
        "expected_product": "Parle-G Biscuit",
        "expected_issue": "MISSING_QTY",
    },
    {
        "id": 9,
        "text": "agli baar surf excel par 5 percent extra dena sharma ne bola hai",
        "expected_supplier": "Sharma Distributors",
        "expected_product": "Surf Excel Easy Wash 1kg",
        "expected_promise": "DISCOUNT",
    },
    {
        "id": 10,
        "text": "gupta ji ne kaha jo tata salt kam aaya woh kal bhej denge",
        "expected_supplier": "Gupta Wholesale",
        "expected_product": "Tata Salt 1kg",
        "expected_promise": "REPLACEMENT",
    },
]


def run_noisy_eval():
    print(f"Running Noisy Room Evaluation on {len(NOISY_SAMPLES)} sentences...\n")
    correct_count = 0
    results = []

    for sample in NOISY_SAMPLES:
        s_id = sample["id"]
        text = sample["text"]
        print(f"[{s_id}/10] Testing: \"{text}\"")

        resp = client.post("/api/extract", json={"text": text})
        time.sleep(1.0)  # Pacing to avoid rate limit spikes

        if resp.status_code != 200:
            print(f"  ❌ Failed with HTTP {resp.status_code}: {resp.text}")
            results.append({"id": s_id, "status": "FAIL", "reason": f"HTTP {resp.status_code}"})
            continue

        data = resp.json()
        record = data.get("record") or {}
        kind = data.get("kind")

        all_records = [record]
        for item in (data.get("additional") or []):
            if item.get("record"):
                all_records.append(item["record"])

        # Verify supplier
        supplier_ok = any(r.get("supplier_name") == sample["expected_supplier"] for r in all_records)
        got_supplier = record.get("supplier_name")

        # Verify product
        all_products = []
        for r in all_records:
            if "lines" in r:
                all_products.extend([l.get("product_name") for l in (r.get("lines") or [])])
            if r.get("product_name"):
                all_products.append(r.get("product_name"))
        product_ok = sample["expected_product"] in all_products

        # Check issues/promise type
        detail_ok = False
        if "expected_issue" in sample:
            for r in all_records:
                for l in (r.get("lines") or []):
                    if l.get("issue") == sample["expected_issue"]:
                        detail_ok = True
        elif "expected_promise" in sample:
            for r in all_records:
                if r.get("promise_type") == sample["expected_promise"]:
                    detail_ok = True

        is_correct = supplier_ok and product_ok and detail_ok
        if is_correct:
            correct_count += 1
            print(f"  ✅ Correct -> Supplier: {sample['expected_supplier']}, Product(s): {all_products}")
            results.append({"id": s_id, "status": "CORRECT", "supplier": sample["expected_supplier"]})
        else:
            print(f"  ⚠️ Partial/Wrong -> Supplier: {got_supplier} (expected {sample['expected_supplier']}), Products: {all_products} (expected {sample['expected_product']})")
            results.append({"id": s_id, "status": "PARTIAL", "got_supplier": got_supplier, "got_products": all_products})

    accuracy = (correct_count / len(NOISY_SAMPLES)) * 100.0
    print("\n" + "=" * 50)
    print(f"NOISY ROOM TEST RESULT: {correct_count}/{len(NOISY_SAMPLES)} ({accuracy:.1f}%)")
    print("=" * 50)
    return correct_count, len(NOISY_SAMPLES), accuracy


if __name__ == "__main__":
    run_noisy_eval()
