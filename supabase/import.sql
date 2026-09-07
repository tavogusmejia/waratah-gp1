-- ============================================================================
-- GP1-MUR Material Register - first import.
--
-- Run AFTER the migrations (supabase db push). Data is not in the
-- migrations - web/data/seed.json is the record of it.
--
-- DO NOT RUN THIS FILE DIRECTLY - its payload is the empty array below.
-- Generate the filled version first:
--
--     python supabase/make_import.py     ->  supabase/import-seed.sql
--
-- and run that. The 154 KB payload is not committed, because it would
-- duplicate web/data/seed.json and the two would drift apart.
--
-- The item JSON uses snake_case keys that match the gp1.register_item columns
-- 1:1, deliberately, so this needs no mapping layer to write, test, or get
-- wrong. From psql, instead of pasting:
--
--     psql "$DATABASE_URL" -f supabase/import-seed.sql
--
-- Re-running is safe: the conflict clause makes it an idempotent refresh of
-- the source columns, and it deliberately does NOT touch spec_url, folder_url,
-- approved, procured or notes - those are the columns the team edits in the
-- page, and a re-import must never overwrite that work with a stale seed.
-- ============================================================================

-- The column list is spelled out, and `select *` is deliberately NOT used.
--
-- jsonb_populate_recordset fills every column of the row type, and the seed
-- carries no updated_at / updated_by keys, so it produces NULL for both.
-- `insert ... select *` then supplies those NULLs EXPLICITLY, which overrides
-- the column default - and updated_at is `not null default now()`, so the
-- whole statement fails with 23502. A default only applies to a column the
-- insert does not mention, so the fix is to not mention them.
--
-- updated_at and updated_by belong to the database anyway: the touch trigger
-- maintains one and the stamp trigger takes the other from the JWT. Neither
-- should ever arrive from a client payload.

insert into gp1.register_item (
  id, seq, discipline_code, discipline, sub_category,
  code_tag, code_new, item, location, manufacturer, model,
  qty, qty_raw, unit, drawing_ref, spec_url, folder_url,
  spec_status, approved, procured, notes, source_sheet, source_row
)
select
  id, seq, discipline_code, discipline, sub_category,
  code_tag, code_new, item, location, manufacturer, model,
  qty, qty_raw, unit, drawing_ref, spec_url, folder_url,
  spec_status, approved, procured, notes, source_sheet, source_row
from jsonb_populate_recordset(null::gp1.register_item, '[]'::jsonb)
on conflict (id) do update set
  seq             = excluded.seq,
  discipline_code = excluded.discipline_code,
  discipline      = excluded.discipline,
  sub_category    = excluded.sub_category,
  code_tag        = excluded.code_tag,
  item            = excluded.item,
  location        = excluded.location,
  manufacturer    = excluded.manufacturer,
  model           = excluded.model,
  qty             = excluded.qty,
  qty_raw         = excluded.qty_raw,
  unit            = excluded.unit,
  drawing_ref     = excluded.drawing_ref,
  source_sheet    = excluded.source_sheet,
  source_row      = excluded.source_row;

-- ----------------------------------------------------------------------------
-- Verify. Expected on the 2026-09-07 seed: 199 items, 71 documented, 13 trades.
-- ----------------------------------------------------------------------------

select count(*) as items,
       count(*) filter (where spec_url <> '' or folder_url <> '') as documented,
       count(distinct discipline_code) as trades
from gp1.register_item;

select * from gp1.register_coverage;
