-- ============================================================================
-- The roster, built for 300 rather than 6.
--
-- WHAT ACTUALLY CHANGES AT 300
--
-- Not the tables - 300 rows is nothing to Postgres, and search, paging and
-- bulk edits all work through the row-level policies already written, with no
-- new functions to keep in step with them. Authorization stays in exactly one
-- place, which is the whole reason there is no `people()` RPC here.
--
-- What changes is that naming 300 people one at a time stops being work
-- anybody does. So:
--
--   DOMAIN RULES. One row saying "@waratahtci.com is a commenter" covers
--   everyone at the company, present and future, without a roster entry each.
--   For most projects that removes the roster almost entirely: the explicit
--   list goes back to being the handful of people who need MORE than their
--   colleagues, which is the size a hand-maintained list should be.
--
--   BLOCKED. The cost of a domain rule is that it is a floor nobody can sit
--   below - a contractor on the company domain would inherit commenter. So a
--   roster row can say no outright, and that beats every rule.
--
-- HOW A ROLE IS NOW DECIDED
--
--   blocked          -> nothing, whatever else says
--   otherwise        -> the HIGHER of the explicit row and the domain rule
--
-- greatest() ignores NULLs, so a person with no row gets the domain rule, a
-- person on no matching domain gets their row, and someone with both gets
-- whichever grants more.
--
-- ONE SETTING THIS DEPENDS ON, AND IT IS NOT OPTIONAL
--
-- Domain rules hand out rights based on the address someone signed up with.
-- If "Confirm email" is ever turned off in Supabase Auth, anybody could
-- register as someone@waratahtci.com WITHOUT owning that mailbox and inherit
-- the rule. Email confirmation is what makes the address evidence of
-- anything. Leave it on.
-- ============================================================================

set local search_path = gp1, public;

-- ----------------------------------------------------------------------------
-- Addresses are identity here, so they are stored one way only. Postgres
-- compares text exactly: without this, Coree@... and coree@... are two people,
-- one of whom has rights and cannot work out why the other does not.
-- ----------------------------------------------------------------------------
create or replace function gp1.normalise_email() returns trigger as $fn$
begin
  new.email = lower(btrim(new.email));
  return new;
end;
$fn$ language plpgsql;

create trigger register_user_normalise
  before insert or update on gp1.register_user
  for each row execute function gp1.normalise_email();

update gp1.register_user set email = lower(btrim(email))
 where email <> lower(btrim(email));

alter table gp1.register_user
  add column blocked boolean not null default false,
  add column company text   not null default '';

comment on column gp1.register_user.blocked is
  'Overrides everything, including domain rules. For the person on a covered '
  'domain who should not have what the domain grants.';

-- ----------------------------------------------------------------------------
-- Domain rules.
-- ----------------------------------------------------------------------------
create table gp1.register_domain (
  domain   text        primary key,          -- 'waratahtci.com', no @
  role     gp1.role    not null default 'commenter',
  note     text        not null default '',
  added_at timestamptz not null default now(),
  added_by text
);

comment on table gp1.register_domain is
  'Everyone with a confirmed address at this domain gets AT LEAST this role, '
  'with no roster entry. Depends on email confirmation being on.';

create or replace function gp1.normalise_domain() returns trigger as $fn$
begin
  -- Accept what people actually paste: '@waratahtci.com', 'WaratahTCI.com',
  -- even 'someone@waratahtci.com'. Store the bare domain.
  new.domain = lower(btrim(new.domain));
  if position('@' in new.domain) > 0 then
    new.domain = split_part(new.domain, '@', 2);
  end if;
  new.added_by = coalesce(auth.jwt() ->> 'email', 'system');
  if new.domain = '' or position('.' in new.domain) = 0 then
    raise exception 'Not a domain: %', new.domain;
  end if;
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

create trigger register_domain_normalise
  before insert or update on gp1.register_domain
  for each row execute function gp1.normalise_domain();

-- ----------------------------------------------------------------------------
-- Role resolution, replacing the straight lookup.
-- ----------------------------------------------------------------------------
create or replace function gp1.my_role() returns gp1.role as $fn$
  with me as (select lower(btrim(coalesce(auth.jwt() ->> 'email', ''))) as email)
  select case
    when (select u.blocked from gp1.register_user u, me where u.email = me.email)
      then null
    else greatest(
      (select u.role from gp1.register_user u, me where u.email = me.email),
      (select d.role from gp1.register_domain d, me
        where d.domain = split_part(me.email, '@', 2))
    )
  end
  from me;
$fn$ language sql stable security definer set search_path = gp1, public;

-- ----------------------------------------------------------------------------
-- Access. A domain rule grants roles, so changing one is a super-admin act:
-- an admin who could write these could grant themselves a domain they own.
-- ----------------------------------------------------------------------------
alter table gp1.register_domain enable row level security;

grant select, insert, update, delete on gp1.register_domain to authenticated;
grant all on gp1.register_domain to service_role;

create policy register_domain_read on gp1.register_domain for select to authenticated
  using (gp1.role_at_least('admin'));
create policy register_domain_write on gp1.register_domain for insert to authenticated
  with check (gp1.role_at_least('super_admin'));
create policy register_domain_edit on gp1.register_domain for update to authenticated
  using (gp1.role_at_least('super_admin')) with check (gp1.role_at_least('super_admin'));
create policy register_domain_del on gp1.register_domain for delete to authenticated
  using (gp1.role_at_least('super_admin'));

-- ----------------------------------------------------------------------------
-- Blocking is an admin act, but blocking an ADMIN is not - otherwise two
-- admins could lock each other out. The existing register_user policies
-- already scope an admin to rows below admin, and blocked rides along on the
-- same row, so nothing further is needed here. Stated because its absence
-- otherwise looks like an oversight.
--
-- Deliberately NOT indexed. 300 rows is a sequential scan measured in
-- microseconds, and an ILIKE search index (pg_trgm) would be three moving
-- parts to keep for a table smaller than one page of the register. Revisit at
-- 50,000, which this project will not reach.
-- ----------------------------------------------------------------------------

-- A convenience for the people screen: how many of each, in one row, without
-- pulling 300 records to count them in the browser.
create or replace function gp1.people_counts() returns jsonb as $fn$
  select case when gp1.role_at_least('admin') then
    jsonb_build_object(
      'total',       (select count(*) from gp1.register_user),
      'blocked',     (select count(*) from gp1.register_user where blocked),
      'viewer',      (select count(*) from gp1.register_user where role = 'viewer' and not blocked),
      'commenter',   (select count(*) from gp1.register_user where role = 'commenter' and not blocked),
      'admin',       (select count(*) from gp1.register_user where role = 'admin' and not blocked),
      'super_admin', (select count(*) from gp1.register_user where role = 'super_admin' and not blocked),
      'domains',     (select count(*) from gp1.register_domain)
    )
  else null end;
$fn$ language sql stable security definer set search_path = gp1, public;

grant execute on function gp1.people_counts() to authenticated;
