-- Munshi Guard: database tables (task 1B-8)
-- How to run: Supabase dashboard > SQL Editor > New query > paste this whole file > Run.
-- Safe to run again: every statement uses "if not exists" / "or replace".
-- Field names follow docs/record-shapes.md (Appendix B of the Build Guide).

-- 1. Suppliers (the master list the app matches spoken names against)
create table if not exists suppliers (
  id          bigint generated always as identity primary key,
  name        text not null unique,
  aliases     text[] not null default '{}',      -- spoken variants, lower case: sharma, sharma ji
  created_at  timestamptz not null default now()
);

-- 2. Products (the master list of items)
create table if not exists products (
  id            bigint generated always as identity primary key,
  name          text not null unique,
  aliases       text[] not null default '{}',    -- spoken variants, lower case
  default_unit  text,
  created_at    timestamptz not null default now()
);

-- 3. Records: ONE table for both record types.
--    DELIVERY_DISCREPANCY uses "lines" (a list, one item per product).
--    SUPPLIER_PROMISE uses promise_type ... follow_up_date.
create table if not exists records (
  id             bigint generated always as identity primary key,
  record_type    text not null
                 check (record_type in ('DELIVERY_DISCREPANCY', 'SUPPLIER_PROMISE')),
  supplier_id    bigint not null references suppliers (id),
  supplier_name  text not null,
  event_date     date not null default current_date,
  status         text not null default 'DRAFT',
  transcript     text,
  photos         text[] not null default '{}',   -- links to pictures
  summary_text   text,                           -- the WhatsApp message
  confirmed      boolean not null default false, -- true only after the person says Haan
  created_at     timestamptz not null default now(),

  -- delivery only: list of {product_id, product_name, unit, expected_qty, received_qty,
  --                         damaged_qty, shortage_qty, issue, amount_diff_rs, note}
  lines          jsonb,

  -- promise only
  promise_type   text
                 check (promise_type in ('DISCOUNT', 'REPLACEMENT', 'CREDIT_NOTE', 'FREE_GOODS',
                                         'CREDIT_PERIOD', 'PRICE_LOCK', 'OTHER')),
  product_id     bigint references products (id),
  product_name   text,
  value          numeric,
  value_type     text
                 check (value_type in ('PERCENT', 'AMOUNT_RS', 'QUANTITY', 'DAYS')),
  unit           text,
  applies_to     text
                 check (applies_to in ('NEXT_ORDER', 'DATE', 'NONE')),
  follow_up_date date,

  -- each record type may only use its own statuses
  constraint records_status_ok check (
    (record_type = 'DELIVERY_DISCREPANCY'
       and status in ('DRAFT', 'OPEN', 'RESOLVED', 'DISPUTED'))
    or
    (record_type = 'SUPPLIER_PROMISE'
       and status in ('DRAFT', 'OPEN', 'FULFILLED', 'PARTLY_FULFILLED', 'NOT_FULFILLED', 'CANCELLED'))
  ),
  constraint delivery_has_lines check (record_type <> 'DELIVERY_DISCREPANCY' or lines is not null),
  constraint promise_has_type   check (record_type <> 'SUPPLIER_PROMISE' or promise_type is not null)
);

create index if not exists records_supplier_idx on records (supplier_id, created_at desc);
create index if not exists records_status_idx   on records (status);

-- 4. "Pending" = confirmed records that still need action.
--    Person B's GET /api/pending should read from this view so the rule lives in one place.
create or replace view pending_records
  with (security_invoker = true) as
  select *
  from records
  where confirmed = true
    and status in ('OPEN', 'DISPUTED', 'PARTLY_FULFILLED');

-- 5. Security: switch row-level security ON for every table and add no policies.
--    Result: the public (anon) key can read and write NOTHING.
--    Our Python server uses the service key, which bypasses this.
--    So: the browser must NEVER talk to Supabase directly. Only the server does.
alter table suppliers enable row level security;
alter table products  enable row level security;
alter table records   enable row level security;

-- To start over from scratch (deletes all data!), run these three lines, then run this file again:
-- drop view if exists pending_records;
-- drop table if exists records;
-- drop table if exists products, suppliers;
