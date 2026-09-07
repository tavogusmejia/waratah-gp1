-- ============================================================================
-- GP1-MUR Material Register - first import.
--
-- Run AFTER schema.sql and policies.sql.
--
-- The item JSON in web/data/seed.json uses snake_case keys that match the
-- register_item columns 1:1, deliberately, so this needs no mapping layer to
-- write, test, or get wrong.
--
-- HOW TO RUN
--   In the Supabase SQL editor, paste the `items` array from
--   web/data/seed.json in place of the [] below. It is ~160 KB, which the
--   editor handles. From psql instead:
--
--     \set payload `jq -c .items web/data/seed.json`
--     insert into register_item
--     select * from jsonb_populate_recordset(null::register_item, :'payload');
--
-- Re-running is safe: the conflict clause makes it an idempotent refresh of
-- the source columns, and it deliberately does NOT touch spec_url, folder_url,
-- approved, procured or notes - those are the columns the team edits in the
-- page, and a re-import must never overwrite that work with a stale seed.
-- ============================================================================

insert into register_item
select * from jsonb_populate_recordset(null::register_item, '[]'::jsonb)
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
from register_item;

select * from register_coverage;
