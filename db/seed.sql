-- Munshi Guard: demo data (task 1B-8)
-- How to run: Supabase > SQL Editor > New query > paste > Run (run schema.sql FIRST).
-- Safe to run again. Running it again also RESETS the records to the demo story,
-- which is exactly what the demo reset route (task 4B-2) will do.
-- Names match the 30 test sentences (Appendix A).

-- A. Clear the demo records (suppliers and products are kept and updated below)
truncate table records restart identity;

-- B. Suppliers (4)
insert into suppliers (name, aliases) values
  ('Sharma Distributors', array['sharma', 'sharma ji', 'sharma distributor']),
  ('Gupta Wholesale',     array['gupta', 'gupta ji', 'gupta wholesale']),
  ('Balaji Traders',      array['balaji', 'balaji ji', 'balaji trader']),
  ('Kumar Provisions',    array['kumar', 'kumar ji', 'kumar provision'])
on conflict (name) do update set aliases = excluded.aliases;

-- C. Products (5)
insert into products (name, aliases, default_unit) values
  ('Maggi Noodles 70g',        array['maggi', 'maggi noodles', 'magi'],                          'carton'),
  ('Surf Excel Easy Wash 1kg', array['surf excel', 'surf', 'surf excel easy wash'],              'carton'),
  ('Tata Salt 1kg',            array['tata salt', 'tata namak', 'namak', 'salt'],                'carton'),
  ('Parle-G Biscuit',          array['parle-g', 'parle g', 'parleg', 'parle'],                   'carton'),
  ('Aashirvaad Atta 5kg',      array['aashirvaad atta', 'aashirvaad', 'ashirvad', 'atta'],       'packet')
on conflict (name) do update
  set aliases = excluded.aliases, default_unit = excluded.default_unit;

-- D. The demo story: 7 earlier records (6 still pending, 1 resolved).
--    They are older than the sentences you will speak live, so live records add to them.

-- D1. Sharma: Surf Excel short by 1 carton (open)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at, lines)
select 'DELIVERY_DISCREPANCY', s.id, s.name, date '2026-11-12', 'OPEN',
       'Sharma Distributors ka Surf Excel 6 mein se 5 carton aaye',
       'Sharma Distributors: Surf Excel 6 carton mangaya, 5 aaye. 1 carton kam.',
       true, timestamptz '2026-11-12 10:30:00+05:30',
       jsonb_build_array(jsonb_build_object(
         'product_id', (select id from products where name = 'Surf Excel Easy Wash 1kg'),
         'product_name', 'Surf Excel Easy Wash 1kg', 'unit', 'carton',
         'expected_qty', 6, 'received_qty', 5, 'damaged_qty', null, 'shortage_qty', 1,
         'issue', 'MISSING_QTY', 'amount_diff_rs', null, 'note', null))
from suppliers s where s.name = 'Sharma Distributors';

-- D2. Sharma: promised 15 days credit (open)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at,
                     promise_type, product_id, product_name, value, value_type, unit,
                     applies_to, follow_up_date)
select 'SUPPLIER_PROMISE', s.id, s.name, date '2026-11-14', 'OPEN',
       'Sharma ne 15 din ka udhaar dene ko bola hai',
       'Sharma Distributors ne 15 din ka udhaar dene ka wada kiya.',
       true, timestamptz '2026-11-14 11:00:00+05:30',
       'CREDIT_PERIOD', null::bigint, null::text, 15, 'DAYS', null::text, 'NONE', null::date
from suppliers s where s.name = 'Sharma Distributors';

-- D3. Gupta: wrong item sent, Tata Salt (disputed)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at, lines)
select 'DELIVERY_DISCREPANCY', s.id, s.name, date '2026-11-15', 'DISPUTED',
       'Gupta ji ne Tata Salt ki jagah dusra namak bhej diya',
       'Gupta Wholesale: Tata Salt ki jagah dusra namak aaya.',
       true, timestamptz '2026-11-15 09:45:00+05:30',
       jsonb_build_array(jsonb_build_object(
         'product_id', (select id from products where name = 'Tata Salt 1kg'),
         'product_name', 'Tata Salt 1kg', 'unit', null, 'expected_qty', null,
         'received_qty', null, 'damaged_qty', null, 'shortage_qty', null,
         'issue', 'WRONG_SKU', 'amount_diff_rs', null, 'note', null))
