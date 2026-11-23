"""Match a spoken supplier or product name to the real list in the database.

"Sharma ji", "sharma" and "Sharma Distributors" must all give the same supplier id.
Matching uses the name plus the aliases stored in the database.
If two items fit equally well, or nothing fits well enough, we return None. We never guess.
"""
import re
import time
from difflib import SequenceMatcher
from typing import Optional

from app import db

MIN_SCORE = 0.75
_CACHE_SECONDS = 30
_cache = {"at": 0.0, "suppliers": [], "products": []}


def load_lists(max_age: int = _CACHE_SECONDS) -> tuple[list[dict], list[dict]]:
    """Return (suppliers, products) from the database. Kept for 30 seconds so we do not ask every time."""
    if time.time() - _cache["at"] > max_age or not _cache["suppliers"]:
        _cache["suppliers"] = db.get_suppliers()
        _cache["products"] = db.get_products()
        _cache["at"] = time.time()
    return _cache["suppliers"], _cache["products"]


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def match_id(spoken: Optional[str], items: list[dict]) -> tuple[Optional[int], Optional[str]]:
    """items: [{"id": 1, "name": "...", "aliases": [...]}, ...]
    Returns (id, official name) of the best match, or (None, None) if unsure.
    """
    if not spoken or not _norm(spoken):
        return None, None
    n = _norm(spoken)
    scores: list[tuple[float, dict]] = []
    for item in items:
        best = 0.0
        for cand in [item["name"], *(item.get("aliases") or [])]:
            c = _norm(cand)
            if not c:
                continue
            if n == c:
                best = 1.0
                break
            score = SequenceMatcher(None, n, c).ratio()
            if min(len(n), len(c)) >= 4 and (n in c or c in n):
                score = max(score, 0.85)
            best = max(best, score)
        scores.append((best, item))
    scores.sort(key=lambda s: s[0], reverse=True)
    if not scores or scores[0][0] < MIN_SCORE:
        return None, None
    if len(scores) > 1 and scores[0][0] < 1.0 and scores[1][0] >= scores[0][0] - 0.05:
        return None, None  # two equally good matches: do not guess
    return scores[0][1]["id"], scores[0][1]["name"]


def match_supplier(spoken: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    suppliers, _ = load_lists()
    return match_id(spoken, suppliers)


def match_product(spoken: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    _, products = load_lists()
    return match_id(spoken, products)