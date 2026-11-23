"""Check name matching against the REAL supplier and product lists in the database.
No AI is used here.

Run from the Supplier-Saarthi folder:
    python scripts/try_matching.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.matching import load_lists, match_id  # noqa: E402

# (what was said, which list, official name it must give or None for "no match")
CHECKS = [
    ("Sharma Distributors", "s", "Sharma Distributors"),
    ("Sharma ji", "s", "Sharma Distributors"),
    ("sharma", "s", "Sharma Distributors"),
    ("SHARMA JI", "s", "Sharma Distributors"),
    ("Sharma Distributer", "s", "Sharma Distributors"),
    ("Gupta ji", "s", "Gupta Wholesale"),
    ("balaji", "s", "Balaji Traders"),
    ("Kumar", "s", "Kumar Provisions"),
    ("Ramesh Traders", "s", None),
    ("Maggi", "p", "Maggi Noodles 70g"),
    ("Maggi noodles", "p", "Maggi Noodles 70g"),
    ("magi", "p", "Maggi Noodles 70g"),
    ("Surf Excel", "p", "Surf Excel Easy Wash 1kg"),
    ("Tata namak", "p", "Tata Salt 1kg"),
    ("Parle G", "p", "Parle-G Biscuit"),
    ("ashirvad atta", "p", "Aashirvaad Atta 5kg"),
    ("sunflower oil", "p", None),
]


def main():
    suppliers, products = load_lists()
    print(f"Loaded {len(suppliers)} suppliers and {len(products)} products from the database.\n")
    passed = 0
    for spoken, which, expected in CHECKS:
        items = suppliers if which == "s" else products
        found_id, found_name = match_id(spoken, items)
        ok = found_name == expected
        passed += ok
        print(f"{'OK  ' if ok else 'FAIL'} {spoken!r:24} -> id={found_id}, name={found_name}")
    print(f"\n{passed} of {len(CHECKS)} checks passed")


if __name__ == "__main__":
    main()