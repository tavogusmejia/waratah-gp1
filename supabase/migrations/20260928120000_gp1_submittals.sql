-- ============================================================================
-- GP1-MUR datasheet register - sign-in, notes, invoices, submittal status.
--
-- WHAT THIS ADDS AND WHAT IT DELIBERATELY DOES NOT
--
-- The register's 139 items are generated from the source datasheet folder by
-- tools/extract_datasheets.py into web/data/datasheets.json, and that stays
-- the truth: a datasheet's code, title, maker, page count and picture are
-- facts about a PDF on disk, re-derived on every rebuild. Putting them in the
-- database would mean two copies of the same fact and a sync job to keep them
-- honest.
--
-- So nothing here duplicates the catalogue. These tables hold only what
-- PEOPLE add - a note, an invoice, an approval - and they join to the
-- catalogue on `item_key`, which is the `key` field in datasheets.json:
-- slug(group + "-" + code), e.g. 'a-a1', 'l-l-l-l12', 'd-dh15'.
--
-- There is no foreign key to a catalogue table because there is no catalogue
-- table. That is the trade: a note can outlive the item it was written
-- against. Made survivable by gp1.orphan_item_state below, which lists any
-- key no longer in the register so a rebuild can report it rather than lose
-- it silently. This is the same failure that cost a week of manufacturer
-- links in September, and the reason item_key is the CODE and not the
-- filename slug: codes survive renames, filenames do not.
--
-- ACCESS
-- Read: signed in. Unlike gp1.register_item, which is world-readable so the
-- schedule can be shared with trades, none of this is - an invoice carries
-- prices and an approval is a contractual position.
-- Write: on the gp1.register_editor allowlist, which already exists.
-- ============================================================================

set local search_path = gp1, public;

-- The five states you named, plus the one every item starts in. Ordered as a
-- lifecycle, so `order by status` sorts the way a submittal log reads.
create type gp1.submittal as enum (
  'not_submitted',
  'submitted',
  'approved',
  'approved_as_noted',
  'revise_resubmit',
  'rejected'
);

-- ----------------------------------------------------------------------------
-- Where each item stands. One row per item, created when someone first acts
-- on it - an item with no row is 'not_submitted', which is why the page must
-- treat a missing row and a not_submitted row identically.
-- ----------------------------------------------------------------------------
create table gp1.item_state (
  item_key     text primary key,
  status       gp1.submittal not null default 'not_submitted',
  status_note  text          not null default '',   -- the "as noted" of approved_as_noted
  submitted_at timestamptz,                         -- when it last went out
  decided_at   timestamptz,                         -- when it was last ruled on
  updated_at   timestamptz   not null default now(),
  updated_by   text
);

-- Every change, kept. "Approved as noted" and "revise and resubmit" are points
-- in a correspondence, and the question asked three months later is always
-- which revision was approved and by whom - which the current status alone
-- cannot answer. Append-only: no update or delete policy exists for it.
create table gp1.item_status_log (
  id        bigint generated always as identity primary key,
  item_key  text          not null,
  status    gp1.submittal not null,
  note      text          not null default '',
  at        timestamptz   not null default now(),
  by_email  text
);
create index item_status_log_item_idx on gp1.item_status_log (item_key, at desc);

-- ----------------------------------------------------------------------------
-- Notes. Several per item, each attributable, each editable only by whoever
-- wrote it - a register where anyone can rewrite anyone's note is not a record.
-- ----------------------------------------------------------------------------
create table gp1.item_note (
  id         uuid        primary key default gen_random_uuid(),
  item_key   text        not null,
  body       text        not null,
  at         timestamptz not null default now(),
  edited_at  timestamptz,
  by_email   text        not null
);
create index item_note_item_idx on gp1.item_note (item_key, at desc);

-- ----------------------------------------------------------------------------
-- Invoices. Two ways to attach one, because the team is not all in one place:
--
--   storage_path  a file uploaded to the private `invoices` bucket. Reached
--                 through a short-lived signed URL, never a public link.
--   drive_url     a link pasted from Google Drive, for an invoice that already
--                 lives where accounts keep them.
--
-- Exactly one of the two, enforced below. The rest is what someone reconciling
-- a payment needs to see without opening the PDF.
-- ----------------------------------------------------------------------------
create table gp1.item_invoice (
  id            uuid        primary key default gen_random_uuid(),
  item_key      text        not null,
  label         text        not null default '',    -- 'Deposit 50%', 'Final'
  invoice_no    text        not null default '',
  supplier      text        not null default '',
  amount        numeric(14,2),
  currency      text        not null default 'USD',
  dated         date,
  storage_path  text,
  drive_url     text,
  filename      text        not null default '',    -- as uploaded, for display
  at            timestamptz not null default now(),
  by_email      text        not null,
  constraint item_invoice_one_location check (
    (storage_path is not null and drive_url is null) or
    (storage_path is null     and drive_url is not null)
  )
);
create index item_invoice_item_idx on gp1.item_invoice (item_key, dated desc nulls last);

-- ----------------------------------------------------------------------------
-- Stamps. updated_by / by_email come from the JWT, never from the client -
-- the only version a page cannot lie about. Same pattern as
-- gp1.stamp_register_editor in the baseline.
-- ----------------------------------------------------------------------------
create or replace function gp1.stamp_email() returns trigger as $fn$
begin
  new.by_email = coalesce(auth.jwt() ->> 'email', 'system');
  return new;
end;
$fn$ language plpgsql security definer;

