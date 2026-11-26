"""First accuracy score on the 30 test sentences (tests/utterances.json).

Each sentence goes through the same steps as POST /api/extract (same AI, same name matching,
real supplier and product lists from the database). The answer is compared with "expected".

Run from the Supplier-Saarthi folder:
    python scripts/eval_utterances.py                 all 30 sentences (takes a few minutes)
    python scripts/eval_utterances.py --ids 1,6,13    only these sentences
    python scripts/eval_utterances.py --group promise only one group
    python scripts/eval_utterances.py --write-docs    also add today's numbers to docs/results.md
"""
import argparse
import json
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.routers.voice import ExtractRequest, extract  # noqa: E402

TARGETS = {"supplier": 90, "product": 85, "quantity": 85}
CHECKS = ["supplier", "product", "quantity", "type", "when"]
LINE_NUMBERS = ["expected_qty", "received_qty", "damaged_qty", "shortage_qty", "amount_diff_rs"]


# ---------- small helpers ----------

def _eq(a, b):
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def _unit_ok(exp, got):
    # If the test does not name a unit, any unit is accepted. If it names one, it must match.
    return exp is None or (got is not None and str(got).strip().lower() == str(exp).strip().lower())


def _date_ok(exp, got, tolerance_days=3):
    if exp is None:
        return got is None
    if got is None:
        return False
    try:
        return abs((date.fromisoformat(str(got)[:10]) - date.fromisoformat(exp)).days) <= tolerance_days
    except ValueError:
        return False


def _as_dict(resp):
    if isinstance(resp, dict):
        return resp
    body = getattr(resp, "body", None)  # an error answer from the route
    if body is not None:
        try:
            return json.loads(body)
        except ValueError:
            pass
    return {"error": "Unreadable answer from /api/extract"}


def call_extract(item):
    body = ExtractRequest(text=item["text"], today=date.fromisoformat(item["today"]))
    data = {"error": "no answer"}
    for attempt in range(4):
        try:
            data = _as_dict(extract(body))
        except Exception as e:  # keep going, one bad sentence must not stop the run
            data = {"error": f"{type(e).__name__}: {e}"}
        err = str(data.get("error") or "").lower()
        busy = data.get("error_code") == "RATE_LIMIT" or any(
            word in err for word in ("429", "rate limit", "too many", "thoda ruko")
        )
        if busy and attempt < 3:
            print("      (Groq is busy, waiting 25 seconds, then trying again...)")
            time.sleep(25)
            continue
        break
    return data


def got_records(data):
    """All records in the answer: the main one plus the ones in "additional"."""
    out = []
    if data.get("record"):
        out.append(data["record"])
    for extra in data.get("additional") or []:
        if extra.get("record"):
            out.append(extra["record"])
    return out


# ---------- scoring one record ----------

def score_delivery(exp, got):
    checks = {"supplier": got.get("supplier_name") == exp["supplier_name"] and got.get("supplier_id") is not None}
    got_lines = list(got.get("lines") or [])
    exp_lines = exp["lines"]

    checks["product"] = (
        Counter(l.get("product_name") for l in exp_lines) == Counter(l.get("product_name") for l in got_lines)
    )

    # Match lines by product name first. Lines left over are matched in order, so a wrong product
    # name does not also spoil the quantity and type scores.
    pairs, used = [], set()
    for e in exp_lines:
        match = next((i for i, g in enumerate(got_lines)
                      if i not in used and g.get("product_name") == e.get("product_name")), None)
        if match is not None:
            used.add(match)
        pairs.append([e, match])
    for pair in pairs:
        if pair[1] is None:
            pair[1] = next((i for i in range(len(got_lines)) if i not in used), None)
            if pair[1] is not None:
                used.add(pair[1])
    pairs = [(e, got_lines[i] if i is not None else None) for e, i in pairs]

    checks["quantity"] = all(
        g is not None and all(_eq(e.get(f), g.get(f)) for f in LINE_NUMBERS) and _unit_ok(e.get("unit"), g.get("unit"))
        for e, g in pairs
    )
    checks["type"] = all(g is not None and e.get("issue") == g.get("issue") for e, g in pairs)
    return checks


def score_promise(exp, got, tolerance_days=0):
    return {
        "supplier": got.get("supplier_name") == exp["supplier_name"] and got.get("supplier_id") is not None,
        "product": _eq(exp.get("product_name"), got.get("product_name")),
        "quantity": (_eq(exp.get("value"), got.get("value")) and _eq(exp.get("value_type"), got.get("value_type"))
                     and _unit_ok(exp.get("unit"), got.get("unit"))),
        "type": exp.get("promise_type") == got.get("promise_type"),
        "when": exp.get("applies_to") == got.get("applies_to") and _date_ok(exp.get("follow_up_date"), got.get("follow_up_date"), tolerance_days),
    }


