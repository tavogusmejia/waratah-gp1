-- ============================================================================
-- GP1-MUR Material & Hardware Register - Supabase / PostgreSQL schema
--
-- Written at build time so moving off the Artifact runtime is copy-paste
-- rather than a redesign. The item JSON in the page uses snake_case keys that
-- match these column names 1:1, deliberately, so the import needs no mapping
-- layer to write, test, or get wrong.
--
-- ONE DATABASE, SEVERAL PROJECTS
-- Everything here lives in a dedicated `gp1` schema rather than `public`.
-- The Waratah database is meant to carry other projects later, and `public`
-- is where every one of them would otherwise put its own `register_item` or
-- `editor` table and collide. A schema per project keeps the boundary
-- explicit and makes "what belongs to GP1-MUR" answerable with one query.
--
-- The cost is two things that `public` gets for free and this does not:
--   * the schema must be added to Settings -> API -> Exposed schemas, or
--     PostgREST returns PGRST106 and the page sees nothing;
--   * usage and table grants must be issued explicitly. They are, below.
--
-- MIGRATION
--   1. In the register, Download JSON. Its `items` array is the payload.
--      (web/data/seed.json already holds it for the first import.)
--   2. Run this file, then policies.sql, then import-seed.sql.
--   3. Expose the schema: Settings -> API -> Exposed schemas -> add `gp1`.
--   4. Put the project URL and anon key in web/assets/config.js. Nothing in
--      the render or edit code changes - that is what the store seam is for.
-- ============================================================================

create schema if not exists gp1;

-- Everything below is created in gp1, without qualifying every name.
set local search_path = gp1, public;

create type gp1.doc_status  as enum ('complete', 'in_progress', 'not_started', 'unknown');
create type gp1.appr_status as enum ('not_started', 'submitted', 'approved', 'rejected', 'unknown');
create type gp1.proc_status as enum ('not_started', 'quoted', 'ordered', 'delivered', 'installed', 'unknown');

create table gp1.register_item (
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

  spec_status      gp1.doc_status  not null default 'unknown',
  approved         gp1.appr_status not null default 'not_started',
  procured         gp1.proc_status not null default 'not_started',
  notes            text        not null default '',

  source_sheet     text        not null,
  source_row       integer     not null,

  updated_at       timestamptz not null default now(),
  updated_by       text
);

create index register_item_order_idx on gp1.register_item (discipline_code, seq);

-- The register's headline query: what still has no documentation.
create index register_item_undocumented_idx on gp1.register_item (discipline_code)
  where spec_url = '' and folder_url = '';

create index register_item_search_idx on gp1.register_item
  using gin (to_tsvector('simple',
    coalesce(item, '') || ' ' || coalesce(manufacturer, '') || ' ' ||
    coalesce(model, '') || ' ' || coalesce(code_tag, '') || ' ' ||
    coalesce(location, '')));

create or replace function gp1.touch_register_item() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger register_item_touch
  before update on gp1.register_item
  for each row execute function gp1.touch_register_item();

-- ----------------------------------------------------------------------------
-- Access lives in policies.sql, which is run after this file. Enabling RLS
-- here and granting nothing there is the safe order: a table with RLS on and
-- no policy denies everyone, whereas a table with RLS off is world-writable.
-- ----------------------------------------------------------------------------

alter table gp1.register_item enable row level security;

-- ----------------------------------------------------------------------------
-- Documentation coverage, the figure the register leads with.
-- ----------------------------------------------------------------------------

create view gp1.register_coverage as
select
  discipline_code,
  discipline,
  count(*)                                                       as items,
  count(*) filter (where spec_url <> '')                         as with_spec,
  count(*) filter (where folder_url <> '')                       as with_folder,
  count(*) filter (where spec_url <> '' or folder_url <> '')     as documented,
  count(*) filter (where spec_url = '' and folder_url = '')      as undocumented
from gp1.register_item
group by discipline_code, discipline
order by discipline_code;

-- ----------------------------------------------------------------------------
-- Grants. `public` gets these from Supabase's default privileges; a schema
-- created by hand does not, and without them PostgREST reports the table as
-- missing rather than as forbidden - which is a confusing way to spend an
-- afternoon. RLS still decides every row; these only open the door.
-- ----------------------------------------------------------------------------

grant usage on schema gp1 to anon, authenticated, service_role;

grant select                         on gp1.register_item     to anon, authenticated;
grant insert, update, delete         on gp1.register_item     to authenticated;
grant select                         on gp1.register_coverage to anon, authenticated;
grant all                            on all tables in schema gp1 to service_role;

-- Anything added to this schema later inherits the same shape.
alter default privileges in schema gp1
  grant select on tables to anon, authenticated;
alter default privileges in schema gp1
  grant all on tables to service_role;
