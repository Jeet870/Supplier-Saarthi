# Record shapes (agreed on 19 Nov 2026)

Rule: if the shopkeeper did not say it, the field is null. Never guess.

## Fields in BOTH record types
id              number     made by the database
record_type     text       DELIVERY_DISCREPANCY or SUPPLIER_PROMISE
supplier_id     number     matched from the supplier list
supplier_name   text       e.g. Sharma Distributors
event_date      date       YYYY-MM-DD, the day it happened
status          text       see the status lists below
transcript      text       the words that were heard
photos          list       links to pictures (can be empty)
summary_text    text       the message that goes to WhatsApp
confirmed       true/false true only after the person says Haan
created_at      timestamp  made by the database

## Extra fields: DELIVERY_DISCREPANCY
lines           list       one item per product, each with:
  product_id      number or null
  product_name    text or null
  unit            text or null    carton, packet, kg ...
  expected_qty    number or null  what was ordered or on the bill
  received_qty    number or null  what actually came
  damaged_qty     number or null
  shortage_qty    number or null  how much is missing
  issue           text            main problem (first in issues)
  issues          list            all problems found for this line, each with:
    type            text          one of predefined issues or custom category
    detail          text or null  shopkeeper's own words
    qty             number or null affected quantity
    custom          true/false    true when category was AI-generated
  amount_diff_rs  number or null  rupees too much or too little
  note            text or null

## Extra fields: SUPPLIER_PROMISE
promise_type    text       DISCOUNT, REPLACEMENT, CREDIT_NOTE, FREE_GOODS,
                           CREDIT_PERIOD, PRICE_LOCK, OTHER
product_id      number or null
product_name    text or null
value           number or null
value_type      text or null   PERCENT, AMOUNT_RS, QUANTITY, DAYS
unit            text or null
applies_to      text       NEXT_ORDER, DATE, NONE
follow_up_date  date or null

## Status lists
Delivery:  DRAFT, OPEN, RESOLVED, DISPUTED
Promise:   DRAFT, OPEN, FULFILLED, PARTLY_FULFILLED, NOT_FULFILLED, CANCELLED
A record starts as DRAFT, becomes OPEN when the person says Haan.