def score_expected_record(exp, got_list, tolerance_days=0):
    """Score one expected record against the matching record (same record_type) in the answer."""
    got = next((g for g in got_list if g.get("record_type") == exp["record_type"]), None)
    if got is None:
        return {c: (False if (c != "when" or exp["record_type"] == "SUPPLIER_PROMISE") else None) for c in CHECKS}
    result = score_delivery(exp, got) if exp["record_type"] == "DELIVERY_DISCREPANCY" else score_promise(exp, got, tolerance_days)
    return {c: result.get(c) for c in CHECKS}


# ---------- the edge sentences (27, 28, 30): the app must ask a question ----------

def score_edge(exp, data):
    question = data.get("clarification")
    reason = data.get("clarification_reason")
    record = data.get("record") or {}
    why = []
    if not question:
        why.append("no question was asked")
    if reason != exp["reason"]:
        why.append(f"reason is {reason}, expected {exp['reason']}")
    if exp["reason"] == "AMBIGUOUS_NUMBER":
        for number in exp.get("candidates", []):
            if str(number) not in str(question):
                why.append(f"the question does not mention {number}")
    if exp["reason"] == "SUPPLIER_NOT_IN_LIST":
        if record.get("supplier_id") is not None:
            why.append("a supplier was wrongly matched")
        if str(record.get("supplier_name") or "").lower() != exp["heard"].lower():
            why.append(f"the heard name is {record.get('supplier_name')}, expected {exp['heard']}")
    if exp["reason"] == "NOTHING_SPECIFIED":
        if record.get("supplier_name") or record.get("lines"):
            why.append("values were guessed")
    return (not why), why


# ---------- one sentence ----------

def evaluate(item):
    started = time.time()
    data = call_extract(item)
    result = {"id": item["id"], "group": item["group"], "text": item["text"], "data": data,
              "checks": {c: None for c in CHECKS}, "edge": None, "notes": [], "units": 0}
    exp = item["expected"]

    if data.get("error"):
        result["notes"].append(f"error: {data['error']}")
        if item["group"] in ("delivery", "promise") or "records" in exp:
            has_promise = item["group"] == "promise" or "records" in exp
            result["checks"] = {c: (False if (c != "when" or has_promise) else None) for c in CHECKS}
        else:
            result["edge"] = False
        result["seconds"] = time.time() - started
        return result

    if item["group"] in ("delivery", "promise") or "records" in exp:
        expected_records = exp["records"] if "records" in exp else [exp]
        got_list = got_records(data)
        if len(got_list) < len(expected_records):
            result["notes"].append(f"expected {len(expected_records)} records, got {len(got_list)}")
        # A date within 3 days is accepted only for "agle hafte" (next week) style sentences.
        tolerance = 3 if "hafte" in item["text"].lower() else 0
        unit_scores = [score_expected_record(e, got_list, tolerance) for e in expected_records]
        result["units"] = len(unit_scores)
        result["unit_scores"] = unit_scores
        for c in CHECKS:
            values = [u[c] for u in unit_scores if u[c] is not None]
            result["checks"][c] = (all(values) if values else None)
    else:
        ok, why = score_edge(exp, data)
        result["edge"] = ok
        result["notes"].extend(why)

    result["seconds"] = time.time() - started
    return result


# ---------- printing ----------

def mark(value):
    return "-" if value is None else ("ok" if value else "FAIL")


def failed_names(r):
    names = [c for c in CHECKS if r["checks"][c] is False]
    if r["edge"] is False:
        names.append("edge")
    return names


def short_line(l):
    return (f"{l.get('product_name')} | {l.get('unit')} | exp={l.get('expected_qty')} rec={l.get('received_qty')} "
            f"dam={l.get('damaged_qty')} short={l.get('shortage_qty')} issue={l.get('issue')} amt={l.get('amount_diff_rs')}")


def short_record(r):
    if r.get("record_type") == "DELIVERY_DISCREPANCY":
        lines = "; ".join(short_line(l) for l in r.get("lines") or []) or "(no lines)"
        return f"DELIVERY {r.get('supplier_name')} :: {lines}"
    if r.get("record_type") == "SUPPLIER_PROMISE":
        return (f"PROMISE {r.get('supplier_name')} | {r.get('promise_type')} | {r.get('product_name')} | "
                f"value={r.get('value')} {r.get('value_type')} unit={r.get('unit')} | {r.get('applies_to')} {r.get('follow_up_date')}")
    return "(no record)"


def summary(results):
    rows = {}
    for c in CHECKS:
        values = []
        for r in results:
            for u in r.get("unit_scores", []):
                if u[c] is not None:
                    values.append(u[c])
            if not r.get("unit_scores") and r["checks"][c] is not None:  # error rows
                values.append(r["checks"][c])
        rows[c] = (sum(values), len(values))
    edge = [r["edge"] for r in results if r["edge"] is not None]
    return rows, (sum(edge), len(edge))


