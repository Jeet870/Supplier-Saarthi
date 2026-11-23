"""Check the read-back sentences. No AI, no database: it only tests the sentence builder.

Run from the Supplier-Saarthi folder:
    python scripts/try_readback.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.voice.readback import build_readback  # noqa: E402


def delivery(supplier, *lines):
    return {"record_type": "DELIVERY_DISCREPANCY", "supplier_name": supplier, "lines": list(lines)}


def line(**kw):
    base = {"product_name": None, "unit": None, "expected_qty": None, "received_qty": None,
            "damaged_qty": None, "shortage_qty": None, "amount_diff_rs": None, "issues": []}
    return {**base, **kw}


def issue(kind, detail=None, qty=None):
    return {"type": kind, "detail": detail, "qty": qty}


def promise(supplier, **kw):
    base = {"record_type": "SUPPLIER_PROMISE", "supplier_name": supplier, "product_name": None,
            "value": None, "value_type": None, "unit": None, "applies_to": "NONE",
            "follow_up_date": None, "transcript": ""}
    return {**base, **kw}


MAGGI = dict(product_name="Maggi Noodles 70g", unit="carton", expected_qty=5, received_qty=4,
             shortage_qty=1, issues=[issue("MISSING_QTY", qty=1)])
SURF = dict(product_name="Surf Excel Easy Wash 1kg", unit="packet", damaged_qty=2,
            issues=[issue("DAMAGED", qty=2)])

CHECKS = [
    ("sentence 1", delivery("Sharma Distributors", line(**MAGGI)),
     "Sharma Distributors se Maggi Noodles 5 carton mangaye the, 4 aaye. 1 carton kam. Sahi hai?"),
    ("sentence 2", delivery("Sharma Distributors", line(**SURF)),
     "Sharma Distributors se Surf Excel Easy Wash 2 packet damage hue. Sahi hai?"),
    ("sentence 6 (two products)", delivery("Sharma Distributors", line(**MAGGI), line(**SURF)),
     "Sharma Distributors se Maggi Noodles 5 carton mangaye the, 4 aaye. 1 carton kam. "
     "Surf Excel Easy Wash 2 packet damage hue. Sahi hai?"),
    ("sentence 7 (bill total)", delivery("Balaji Traders", line(amount_diff_rs=200, issues=[issue("INVOICE_MISMATCH")])),
     "Balaji Traders se bill mein Rs 200 zyada. Sahi hai?"),
    ("sentence 9", delivery("Gupta Wholesale", line(product_name="Parle-G Biscuit", unit="carton", shortage_qty=3,
                                                    issues=[issue("MISSING_QTY", qty=3)])),
     "Gupta Wholesale se Parle-G Biscuit 3 carton kam aaya. Sahi hai?"),
    ("two problems, one product + a new category",
     delivery("Balaji Traders", line(product_name="Aashirvaad Atta 5kg", unit="bag", expected_qty=4, received_qty=2,
                                     shortage_qty=2, issues=[issue("MISSING_QTY", qty=2),
                                                             issue("QUALITY", "ghun lag gaya", 1),
                                                             issue("LATE_DELIVERY", "2 din late")])),
     "Balaji Traders se Aashirvaad Atta 4 bag mangaye the, 2 aaye. 2 bag kam. "
     "1 bag mein quality problem: ghun lag gaya. Late delivery: 2 din late. Sahi hai?"),
    ("promise 13", promise("Sharma Distributors", promise_type="DISCOUNT", product_name="Surf Excel Easy Wash 1kg",
                           value=5, value_type="PERCENT", applies_to="NEXT_ORDER"),
     "Sharma Distributors ne agli baar Surf Excel Easy Wash par 5% discount dene ka wada kiya. Sahi hai?"),
    ("promise 15", promise("Gupta Wholesale", promise_type="REPLACEMENT", product_name="Tata Salt 1kg",
                           applies_to="DATE", follow_up_date="2026-11-24"),
     "Gupta Wholesale ne 24 Nov tak Tata Salt badalne ka wada kiya. Sahi hai?"),
    ("promise 16", promise("Kumar Provisions", promise_type="CREDIT_NOTE", value=500, value_type="AMOUNT_RS"),
     "Kumar Provisions ne Rs 500 ka credit note dene ka wada kiya. Sahi hai?"),
    ("promise 17", promise("Sharma Distributors", promise_type="CREDIT_PERIOD", value=15, value_type="DAYS"),
     "Sharma Distributors ne 15 din ka udhaar (credit) dene ka wada kiya. Sahi hai?"),
]


def main():
    passed = 0
    for name, record, expected in CHECKS:
        got = build_readback(record)
        ok = got == expected
        passed += ok
        print(f"{'OK  ' if ok else 'FAIL'} {name}")
        if not ok:
            print(f"     expected: {expected}\n     got:      {got}")
    print(f"\n{passed} of {len(CHECKS)} checks passed")


if __name__ == "__main__":
    main()