-- ============================================================================
-- GP1-MUR datasheet register - roles, notes, invoices, submittal status.
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
-- ACCESS: READING IS PUBLIC, WRITING NEEDS A ROLE
--
-- The register stays open to anyone with the link - that is what makes it
-- useful to trades and consultants who will never have an account. Signing in
-- is what it takes to CHANGE something.
--
--                            public  viewer  commenter  admin  super_admin
--   items, datasheets, pics     Y       Y        Y        Y         Y
--   submittal status            Y       Y        Y        Y         Y
--   who set it, and when        -       Y        Y        Y         Y
--   read notes                  -       Y        Y        Y         Y
--   write notes                 -       -        Y        Y         Y
--   set status                  -       -        -        Y         Y
--   invoices                    -       -        -        Y         Y
--   manage viewers/commenters   -       -        -        Y         Y
--   manage admins               -       -        -        -         Y
--
-- Two deliberate narrowings of "everything public", both one line to widen if
-- you disagree:
--
--   INVOICES ARE ADMIN-ONLY. They carry your prices and your suppliers'
--   terms. A public register that also publishes what you paid is a different
--   decision from a public register, and not one to make by default.
--
--   EMAILS ARE NOT PUBLIC. The status itself is public, but who set it is
--   not, so anonymous readers get gp1.item_status_public rather than the
--   table. Same reasoning the baseline used for register_editor: a shared
--   register should not also publish the team's address book.
--
-- Signing in on its own grants NOTHING. A new account has no row in
-- register_user and is treated exactly like the public until an admin gives
-- it a role.
-- ============================================================================

set local search_path = gp1, public;

-- ----------------------------------------------------------------------------
-- Roles.
--
-- Declared weakest first ON PURPOSE. Postgres compares enum values by
-- declaration order, so `role >= 'admin'` is a valid test and the whole
-- permission model below is expressible without a lookup table of grants.
-- Insert new roles with `alter type ... add value ... before/after` so the
-- ordering keeps meaning what it says.
-- ----------------------------------------------------------------------------
create type gp1.role as enum ('viewer', 'commenter', 'admin', 'super_admin');

create table gp1.register_user (
  email        text        primary key,
  role         gp1.role    not null default 'viewer',
  name         text        not null default '',
  note         text        not null default '',   -- 'Procurement', 'Lighting designer'
  added_at     timestamptz not null default now(),
  added_by     text,
  last_seen_at timestamptz
);

comment on table gp1.register_user is
  'Who may change the register, and how much. An address absent from this '
  'table can still sign in - it simply has no more rights than the public.';

-- ----------------------------------------------------------------------------
-- The two questions every policy below asks.
--
-- security definer so they can read register_user regardless of the caller's
-- own RLS - otherwise the test for "may I read this table" would need to read
-- that table, which is a loop.
-- ----------------------------------------------------------------------------
create or replace function gp1.my_role() returns gp1.role as $fn$
  select role from gp1.register_user where email = auth.jwt() ->> 'email';
$fn$ language sql stable security definer set search_path = gp1, public;

-- Null-safe: a signed-in stranger has no role, and no role is never enough.
create or replace function gp1.role_at_least(want gp1.role) returns boolean as $fn$
  select coalesce(gp1.my_role() >= want, false);
$fn$ language sql stable security definer set search_path = gp1, public;

grant execute on function gp1.my_role()                to authenticated;
grant execute on function gp1.role_at_least(gp1.role)  to authenticated;

-- ----------------------------------------------------------------------------
-- Carry the baseline's allowlist across, then retire it.
--
-- gp1.register_editor was a flat list with one power: edit the 199-item
-- workbook register. Everyone on it becomes an admin here, and the policy
-- that referenced it is repointed, so there is ONE answer to "who can change
-- things" rather than two lists that drift apart.
--
-- Guarded by to_regclass because this migration must also apply to a database
-- where the baseline was never run.
-- ----------------------------------------------------------------------------
do $mig$
begin
  if to_regclass('gp1.register_editor') is not null then
    insert into gp1.register_user (email, role, note)
      select email, 'admin', coalesce(note, '') from gp1.register_editor
      on conflict (email) do nothing;

    drop policy if exists register_item_team_updates on gp1.register_item;
    create policy register_item_team_updates on gp1.register_item for update
      to authenticated
      using (gp1.role_at_least('admin')) with check (gp1.role_at_least('admin'));

    drop policy if exists register_editor_self_read on gp1.register_editor;
    drop table gp1.register_editor;
  end if;
end
$mig$;