def print_report(results, skipped):
    print()
    print(f"{'id':>3}  {'group':9} {'supplier':9} {'product':8} {'quantity':9} {'type':6} {'when':6} {'edge':6} {'secs':>5}")
    print("-" * 70)
    for r in results:
        print(f"{r['id']:>3}  {r['group']:9} {mark(r['checks']['supplier']):9} {mark(r['checks']['product']):8} "
              f"{mark(r['checks']['quantity']):9} {mark(r['checks']['type']):6} {mark(r['checks']['when']):6} "
              f"{mark(r['edge']):6} {r['seconds']:>5.1f}")
    for item in skipped:
        print(f"{item['id']:>3}  {item['group']:9} skipped: question sentences are not built yet")

    rows, (edge_ok, edge_total) = summary(results)
    print("\nRESULT")
    print("-" * 70)
    for c in CHECKS:
        ok, total = rows[c]
        if total == 0:
            continue
        pct = round(100 * ok / total)
        target = TARGETS.get(c)
        verdict = "" if target is None else ("   target %d%%: reached" % target if pct >= target else "   target %d%%: BELOW" % target)
        print(f"  {c.capitalize():9} {pct:>3}%  ({ok}/{total} records){verdict}")
    if edge_total:
        print(f"  {'Edge':9} {edge_ok}/{edge_total} questions asked correctly (sentences 27, 28, 30)")

    worst = sorted([r for r in results if failed_names(r)], key=lambda r: (-len(failed_names(r)), r["id"]))[:5]
    if worst:
        print("\nTHE %d WORST SENTENCES (send these to Claude with task 3A-2)" % len(worst))
        print("-" * 70)
        for r in worst:
            print(f"#{r['id']}  \"{r['text']}\"")
            print(f"   failed:   {', '.join(failed_names(r))}")
            for note in r["notes"]:
                print(f"   note:     {note}")
            for rec in got_records(r["data"]):
                print(f"   got:      {short_record(rec)}")
            if r["data"].get("clarification"):
                print(f"   question: {r['data']['clarification']} [{r['data'].get('clarification_reason')}]")
            print(f"   expected: {r['expected_short']}")
            print()


def expected_short(item):
    exp = item["expected"]
    if "records" in exp:
        return " + ".join(short_record(r) for r in exp["records"])
    if item["group"] in ("delivery", "promise"):
        return short_record(exp)
    return json.dumps(exp, ensure_ascii=False)


def write_docs(results, skipped, path):
    rows, (edge_ok, edge_total) = summary(results)
    try:
        from app.config import settings
        model = settings.GROQ_MODEL
    except Exception:
        model = "unknown"
    lines = [f"## Run on {date.today().isoformat()} ({datetime.now().strftime('%H:%M')})", "",
             f"Model: {model}. Sentences scored: {len(results)}. The test sentences pretend today is 2026-11-19.", "",
             "| Measure | Correct | Target |", "|---|---|---|"]
    for c in CHECKS:
        ok, total = rows[c]
        if total:
            target = f"{TARGETS[c]}%" if c in TARGETS else "-"
            lines.append(f"| {c.capitalize()} | {round(100 * ok / total)}% ({ok}/{total}) | {target} |")
    if edge_total:
        lines.append(f"| Edge questions | {edge_ok}/{edge_total} | - |")
    lines += ["", "Sentences with a problem: " + (", ".join(f"#{r['id']} ({', '.join(failed_names(r))})"
                                                     for r in results if failed_names(r)) or "none"), ""]
    if skipped:
        lines.append("Skipped (query sentences, not built yet): " + ", ".join(f"#{i['id']}" for i in skipped))
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    header = "" if path.exists() else "# Accuracy results\n\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    try:
        shown = path.relative_to(ROOT)
    except ValueError:
        shown = path
    print(f"Added today's numbers to {shown}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=str(ROOT / "tests" / "utterances.json"))
    parser.add_argument("--ids", help="comma separated sentence numbers, for example 1,6,13")
    parser.add_argument("--group", choices=["delivery", "promise", "edge", "query"])
    parser.add_argument("--pause", type=float, default=2.0, help="seconds to wait between sentences")
    parser.add_argument("--write-docs", action="store_true", help="add the numbers to docs/results.md")
    args = parser.parse_args()

    items = json.load(open(args.file, encoding="utf-8"))
    if args.ids:
        wanted = {int(x) for x in args.ids.split(",")}
        items = [i for i in items if i["id"] in wanted]
    if args.group:
        items = [i for i in items if i["group"] == args.group]

    to_run = [i for i in items if i["group"] != "query"]
    skipped = [i for i in items if i["group"] == "query"]
    print(f"Running {len(to_run)} sentences. This can take a few minutes.\n")

    results = []
    for n, item in enumerate(to_run, start=1):
        print(f"[{n}/{len(to_run)}] #{item['id']} {item['text']}")
        r = evaluate(item)
        r["expected_short"] = expected_short(item)
        results.append(r)
        time.sleep(args.pause)

    print_report(results, skipped)
    if args.write_docs:
        write_docs(results, skipped, ROOT / "docs" / "results.md")


if __name__ == "__main__":
    main()