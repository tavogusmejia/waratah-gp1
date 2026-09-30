-- ============================================================================
-- The commercial guard has to let the server through.
--
-- It refuses a change to `commercial` unless the caller is a super admin,
-- which is right for anybody holding a session - and wrong for anybody
-- holding the service key, who has no JWT at all. `role_at_least` reads the
-- caller's email out of the token, finds none, and answers false. So the
-- guard blocked exactly the caller that is meant to be able to do anything:
-- the SQL editor, a migration, a support script.
--
-- It failed silently, which is the part worth recording. The write was an
-- upsert, the trigger raised, PostgREST reported nothing useful, and the flag
-- simply stayed false - so a user who looked granted was not, and the first
-- symptom was an invoice insert refused several steps later. The test that
-- caught it had itself passed a moment earlier for a second bad reason: a
-- SELECT under row-level security answers 200 with an empty list, and
-- "status is 200" read that as access.
--
-- The rest of the schema already treats a tokenless caller as the server -
-- every stamp function writes `coalesce(auth.jwt() ->> 'email', 'system')`.
-- This now matches: no token means the server, and the server is not subject
-- to a rule about which signed-in people may grant what.
-- ============================================================================

set local search_path = gp1, public;

create or replace function gp1.guard_register_user() returns trigger as $fn$
declare
  supers int;
  caller text := nullif(auth.jwt() ->> 'email', '');
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
  if new.role is distinct from old.role and old.email = caller then
    raise exception 'You cannot change your own role';
  end if;
  -- Only for a caller who actually is somebody. No token is the server.
  if new.commercial is distinct from old.commercial
     and caller is not null
     and not gp1.role_at_least('super_admin') then
    raise exception 'Only a super admin can change commercial access';
  end if;
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

create or replace function gp1.guard_register_user_insert() returns trigger as $fn$
begin
  if new.commercial
     and nullif(auth.jwt() ->> 'email', '') is not null
     and not gp1.role_at_least('super_admin') then
    raise exception 'Only a super admin can grant commercial access';
  end if;
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;