-- ----------------------------------------------------------------------------
-- The five states you named, plus the one every item starts in. Ordered as a
-- lifecycle, so `order by status` sorts the way a submittal log reads.
-- ----------------------------------------------------------------------------
create type gp1.submittal as enum (
  'not_submitted',
  'submitted',
  'approved',
  'approved_as_noted',
  'revise_resubmit',
  'rejected'
);

-- Where each item stands. One row per item, created when someone first acts
-- on it - an item with no row is 'not_submitted', which is why the page must
-- treat a missing row and a not_submitted row identically.
create table gp1.item_state (
  item_key     text primary key,
  status       gp1.submittal not null default 'not_submitted',
  status_note  text          not null default '',   -- the "as noted" of approved_as_noted
  submitted_at timestamptz,                         -- when it last went out
  decided_at   timestamptz,                         -- when it was last ruled on
  updated_at   timestamptz   not null default now(),
  updated_by   text
);

-- The public half: the status, without the address book. Deliberately NOT a
-- security_invoker view - it runs as its owner so that anon can read it while
-- item_state itself stays closed.
create view gp1.item_status_public with (security_invoker = false) as
  select item_key, status, status_note, submitted_at, decided_at, updated_at
    from gp1.item_state;

-- Every change, kept. "Approved as noted" and "revise and resubmit" are points
-- in a correspondence, and the question asked three months later is always
-- which revision was approved and by whom - which the current status alone
-- cannot answer. Append-only: no insert, update or delete policy exists, so
-- only the security-definer trigger writes it.
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
-- the only version a page cannot lie about.
-- ----------------------------------------------------------------------------
create or replace function gp1.stamp_email() returns trigger as $fn$
begin
  new.by_email = coalesce(auth.jwt() ->> 'email', 'system');
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

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
$fn$ language plpgsql security definer set search_path = gp1, public;

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
$fn$ language plpgsql security definer set search_path = gp1, public;

create trigger item_state_log
  after insert or update on gp1.item_state
  for each row execute function gp1.log_item_status();

-- ----------------------------------------------------------------------------
-- Two ways to lock yourself out of your own register, both refused here.
--
-- Policies cannot express either: RLS decides whether a row may be written,
-- not whether the TABLE still makes sense afterwards. Removing the last super
-- admin leaves nobody who can appoint one, and self-promotion would make the
-- admin/super_admin line decorative.
-- ----------------------------------------------------------------------------
create or replace function gp1.guard_register_user() returns trigger as $fn$
declare supers int;
begin
  select count(*) into supers from gp1.register_user where role = 'super_admin';

  if tg_op = 'DELETE' then
    if old.role = 'super_admin' and supers <= 1 then
      raise exception 'Cannot remove the last super admin';
    end if;
    return old;
  end if;

  if old.role = 'super_admin' and new.role <> 'super_admin' and supers <= 1 then
    raise exception 'Cannot demote the last super admin';
  end if;
  if new.role is distinct from old.role
     and old.email = auth.jwt() ->> 'email' then
    raise exception 'You cannot change your own role';
  end if;
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

create trigger register_user_guard
  before update or delete on gp1.register_user
  for each row execute function gp1.guard_register_user();

create or replace function gp1.stamp_register_user() returns trigger as $fn$
begin
  new.added_by = coalesce(auth.jwt() ->> 'email', 'system');
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

create trigger register_user_stamp
  before insert on gp1.register_user
  for each row execute function gp1.stamp_register_user();

-- ----------------------------------------------------------------------------
-- Access. RLS on first, policies after - a table with RLS on and no policy
-- denies everyone; a table with RLS off is world-writable.
-- ----------------------------------------------------------------------------
alter table gp1.register_user   enable row level security;
alter table gp1.item_state      enable row level security;
alter table gp1.item_status_log enable row level security;
alter table gp1.item_note       enable row level security;
alter table gp1.item_invoice    enable row level security;

grant usage on schema gp1 to anon, authenticated;

grant select                         on gp1.item_status_public to anon, authenticated;
grant select, insert, update         on gp1.item_state         to authenticated;
grant select                         on gp1.item_status_log    to authenticated;
grant select, insert, update, delete on gp1.item_note          to authenticated;
grant select, insert, update, delete on gp1.item_invoice       to authenticated;
grant select, insert, update, delete on gp1.register_user      to authenticated;
grant all on all tables in schema gp1 to service_role;

-- --- register_user ---------------------------------------------------------
-- You can always see your own row: the page needs it to know what to render,
-- and it is the answer to "why can I not edit this".
create policy register_user_self on gp1.register_user for select to authenticated
  using (email = auth.jwt() ->> 'email');