create or replace function gp1.touch_item_state() returns trigger as $fn$
begin
  new.updated_at = now();
  new.updated_by = coalesce(auth.jwt() ->> 'email', 'system');
  -- The two dates are derived from the status rather than sent by the page,
  -- so they cannot disagree with it.
  if tg_op = 'INSERT' or new.status is distinct from old.status then
    if new.status = 'submitted' then
      new.submitted_at = now();
      new.decided_at = null;
    elsif new.status <> 'not_submitted' then
      new.decided_at = now();
    else
      new.submitted_at = null;
      new.decided_at = null;
    end if;
  end if;
  return new;
end;
$fn$ language plpgsql security definer;

create trigger item_state_touch
  before insert or update on gp1.item_state
  for each row execute function gp1.touch_item_state();

create trigger item_note_stamp
  before insert on gp1.item_note
  for each row execute function gp1.stamp_email();

create trigger item_invoice_stamp
  before insert on gp1.item_invoice
  for each row execute function gp1.stamp_email();

-- The log writes itself. A page that had to remember to append would
-- eventually forget, and the gap would be invisible.
create or replace function gp1.log_item_status() returns trigger as $fn$
begin
  if tg_op = 'INSERT' or new.status is distinct from old.status
     or new.status_note is distinct from old.status_note then
    insert into gp1.item_status_log (item_key, status, note, by_email)
    values (new.item_key, new.status, new.status_note,
            coalesce(auth.jwt() ->> 'email', 'system'));
  end if;
  return new;
end;
$fn$ language plpgsql security definer;

create trigger item_state_log
  after insert or update on gp1.item_state
  for each row execute function gp1.log_item_status();

-- ----------------------------------------------------------------------------
-- Access. RLS on first, policies after - a table with RLS on and no policy
-- denies everyone; a table with RLS off is world-writable.
-- ----------------------------------------------------------------------------
alter table gp1.item_state      enable row level security;
alter table gp1.item_status_log enable row level security;
alter table gp1.item_note       enable row level security;
alter table gp1.item_invoice    enable row level security;

grant usage on schema gp1 to authenticated;
grant select                         on gp1.item_state      to authenticated;
grant insert, update                 on gp1.item_state      to authenticated;
grant select                         on gp1.item_status_log to authenticated;
grant select, insert, update, delete on gp1.item_note       to authenticated;
grant select, insert, delete         on gp1.item_invoice    to authenticated;
grant all on all tables in schema gp1 to service_role;

create or replace function gp1.is_editor() returns boolean as $fn$
  select exists (
    select 1 from gp1.register_editor
     where email = auth.jwt() ->> 'email'
  );
$fn$ language sql stable security definer;

-- Signed in reads; on the allowlist writes. `anon` is granted nothing here on
-- purpose: this is the commercial half of the register.
create policy item_state_read  on gp1.item_state for select to authenticated using (true);
create policy item_state_write on gp1.item_state for insert to authenticated
  with check (gp1.is_editor());
create policy item_state_edit  on gp1.item_state for update to authenticated
  using (gp1.is_editor()) with check (gp1.is_editor());

create policy item_log_read on gp1.item_status_log for select to authenticated using (true);
-- No insert policy: only the trigger, which is security definer, writes it.

create policy item_note_read     on gp1.item_note for select to authenticated using (true);
create policy item_note_write    on gp1.item_note for insert to authenticated
  with check (gp1.is_editor());
create policy item_note_mine     on gp1.item_note for update to authenticated
  using (by_email = auth.jwt() ->> 'email') with check (by_email = auth.jwt() ->> 'email');
create policy item_note_mine_del on gp1.item_note for delete to authenticated
  using (by_email = auth.jwt() ->> 'email');

create policy item_invoice_read  on gp1.item_invoice for select to authenticated using (true);
create policy item_invoice_write on gp1.item_invoice for insert to authenticated
  with check (gp1.is_editor());
create policy item_invoice_del   on gp1.item_invoice for delete to authenticated
  using (by_email = auth.jwt() ->> 'email');

-- ----------------------------------------------------------------------------
-- The orphan check. Run it after every rebuild: it is the only thing standing
-- between a renamed code and a note nobody can find again.
--
--   select * from gp1.orphan_item_state(array['a-a1', 'b-b3', ...]);
--
-- The page passes the keys it just loaded from datasheets.json; anything with
-- state attached that is not in that list comes back.
-- ----------------------------------------------------------------------------
create or replace function gp1.orphan_item_state(live text[])
  returns table (item_key text, notes bigint, invoices bigint, status gp1.submittal) as $fn$
  select k.item_key,
         (select count(*) from gp1.item_note    n where n.item_key = k.item_key),
         (select count(*) from gp1.item_invoice v where v.item_key = k.item_key),
         (select s.status from gp1.item_state   s where s.item_key = k.item_key)
    from (
      select item_key from gp1.item_state
      union select item_key from gp1.item_note
      union select item_key from gp1.item_invoice
    ) k
   where not (k.item_key = any (live))
   order by 1;
$fn$ language sql stable;

grant execute on function gp1.orphan_item_state(text[]) to authenticated;

-- ----------------------------------------------------------------------------
-- Invoice storage. Private bucket; files are reached with a signed URL that
-- expires, so a leaked link is not a leaked invoice. Path convention is
-- <item_key>/<uuid>-<filename>, which makes an item's files one prefix.
--
-- 20 MB is a generous scanned-PDF ceiling and a cheap guard against someone
-- parking a video in the project's storage quota.
-- ----------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('invoices', 'invoices', false, 20971520,
        array['application/pdf', 'image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do nothing;

create policy invoices_read on storage.objects for select to authenticated
  using (bucket_id = 'invoices');
create policy invoices_write on storage.objects for insert to authenticated
  with check (bucket_id = 'invoices' and gp1.is_editor());
create policy invoices_delete on storage.objects for delete to authenticated
  using (bucket_id = 'invoices' and gp1.is_editor());
