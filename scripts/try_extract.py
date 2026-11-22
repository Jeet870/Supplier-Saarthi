"""Try the extractor from the terminal. No database needed.

Run the built-in checks (from the Supplier-Saarthi folder):
    python scripts/try_extract.py

Try your own sentence:
    python scripts/try_extract.py --type delivery "Sharma ke yahan se Maggi 5 carton mein 4 aaye"
    python scripts/try_extract.py --type promise "Gupta ne bola agli baar Tata Salt par 3 rupaye kam"
"""
import argparse
import sys
from datetime import date
from pathlib import Path

# Lets this file import from the app/ folder when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.voice.extract import DELIVERY, PROMISE, extract_record  # noqa: E402

# Demo lists. The real ids come from the database; these are only for this test.
SUPPLIERS = [
    {"id": 1, "name": "Sharma Distributors"},
    {"id": 2, "name": "Gupta Wholesale"},
    {"id": 3, "name": "Balaji Traders"},
    {"id": 4, "name": "Kumar Provisions"},
]
PRODUCTS = [
    {"id": 1, "name": "Maggi Noodles 70g", "aliases": ["maggi", "maggi noodles"]},
    {"id": 2, "name": "Surf Excel Easy Wash 1kg", "aliases": ["surf excel", "surf"]},
    {"id": 3, "name": "Tata Salt 1kg", "aliases": ["tata namak", "namak", "tata salt"]},
    {"id": 4, "name": "Fortune Sunflower Oil 1L", "aliases": ["fortune oil", "sunflower oil", "tel"]},
    {"id": 5, "name": "Aashirvaad Atta 5kg", "aliases": ["atta", "aashirvaad"]},
]


def _delivery_ok(r):
    rec = r.record
    if rec is None or rec.supplier_id != 1 or len(rec.lines) != 2:
        return False
    maggi = next((l for l in rec.lines if l.product_id == 1), None)
    surf = next((l for l in rec.lines if l.product_id == 2), None)
    return bool(
        maggi and maggi.issue.value == "MISSING_QTY" and maggi.expected_qty == 5
        and maggi.received_qty == 4 and maggi.shortage_qty == 1
        and surf and surf.issue.value == "DAMAGED" and surf.damaged_qty == 2
        and rec.status.value == "DRAFT" and rec.confirmed is False
    )


def _promise_ok(r):
    rec = r.record
    return bool(
        rec and rec.supplier_id == 1 and rec.promise_type.value == "DISCOUNT"
        and rec.product_id == 2 and rec.value == 5 and rec.value_type.value == "PERCENT"
        and rec.applies_to.value == "NEXT_ORDER" and rec.status.value == "DRAFT"
    )


def _asks_supplier(r):
    # Nothing about a supplier was said, so the supplier stays empty and we must ask.
    return bool(r.record and r.record.supplier_id is None and r.clarification_question)


def _unknown_supplier(r):
    return bool(r.record and r.record.supplier_id is None and r.record.supplier_name and r.clarification_question)


# (type, what the shopkeeper says, what must be true, short description)
SAMPLES = [
    (DELIVERY, "Sharma Distributors ne Maggi 5 carton bola tha, 4 hi aaye. Surf Excel ke 2 packet phate hue the.",
     _delivery_ok, "supplier 1; Maggi missing 1 carton; Surf Excel 2 damaged"),
    (PROMISE, "Sharma ji ne bola agli baar Surf Excel par 5 percent discount dega.",
     _promise_ok, "DISCOUNT, 5 PERCENT, Surf Excel, NEXT_ORDER"),
    (DELIVERY, "Aaj Maggi ke 3 carton kam aaye.",
     _asks_supplier, "no supplier said, so supplier is null and a question is asked"),
    (DELIVERY, "Ramesh Traders se tel ka ek carton kam aaya.",
     _unknown_supplier, "supplier not in list, so id is null and a question is asked"),
]


def run_one(record_type, text):
    result = extract_record(record_type, text, SUPPLIERS, PRODUCTS, today=date.today())
    print(f'\nSAID: "{text}"')
    if result.error:
        print("ERROR:", result.error)
    if result.record:
        print(result.record.model_dump_json(indent=2))
    if result.clarification_question:
        print("QUESTION TO ASK:", result.clarification_question)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", help="what the shopkeeper said")
    parser.add_argument("--type", choices=["delivery", "promise"], default="delivery")
    args = parser.parse_args()

    if args.text:
        run_one(DELIVERY if args.type == "delivery" else PROMISE, args.text)
        return

    passed = 0
    for i, (rtype, text, check, expect) in enumerate(SAMPLES, start=1):
        result = run_one(rtype, text)
        ok = False
        try:
            ok = check(result)
        except Exception:
            ok = False
        print(f"CHECK {i}: {'OK' if ok else 'FAIL'}  (expected: {expect})")
        passed += ok
    print(f"\n{passed} of {len(SAMPLES)} checks passed")


if __name__ == "__main__":
    main()