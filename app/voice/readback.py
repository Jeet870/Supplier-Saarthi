"""Build the read-back sentence from a finished record.

The sentence is built by plain Python from the record, never by the AI, so it can only
say what the record really contains. Hinglish in English letters, short, ends with "Sahi hai?".
"""
import re
from datetime import date
from typing import Optional

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _num(value) -> str:
    """5.0 -> '5', 2.5 -> '2.5'"""
    if value is None:
        return ""
    return str(int(value)) if float(value) == int(value) else str(value)


def _short_name(name: Optional[str]) -> str:
    """'Maggi Noodles 70g' -> 'Maggi Noodles' (the size is dropped, it is long to say aloud)."""
    if not name:
        return ""
    return re.sub(r"\s+\d+(\.\d+)?\s?(g|gm|kg|ml|l|ltr)\b.*$", "", name, flags=re.IGNORECASE).strip()


def _qty(value, unit) -> str:
    return " ".join(x for x in [_num(value), unit or ""] if x)


def _human(issue_type: str) -> str:
    return issue_type.replace("_", " ").lower()


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _date_phrase(value) -> str:
    try:
        d = date.fromisoformat(str(value)[:10])
        return f"{d.day} {MONTHS[d.month - 1]}"
    except (ValueError, TypeError):
        return ""


# ---------- delivery ----------

def _line_sentences(line: dict) -> list[str]:
    name = _short_name(line.get("product_name"))
    unit = line.get("unit")
    exp, rec = line.get("expected_qty"), line.get("received_qty")
    out: list[str] = []

    if exp is not None and rec is not None:
        out.append(f"{name} {_qty(exp, unit)} mangaye the, {_num(rec)} aaye".strip())
    elif exp is not None:
        out.append(f"{name} {_qty(exp, unit)} mangaye the".strip())
    elif rec is not None:
        out.append(f"{name} {_qty(rec, unit)} aaye".strip())
    has_head = bool(out)

    issues = line.get("issues") or ([{"type": line["issue"]}] if line.get("issue") else [])
    for issue in issues:
        t = issue.get("type") or ""
        detail = issue.get("detail")
        qty = issue.get("qty")
        lead = "" if has_head else name  # say the product name once, in the first sentence of the line
        if t == "MISSING_QTY":
            short = line.get("shortage_qty") if line.get("shortage_qty") is not None else qty
            if short is not None:
                s = f"{_qty(short, unit)} kam" if has_head else f"{lead} {_qty(short, unit)} kam aaya".strip()
            else:
                s = "maal kam aaya" if not lead else f"{lead} kam aaya"
        elif t == "DAMAGED":
            q = qty if qty is not None else line.get("damaged_qty")
            s = (f"{lead} {_qty(q, unit)} damage hue".strip() if q is not None
                 else f"{lead} damage aaya".strip())
        elif t == "QUALITY":
            where = f"{_qty(qty, unit)} mein " if qty is not None else ""
            s = f"{lead} {where}quality problem{': ' + detail if detail else ''}".strip()
        elif t == "WRONG_SKU":
            who = f"{name} ki jagah " if name else ""
            s = f"{who}galat maal aaya" + (f", {_qty(qty, unit)}" if qty is not None else "")
        elif t == "PRICE_MISMATCH":
            amt = line.get("amount_diff_rs")
            if amt is None:
                s = f"{lead} ke rate mein farak".strip()
            else:
                s = f"{lead} ka rate Rs {_num(abs(amt))} {'zyada' if amt > 0 else 'kam'}".strip()
        elif t == "INVOICE_MISMATCH":
            amt = line.get("amount_diff_rs")
            s = (f"bill mein Rs {_num(abs(amt))} {'zyada' if amt > 0 else 'kam'}" if amt is not None
                 else "bill aur maal mein farak")
        else:  # OTHER or a category made up by the AI
            s = f"{lead} {_human(t) or 'dikkat'}{': ' + detail if detail else ''}".strip()
        out.append(s)
        has_head = True
    return out


def _delivery_readback(record: dict) -> str:
    sentences: list[str] = []
    for line in record.get("lines") or []:
        sentences.extend(_line_sentences(line))
    if not sentences:
        return ""
    supplier = record.get("supplier_name") or "Supplier"
    sentences[0] = f"{supplier} se {sentences[0]}"
    return ". ".join(_cap(s) if i else s for i, s in enumerate(sentences)) + ". Sahi hai?"


# ---------- promise ----------

def _promise_readback(record: dict) -> str:
    supplier = record.get("supplier_name") or "Supplier"
    ptype = record.get("promise_type")
    product = _short_name(record.get("product_name"))
    value, vtype, unit = record.get("value"), record.get("value_type"), record.get("unit")
    applies = record.get("applies_to")
    when = ""
    if applies == "NEXT_ORDER":
        when = " agli baar"
    elif applies == "DATE" and _date_phrase(record.get("follow_up_date")):
        when = f" {_date_phrase(record.get('follow_up_date'))} tak"

    if ptype == "DISCOUNT":
        if value is not None and vtype == "PERCENT":
            amount = f"{_num(value)}% "
        elif value is not None and vtype == "AMOUNT_RS":
            amount = f"Rs {_num(value)} "
        else:
            amount = ""
        on = f" {product} par" if product else ""
        body = f"{supplier} ne{when}{on} {amount}discount dene ka wada kiya"
    elif ptype == "REPLACEMENT":
        what = f"{product} " if product else "maal "
        body = f"{supplier} ne{when} {what}badalne ka wada kiya"
    elif ptype == "CREDIT_NOTE":
        amount = f"Rs {_num(value)} ka " if value is not None else ""
        body = f"{supplier} ne{when} {amount}credit note dene ka wada kiya"
    elif ptype == "FREE_GOODS":
        what = " ".join(x for x in [_qty(value, unit) if value is not None else "", product] if x) or "maal"
        body = f"{supplier} ne{when} {what} free dene ka wada kiya"
    elif ptype == "CREDIT_PERIOD":
        days = f"{_num(value)} din ka " if value is not None else ""
        body = f"{supplier} ne {days}udhaar (credit) dene ka wada kiya"
    elif ptype == "PRICE_LOCK":
        on = f"{product} ka " if product else ""
        price = f" Rs {_num(value)} par" if value is not None else ""
        body = f"{supplier} ne {on}rate{price} fix rakhne ka wada kiya"
    else:
        body = f"{supplier} ne yeh wada kiya: {record.get('transcript') or ''}".strip()
    return re.sub(r"\s+", " ", body).strip() + ". Sahi hai?"


def build_readback(record: dict) -> str:
    """record is the dict form of a delivery or promise record. Returns "" if there is nothing to say."""
    if record.get("record_type") == "DELIVERY_DISCREPANCY":
        return _delivery_readback(record)
    if record.get("record_type") == "SUPPLIER_PROMISE":
        return _promise_readback(record)
    return ""