create policy register_user_admin_read on gp1.register_user for select to authenticated
  using (gp1.role_at_least('admin'));

-- An admin manages the people below them; a super admin manages everyone.
-- Both halves of update are checked: `using` decides which rows may be
-- touched, `with check` decides what they may become - without the second, an
-- admin could promote a viewer to super_admin and then be managed by them.
create policy register_user_write on gp1.register_user for insert to authenticated
  with check (gp1.role_at_least('super_admin')
              or (gp1.role_at_least('admin') and register_user.role < 'admin'::gp1.role));
create policy register_user_edit on gp1.register_user for update to authenticated
  using      (gp1.role_at_least('super_admin')
              or (gp1.role_at_least('admin') and register_user.role < 'admin'::gp1.role))
  with check (gp1.role_at_least('super_admin')
              or (gp1.role_at_least('admin') and register_user.role < 'admin'::gp1.role));
create policy register_user_remove on gp1.register_user for delete to authenticated
  using (gp1.role_at_least('super_admin')
         or (gp1.role_at_least('admin') and register_user.role < 'admin'::gp1.role));

-- --- item_state ------------------------------------------------------------
-- The public reads gp1.item_status_public instead; this carries updated_by.
create policy item_state_read  on gp1.item_state for select to authenticated
  using (gp1.role_at_least('viewer'));
create policy item_state_write on gp1.item_state for insert to authenticated
  with check (gp1.role_at_least('admin'));
create policy item_state_edit  on gp1.item_state for update to authenticated
  using (gp1.role_at_least('admin')) with check (gp1.role_at_least('admin'));

-- --- item_status_log -------------------------------------------------------
create policy item_log_read on gp1.item_status_log for select to authenticated
  using (gp1.role_at_least('viewer'));

-- --- item_note -------------------------------------------------------------
create policy item_note_read     on gp1.item_note for select to authenticated
  using (gp1.role_at_least('viewer'));
create policy item_note_write    on gp1.item_note for insert to authenticated
  with check (gp1.role_at_least('commenter'));
-- Your own words stay yours. An admin may delete a note, but cannot rewrite
-- one and leave someone else's name on it.
create policy item_note_mine     on gp1.item_note for update to authenticated
  using (by_email = auth.jwt() ->> 'email')
  with check (by_email = auth.jwt() ->> 'email');
create policy item_note_mine_del on gp1.item_note for delete to authenticated
  using (by_email = auth.jwt() ->> 'email' or gp1.role_at_least('admin'));

-- --- item_invoice ----------------------------------------------------------
create policy item_invoice_read  on gp1.item_invoice for select to authenticated
  using (gp1.role_at_least('admin'));
create policy item_invoice_write on gp1.item_invoice for insert to authenticated
  with check (gp1.role_at_least('admin'));
create policy item_invoice_edit  on gp1.item_invoice for update to authenticated
  using (gp1.role_at_least('admin')) with check (gp1.role_at_least('admin'));
create policy item_invoice_del   on gp1.item_invoice for delete to authenticated
  using (gp1.role_at_least('admin'));

-- Nobody may update their own register_user row - the policies above see to
-- that, and should. But "added three months ago, never once signed in" is the
-- most useful column on a user-management screen, so last_seen_at is written
-- through a definer function the page calls on sign-in instead.
create or replace function gp1.touch_me() returns void as $fn$
  update gp1.register_user set last_seen_at = now()
   where email = auth.jwt() ->> 'email';
$fn$ language sql volatile security definer set search_path = gp1, public;

revoke execute on function gp1.touch_me() from public, anon;
grant  execute on function gp1.touch_me() to authenticated;

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
$fn$ language sql stable security definer set search_path = gp1, public;

revoke execute on function gp1.orphan_item_state(text[]) from public, anon;
grant  execute on function gp1.orphan_item_state(text[]) to authenticated;

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
  using (bucket_id = 'invoices' and gp1.role_at_least('admin'));
create policy invoices_write on storage.objects for insert to authenticated
  with check (bucket_id = 'invoices' and gp1.role_at_least('admin'));
create policy invoices_delete on storage.objects for delete to authenticated
  using (bucket_id = 'invoices' and gp1.role_at_least('admin'));

-- ----------------------------------------------------------------------------
-- The first super admin. Chicken and egg: the policies above let an admin
-- appoint people, and there is nobody yet. Seed exactly one by hand here,
-- then every other account is made from the page.
-- ----------------------------------------------------------------------------
-- insert into gp1.register_user (email, role, name, note) values
--   ('you@example.com', 'super_admin', 'Gus', 'Project lead')
-- on conflict (email) do update set role = 'super_admin';