from suppliers s where s.name = 'Gupta Wholesale';

-- D4. Gupta: promised to replace the Tata Salt tomorrow (open, follow-up 20 Nov)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at,
                     promise_type, product_id, product_name, value, value_type, unit,
                     applies_to, follow_up_date)
select 'SUPPLIER_PROMISE', s.id, s.name, date '2026-11-15', 'OPEN',
       'Gupta ji ne kaha jo Tata Salt kam aaya woh kal bhej denge',
       'Gupta Wholesale ne Tata Salt badalne ka wada kiya (20 Nov tak).',
       true, timestamptz '2026-11-15 09:50:00+05:30',
       'REPLACEMENT', (select id from products where name = 'Tata Salt 1kg'), 'Tata Salt 1kg',
       null::numeric, null::text, null::text, 'DATE', date '2026-11-20'
from suppliers s where s.name = 'Gupta Wholesale';

-- D5. Balaji: Parle-G rate Rs 5 too high (resolved)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at, lines)
select 'DELIVERY_DISCREPANCY', s.id, s.name, date '2026-11-10', 'RESOLVED',
       'Balaji ke bill mein Parle-G ka rate 5 rupaye zyada laga hai',
       'Balaji Traders: Parle-G ka rate bill mein Rs 5 zyada tha.',
       true, timestamptz '2026-11-10 12:15:00+05:30',
       jsonb_build_array(jsonb_build_object(
         'product_id', (select id from products where name = 'Parle-G Biscuit'),
         'product_name', 'Parle-G Biscuit', 'unit', null, 'expected_qty', null,
         'received_qty', null, 'damaged_qty', null, 'shortage_qty', null,
         'issue', 'PRICE_MISMATCH', 'amount_diff_rs', 5, 'note', null))
from suppliers s where s.name = 'Balaji Traders';

-- D6. Kumar: promised a Rs 500 credit note (open)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at,
                     promise_type, product_id, product_name, value, value_type, unit,
                     applies_to, follow_up_date)
select 'SUPPLIER_PROMISE', s.id, s.name, date '2026-11-13', 'OPEN',
       'Kumar Provisions ne 500 rupaye ka credit note dene ka bola hai',
       'Kumar Provisions ne Rs 500 ka credit note dene ka wada kiya.',
       true, timestamptz '2026-11-13 16:20:00+05:30',
       'CREDIT_NOTE', null::bigint, null::text, 500, 'AMOUNT_RS', null::text, 'NONE', null::date
from suppliers s where s.name = 'Kumar Provisions';

-- D7. Balaji: 3 cartons of Parle-G damaged (open)
insert into records (record_type, supplier_id, supplier_name, event_date, status, transcript,
                     summary_text, confirmed, created_at, lines)
select 'DELIVERY_DISCREPANCY', s.id, s.name, date '2026-11-18', 'OPEN',
       'Balaji ke Parle-G ke 3 carton damage the',
       'Balaji Traders: Parle-G ke 3 carton damage aaye.',
       true, timestamptz '2026-11-18 10:05:00+05:30',
       jsonb_build_array(jsonb_build_object(
         'product_id', (select id from products where name = 'Parle-G Biscuit'),
         'product_name', 'Parle-G Biscuit', 'unit', 'carton', 'expected_qty', null,
         'received_qty', null, 'damaged_qty', 3, 'shortage_qty', null,
         'issue', 'DAMAGED', 'amount_diff_rs', null, 'note', null))
from suppliers s where s.name = 'Balaji Traders';

-- E. Quick check. Run this last; you should see: suppliers 4, products 5, records 7, pending 6
select (select count(*) from suppliers)       as suppliers,
       (select count(*) from products)        as products,
       (select count(*) from records)         as records,
       (select count(*) from pending_records) as pending;
