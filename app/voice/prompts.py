"""Prompts for turning a shopkeeper's spoken words (Hindi / Hinglish / English)
into the agreed record shapes. The model only reads; Python does the matching
and the checking afterwards (see extract.py).
"""

COMMON_RULES = """You read what an Indian kirana (small grocery) shopkeeper said about a supplier.
The words come from speech-to-text, so they can be Hindi, Hinglish or English, with small spelling mistakes.

HARD RULES
1. Never guess. If the shopkeeper did not say something, that field is null. Do not copy values from the examples.
2. Do not invent suppliers, products, numbers, dates or rupee amounts.
3. Numbers can be spoken in Hindi (do, teen, paanch, das, pachas, sau, hazaar). Convert them to digits.
4. Dates: "aaj" = today, "kal" = yesterday, "parso" = the day before yesterday. Use the date given below as today.
   Write dates as YYYY-MM-DD. If no day is said, event_date is null.
5. If something important is missing or unclear, put ONE short question in "clarification_question"
   (simple Hinglish, under 15 words) and the reason in "clarification_reason". If nothing is missing, both are null.
   clarification_reason is one of: AMBIGUOUS_NUMBER, SUPPLIER_MISSING, PRODUCT_MISSING, ISSUE_UNCLEAR, PROMISE_UNCLEAR, OTHER.
6. If a spoken number could be two different numbers (for example pachas vs pachpan), set that number to null
   and ask which one, naming BOTH options in the question (for example "Maggi 50 carton ya 55 carton?"),
   with clarification_reason AMBIGUOUS_NUMBER. This question comes before any other question.
7. "Same as last time" or "usual rate" is not a value. Leave it null.
8. Reply with ONE JSON object only. No text before or after it, no markdown.
9. Use supplier and product names from the known lists when the speech clearly means one of them.
   Otherwise write the name exactly as spoken. Never write a list name that was not spoken about.
10. Always write supplier_name and product_name in English letters (Roman script), even if the speech has Devanagari.
    For example "शर्मा जी" means Sharma Distributors if that is in the list.
"""

DELIVERY_SCHEMA = """Return exactly this JSON shape:
{
  "supplier_name": string or null,
  "event_date": "YYYY-MM-DD" or null,
  "lines": [
    {
      "product_name": string or null,
      "unit": string or null,            // carton, packet, kg, bag, piece ...
      "expected_qty": number or null,    // what was ordered or written on the bill
      "received_qty": number or null,    // what actually came
      "damaged_qty": number or null,     // only for packs that are physically damaged
      "shortage_qty": number or null,    // only if the shopkeeper said how much is missing
      "issues": [                        // EVERY separate problem with this product, in the order said
        {"type": string, "detail": string or null, "qty": number or null}
      ],
      "amount_diff_rs": number or null,  // rupees too much or too little, only if said
      "note": string or null             // anything else worth keeping
    }
  ],
  "clarification_question": string or null,
  "clarification_reason": string or null
}

DELIVERY RULES
- ONE line per product. Put the numbers for that product once, in that line.
  Use separate lines only for different products.
- "issues" lists EVERY problem the shopkeeper mentioned for that product: one entry per problem, none left out.
  Example: "4 ordered, 2 came, and 1 of them has insects" is TWO problems (MISSING_QTY and QUALITY), so two entries.
  If there is only one problem, the list has one entry. Never merge two problems into one entry.
- For each entry: "type" is the category, "detail" is what the shopkeeper said about it in a few words
  (Roman letters, for example "ghun lag gaya"), "qty" is how many were affected if said, otherwise null.
- Use one of these known categories whenever it fits:
    MISSING_QTY      fewer came than expected
    DAMAGED          packs physically broken, torn, crushed or leaking
    QUALITY          goods themselves are bad: insects or mites (keede, ghun), fungus, bad smell, wet, stale,
                     expired or too close to expiry date
    WRONG_SKU        a different product, brand or size came
    PRICE_MISMATCH   bill price is different from the agreed price
    INVOICE_MISMATCH bill and goods do not match in another way (for example wrong bill total)
- If a problem fits NONE of these, make up a short new category yourself: 1 to 3 English words in CAPITAL
  LETTERS joined by underscores (for example LATE_DELIVERY, WRONG_WEIGHT, MISSING_FREE_ITEM, EXPIRED_STOCK).
  Name what the problem really is. Do not use a known category that does not truly fit. Use OTHER only if you cannot name it.
- The product can be any item, even one that is not in the known list. Write the name as spoken.
- If nothing about a delivery problem was said, "lines" is an empty list and you ask what the problem was.
- The speech may also contain something the supplier promised for later. Ignore that part here, it is handled separately.
"""

