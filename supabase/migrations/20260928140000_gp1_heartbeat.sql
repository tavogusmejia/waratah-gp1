-- ============================================================================
-- Keep the project awake, and prove it is working while doing it.
--
-- A Supabase free-tier project pauses after seven days without activity, and a
-- paused project means nobody can approve anything - the register keeps
-- rendering (the catalogue is static) while every status, note and invoice
-- silently fails. That is the worst shape for a failure to take: the page
-- looks fine.
--
-- So a Vercel cron job calls gp1.beat() once a day. Two things make it a
-- VERIFICATION rather than a ping:
--
--   * It WRITES. A read might or might not count as activity depending on how
--     Supabase measures it; an insert is not ambiguous. It also exercises the
--     path that actually matters - if writes are broken, a read-only ping
--     would keep reporting success.
--   * It COUNTS. The reply carries how many items have a status, how many
--     notes and invoices exist and how many people are on the register, so a
--     glance at the endpoint answers "is this thing alive and holding my
--     data" rather than just "did something respond".
--
-- SAFE TO CALL FROM ANYWHERE. beat() is granted to anon because the Vercel
-- function holds nothing but the public anon key - there is no service_role
-- key anywhere in this deployment, and adding one to keep a project awake
-- would be a poor trade. What makes that safe is the rate limit INSIDE the
-- function: a call within an hour of the last one records nothing and just
-- reports. Hammering the endpoint writes no more rows than the cron does.
-- ============================================================================

set local search_path = gp1, public;

create table gp1.heartbeat (
  id     bigint      generated always as identity primary key,
  at     timestamptz not null default now(),
  source text        not null default 'cron'
);

comment on table gp1.heartbeat is
  'One row per keep-alive. Pruned to the last 120, which at one a day is four '
  'months of evidence that the project never went to sleep.';

-- ----------------------------------------------------------------------------
-- The beat. Writes at most once an hour; always reports.
-- ----------------------------------------------------------------------------
create or replace function gp1.beat(source text default 'cron')
returns jsonb as $fn$
declare
  last_at timestamptz;
  wrote   boolean := false;
begin
  select max(at) into last_at from gp1.heartbeat;

  if last_at is null or last_at < now() - interval '1 hour' then
    insert into gp1.heartbeat (source)
      values (left(coalesce(nullif(source, ''), 'cron'), 40));
    -- Keep the table from growing without bound. `id <` rather than a date
    -- window so the count is what is bounded, whatever the schedule becomes.
    delete from gp1.heartbeat
     where id <= (select max(id) - 120 from gp1.heartbeat);
    wrote := true;
    select max(at) into last_at from gp1.heartbeat;
  end if;

  return jsonb_build_object(
    'ok',        true,
    'wrote',     wrote,
    'last_beat', last_at,
    'beats',     (select count(*) from gp1.heartbeat),
    'counts',    jsonb_build_object(
                   'with_status', (select count(*) from gp1.item_state),
                   'notes',       (select count(*) from gp1.item_note),
                   'invoices',    (select count(*) from gp1.item_invoice),
                   'people',      (select count(*) from gp1.register_user)
                 )
  );
end;
$fn$ language plpgsql volatile security definer set search_path = gp1, public;

-- ----------------------------------------------------------------------------
-- The same picture without writing anything, for looking at by hand. This is
-- what the endpoint returns to an unauthenticated visitor, so opening the URL
-- in a browser answers "is the keep-alive working" without being a way to
-- drive it.
-- ----------------------------------------------------------------------------
create or replace function gp1.beat_status()
returns jsonb as $fn$
  select jsonb_build_object(
    'ok',          true,
    'last_beat',   (select max(at) from gp1.heartbeat),
    'hours_ago',   round(extract(epoch from
                     now() - coalesce((select max(at) from gp1.heartbeat),
                                      now() - interval '999 hours')) / 3600.0, 1),
    'beats',       (select count(*) from gp1.heartbeat),
    'counts',      jsonb_build_object(
                     'with_status', (select count(*) from gp1.item_state),
                     'notes',       (select count(*) from gp1.item_note),
                     'invoices',    (select count(*) from gp1.item_invoice),
                     'people',      (select count(*) from gp1.register_user)
                   )
  );
$fn$ language sql stable security definer set search_path = gp1, public;

-- The table itself stays closed - the two functions are the whole interface,
-- and they are what is granted.
alter table gp1.heartbeat enable row level security;
grant all on gp1.heartbeat to service_role;

grant execute on function gp1.beat(text)    to anon, authenticated;
grant execute on function gp1.beat_status() to anon, authenticated;

-- Admins can see the history on the register itself, if it is ever worth
-- putting on a page. Nobody else needs it.
create policy heartbeat_admin_read on gp1.heartbeat for select to authenticated
  using (gp1.role_at_least('admin'));
grant select on gp1.heartbeat to authenticated;
