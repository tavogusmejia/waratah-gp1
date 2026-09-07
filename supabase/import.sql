-- ============================================================================
-- GP1-MUR Material Register - first import.
--
-- Run AFTER schema.sql and policies.sql.
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

insert into gp1.register_item
select * from jsonb_populate_recordset(null::gp1.register_item, '[]'::jsonb)
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