DELIVERY_EXAMPLE = """EXAMPLE 1 (the names and numbers are only for the format)
Speech: "Sharma Distributors ne kal Maggi 5 carton bola tha, 4 hi aaye. Surf Excel ke 2 packet phate hue the."
JSON: {"supplier_name": "Sharma Distributors", "event_date": "<yesterday>", "lines": [
 {"product_name": "Maggi", "unit": "carton", "expected_qty": 5, "received_qty": 4, "damaged_qty": null, "shortage_qty": null,
  "issues": [{"type": "MISSING_QTY", "detail": "4 hi aaye", "qty": null}], "amount_diff_rs": null, "note": null},
 {"product_name": "Surf Excel", "unit": "packet", "expected_qty": null, "received_qty": null, "damaged_qty": 2, "shortage_qty": null,
  "issues": [{"type": "DAMAGED", "detail": "phate hue", "qty": 2}], "amount_diff_rs": null, "note": null}],
 "clarification_question": null}

EXAMPLE 2: two problems with the same product, and a new category
Speech: "Kumar ne Tata Salt 10 carton bola tha, 8 aaye, aur 3 carton ka dabba geela tha, delivery bhi 2 din late aayi."
JSON: {"supplier_name": "Kumar", "event_date": null, "lines": [
 {"product_name": "Tata Salt", "unit": "carton", "expected_qty": 10, "received_qty": 8, "damaged_qty": null, "shortage_qty": null,
  "issues": [{"type": "MISSING_QTY", "detail": "8 aaye", "qty": null},
             {"type": "QUALITY", "detail": "dabba geela tha", "qty": 3},
             {"type": "LATE_DELIVERY", "detail": "2 din late", "qty": null}],
  "amount_diff_rs": null, "note": null}],
 "clarification_question": null}
"""

PROMISE_SCHEMA = """Return exactly this JSON shape:
{
  "supplier_name": string or null,
  "event_date": "YYYY-MM-DD" or null,      // the day the promise was made, only if said
  "promise_type": "DISCOUNT" | "REPLACEMENT" | "CREDIT_NOTE" | "FREE_GOODS" | "CREDIT_PERIOD" | "PRICE_LOCK" | "OTHER" or null,
  "product_name": string or null,
  "value": number or null,
  "value_type": "PERCENT" | "AMOUNT_RS" | "QUANTITY" | "DAYS" or null,
  "unit": string or null,                  // carton, packet, kg ... mainly for QUANTITY
  "applies_to": "NEXT_ORDER" | "DATE" | "NONE",
  "follow_up_date": "YYYY-MM-DD" or null,
  "clarification_question": string or null,
  "clarification_reason": string or null
}

PROMISE RULES
- A promise is something the supplier agreed to do later, for example a discount, extra free goods, a replacement,
  a credit note, more days to pay, or a price that will not change.
- applies_to: NEXT_ORDER if the shopkeeper said "agli baar" / "next order"; DATE if a specific date was said
  (put that date in follow_up_date); otherwise NONE.
- If the type of promise is unclear, promise_type is null and you ask.
- The speech may also describe a delivery problem (short, damaged, wrong item). Ignore that part here, it is handled separately.
"""

DELIVERY_EXAMPLE = """EXAMPLE (the names and numbers are only for the format)
Speech: "Sharma Distributors ne kal Maggi 5 carton bola tha, 4 hi aaye. Surf Excel ke 2 packet phate hue the."
JSON: {"supplier_name": "Sharma Distributors", "event_date": "<yesterday>", "lines": [
 {"product_name": "Maggi", "unit": "carton", "expected_qty": 5, "received_qty": 4, "damaged_qty": null, "shortage_qty": null, "issue": "MISSING_QTY", "amount_diff_rs": null, "note": null},
 {"product_name": "Surf Excel", "unit": "packet", "expected_qty": null, "received_qty": null, "damaged_qty": 2, "shortage_qty": null, "issue": "DAMAGED", "amount_diff_rs": null, "note": "phate hue"}],
 "clarification_question": null}
"""

PROMISE_EXAMPLE = """EXAMPLE (the names and numbers are only for the format)
Speech: "Gupta ji ne bola agli baar Tata Salt par 3 rupaye kam rate lagayenge."
JSON: {"supplier_name": "Gupta", "event_date": null, "promise_type": "DISCOUNT", "product_name": "Tata Salt",
 "value": 3, "value_type": "AMOUNT_RS", "unit": null, "applies_to": "NEXT_ORDER", "follow_up_date": null,
 "clarification_question": null}
"""


def _lists_block(suppliers: list[dict], products: list[dict]) -> str:
    sup_parts = []
    for s in suppliers:
        aliases = s.get("aliases") or []
        sup_parts.append(s["name"] + (f" (also called: {', '.join(aliases)})" if aliases else ""))
    sup = "; ".join(sup_parts) or "(none)"
    prod_parts = []
    for p in products:
        aliases = p.get("aliases") or []
        prod_parts.append(p["name"] + (f" (also called: {', '.join(aliases)})" if aliases else ""))
    prod = "; ".join(prod_parts) or "(none)"
    return f"KNOWN SUPPLIERS: {sup}\nKNOWN PRODUCTS: {prod}\n"


def build_system_prompt(record_type: str, suppliers: list[dict], products: list[dict], today: str) -> str:
    """record_type is DELIVERY_DISCREPANCY or SUPPLIER_PROMISE. today is YYYY-MM-DD."""
    if record_type == "DELIVERY_DISCREPANCY":
        task = "TASK: the shopkeeper is describing a problem with a delivery.\n" + DELIVERY_SCHEMA + DELIVERY_EXAMPLE
    elif record_type == "SUPPLIER_PROMISE":
        task = "TASK: the shopkeeper is noting something a supplier promised.\n" + PROMISE_SCHEMA + PROMISE_EXAMPLE
    else:
        raise ValueError(f"Unknown record_type: {record_type}")
    return f"{COMMON_RULES}\nTODAY: {today}\n{_lists_block(suppliers, products)}\n{task}"


def build_user_prompt(transcript: str) -> str:
    return f'Speech: "{transcript}"\nReturn the JSON object now.'