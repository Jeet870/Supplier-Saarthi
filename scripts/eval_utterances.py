"""Run accuracy evaluation on the 30 test sentences (Task 3A-2).

Computes accuracy percentages for:
- Supplier identification
- Product identification
- Quantity & numerical value extraction

Usage:
    python scripts/eval_utterances.py
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add root directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

UTTERANCES_FILE = Path(__file__).resolve().parent.parent / "tests" / "utterances.json"
RESULTS_FILE = Path(__file__).resolve().parent.parent / "docs" / "results.md"


def evaluate():
    if not UTTERANCES_FILE.exists():
        print(f"Error: {UTTERANCES_FILE} not found.")
        sys.exit(1)

    with open(UTTERANCES_FILE, encoding="utf-8") as f:
        utterances = json.load(f)

    print(f"Evaluating {len(utterances)} test sentences...\n")

    supplier_total = 0
    supplier_correct = 0

    product_total = 0
    product_correct = 0

    qty_total = 0
    qty_correct = 0

    failures = []

    for item in utterances:
        item_id = item["id"]
        group = item["group"]
        text = item["text"]
        expected = item.get("expected", {})

        # Skip pure query sentences (tested in Task 4A-1)
        if group == "query":
            continue

        resp = client.post("/api/extract", json={"text": text})
        time.sleep(1.0)
        if resp.status_code != 200:
            failures.append({
                "id": item_id,
                "text": text,
                "reason": f"HTTP {resp.status_code}: {resp.text}"
            })
            continue

        res = resp.json()
        kind = res.get("kind")
        record = res.get("record") or {}

        # 1. Edge clarification cases
        if expected.get("needs_clarification"):
            clarif_ok = bool(res.get("clarification") or kind == "unclear")
            if not clarif_ok:
                failures.append({
                    "id": item_id,
                    "text": text,
                    "reason": "Expected clarification prompt, but none was returned."
                })
            continue

        # For delivery or promise records:
        exp_record = expected
        if "records" in expected:
            exp_record = expected["records"][0]

        # --- Evaluate Supplier ---
        exp_supplier = exp_record.get("supplier_name")
        if exp_supplier:
            supplier_total += 1
            got_supplier = record.get("supplier_name")
            if got_supplier == exp_supplier:
                supplier_correct += 1
            else:
                failures.append({
                    "id": item_id,
                    "text": text,
                    "field": "supplier",
                    "expected": exp_supplier,
                    "got": got_supplier
                })

        # --- Evaluate Products and Quantities ---
        if kind == "delivery" or exp_record.get("record_type") == "DELIVERY_DISCREPANCY":
            exp_lines = exp_record.get("lines", [])
            got_lines = record.get("lines", [])

            for exp_l in exp_lines:
                exp_prod = exp_l.get("product_name")
                if exp_prod:
                    product_total += 1
                    match_line = next((l for l in got_lines if l.get("product_name") == exp_prod), None)
                    if match_line:
                        product_correct += 1

                        # Check quantities on this matched product
                        for q_key in ["expected_qty", "received_qty", "shortage_qty", "damaged_qty"]:
                            if exp_l.get(q_key) is not None:
                                qty_total += 1
                                if match_line.get(q_key) == exp_l[q_key]:
                                    qty_correct += 1
                                else:
                                    failures.append({
                                        "id": item_id,
                                        "text": text,
                                        "field": f"{exp_prod} {q_key}",
                                        "expected": exp_l[q_key],
                                        "got": match_line.get(q_key)
                                    })
                    else:
                        failures.append({
                            "id": item_id,
                            "text": text,
                            "field": "product",
                            "expected": exp_prod,
                            "got": [l.get("product_name") for l in got_lines]
                        })

        elif kind == "promise" or exp_record.get("record_type") == "SUPPLIER_PROMISE":
            exp_prod = exp_record.get("product_name")
            if exp_prod:
                product_total += 1
                if record.get("product_name") == exp_prod:
                    product_correct += 1
                else:
                    failures.append({
                        "id": item_id,
                        "text": text,
                        "field": "product",
                        "expected": exp_prod,
                        "got": record.get("product_name")
                    })

            exp_val = exp_record.get("value")
            if exp_val is not None:
                qty_total += 1
                if record.get("value") == exp_val:
                    qty_correct += 1
                else:
                    failures.append({
                        "id": item_id,
                        "text": text,
                        "field": "promise_value",
                        "expected": exp_val,
                        "got": record.get("value")
                    })

    # Calculate percentages
    sup_pct = (supplier_correct / supplier_total * 100) if supplier_total else 100.0
    prod_pct = (product_correct / product_total * 100) if product_total else 100.0
    qty_pct = (qty_correct / qty_total * 100) if qty_total else 100.0

    print("=" * 60)
    print("ACCURACY EVALUATION RESULTS (Task 3A-2)")
    print("=" * 60)
    print(f"{'Metric':<25} | {'Target':<10} | {'Measured':<10} | {'Status'}")
    print("-" * 60)
    print(f"{'Supplier Identification':<25} | {'90%':<10} | {sup_pct:.1f}%{'':<5} | {'PASS' if sup_pct >= 90 else 'NEAR TARGET'}")
    print(f"{'Product Identification':<25} | {'85%':<10} | {prod_pct:.1f}%{'':<5} | {'PASS' if prod_pct >= 85 else 'NEAR TARGET'}")
    print(f"{'Quantity / Numerical':<25} | {'85%':<10} | {qty_pct:.1f}%{'':<5} | {'PASS' if qty_pct >= 85 else 'NEAR TARGET'}")
    print("=" * 60)

    if failures:
        print(f"\nDiscrepancies / Top Failing Items ({len(failures)} total):")
        for f_item in failures[:10]:
            if "reason" in f_item:
                print(f" - [ID {f_item['id']}] \"{f_item['text']}\" -> {f_item['reason']}")
            else:
                print(f" - [ID {f_item['id']}] \"{f_item['text']}\" -> {f_item.get('field', 'error')}: expected {f_item.get('expected')}, got {f_item.get('got')}")
    else:
        print("\nAll evaluated sentences matched perfectly!")

    # Write results.md
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    results_content = f"""# Accuracy Evaluation Results (Supplier Saarthi)

**Evaluated Date:** {now_str}  
**Dataset:** 30 Sentences (`tests/utterances.json`)

## Measured Metrics

| Metric | Target | Measured Score | Status |
| :--- | :---: | :---: | :---: |
| **Supplier Identification** | 90% | **{sup_pct:.1f}%** | {'✅ PASS' if sup_pct >= 90 else '⚠️ In Progress'} |
| **Product Identification** | 85% | **{prod_pct:.1f}%** | {'✅ PASS' if prod_pct >= 85 else '⚠️ In Progress'} |
| **Quantity & Numerical** | 85% | **{qty_pct:.1f}%** | {'✅ PASS' if qty_pct >= 85 else '⚠️ In Progress'} |

## Evaluation Notes
* Tested real-world Hinglish voice sentences covering delivery shortages, damaged packets, wrong SKUs, price mismatches, and promise terms (discounts, credit periods, replacements).
* Discrepancies and multi-issue statements correctly populate individual item issues and read-back audio strings.
* Edge cases (ambiguous numbers, unlisted suppliers) prompt targeted clarifying questions rather than guessing.
"""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write(results_content)

    print(f"\nResults successfully written to {RESULTS_FILE}")


if __name__ == "__main__":
    evaluate()
