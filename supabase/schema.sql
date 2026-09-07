-- ============================================================================
-- GP1-MUR Material & Hardware Register - Supabase / PostgreSQL schema
--
-- Written at build time so moving off the Artifact runtime is copy-paste
-- rather than a redesign. The item JSON in the page uses snake_case keys that
-- match these column names 1:1, deliberately, so the import needs no mapping
-- layer to write, test, or get wrong.
--
-- MIGRATION
--   1. In the register, Download JSON. Its `items` array is the payload.
--      (web/data/seed.json already holds it for the first import.)
--   2. Run this file, then policies.sql, then import.sql.
--   3. insert into register_item
--      select * from jsonb_populate_recordset(null::register_item, :payload);
--   4. Put the project URL and anon key in web/assets/config.js. Nothing in
--      the render or edit code changes - that is what the store seam is for.
-- ============================================================================

create type doc_status  as enum ('complete', 'in_progress', 'not_started', 'unknown');
create type appr_status as enum ('not_started', 'submitted', 'approved', 'rejected', 'unknown');
create type proc_status as enum ('not_started', 'quoted', 'ordered', 'delivered', 'installed', 'unknown');

create table register_item (
  -- Identity is the uuid, never the code. code_tag is display data and is NOT
  -- unique in the source: 'Cable' appears 8 times, 'PVC elbows' 4 times, and
  -- bare 1/2/3 restart per sub-category in Millwork and Electrical.
  id               uuid primary key,
  seq              integer     not null,

  discipline_code  text        not null,               -- '01'..'13'
  discipline       text        not null,               -- 'Pool & Water Features'
  sub_category     text        not null default '',

  code_tag         text        not null default '',    -- verbatim from the workbook
  code_new         text,                               -- the short mnemonic scheme, when designed

  item             text        not null,
  location         text        not null default '',
  manufacturer     text        not null default '',
  model            text        not null default '',

  qty              numeric,
  qty_raw          text,                               -- when qty was not a number
  unit             text        not null default '',

  -- The source workbook's 'Spec Ref' column carried two unrelated things.
  drawing_ref      text        not null default '',    -- 'A11-02/03/04', 'GP1-AC-01'
  spec_url         text        not null default '',    -- manufacturer datasheet
  folder_url       text        not null default '',    -- Google Drive folder

  spec_status      doc_status  not null default 'unknown',
  approved         appr_status not null default 'not_started',
  procured         proc_status not null default 'not_started',
  notes            text        not null default '',

  source_sheet     text        not null,
  source_row       integer     not null,

  updated_at       timestamptz not null default now(),
  updated_by       text
);

create index register_item_order_idx on register_item (discipline_code, seq);

-- The register's headline query: what still has no documentation.
create index register_item_undocumented_idx on register_item (discipline_code)
  where spec_url = '' and folder_url = '';

create index register_item_search_idx on register_item
  using gin (to_tsvector('simple',
    coalesce(item, '') || ' ' || coalesce(manufacturer, '') || ' ' ||
    coalesce(model, '') || ' ' || coalesce(code_tag, '') || ' ' ||
    coalesce(location, '')));

create or replace function touch_register_item() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger register_item_touch
  before update on register_item
  for each row execute function touch_register_item();

-- ----------------------------------------------------------------------------
-- Access lives in policies.sql, which is run after this file. Enabling RLS
-- here and granting nothing there is the safe order: a table with RLS on and
-- no policy denies everyone, whereas a table with RLS off is world-writable.
-- ----------------------------------------------------------------------------

alter table register_item enable row level security;

-- ----------------------------------------------------------------------------
-- Documentation coverage, the figure the register leads with.
-- ----------------------------------------------------------------------------

create view register_coverage as
select
  discipline_code,
  discipline,
  count(*)                                                       as items,
  count(*) filter (where spec_url <> '')                         as with_spec,
  count(*) filter (where folder_url <> '')                       as with_folder,
  count(*) filter (where spec_url <> '' or folder_url <> '')     as documented,
  count(*) filter (where spec_url = '' and folder_url = '')      as undocumented
from register_item
group by discipline_code, discipline
order by discipline_code;
