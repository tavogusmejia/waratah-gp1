-- ============================================================================
-- Invoices move off the role ladder onto a flag of their own.
--
-- Everything else in this register is a question of how much somebody may
-- change: a viewer reads, a commenter writes a note, an admin moves a
-- submittal and fixes a picture, a super admin appoints people. Invoices are
-- not a rung on that ladder. They are a different KIND of access - who may
-- see what things cost - and stapling them to "admin" meant the choice was
-- always between letting somebody help with pictures and letting them see
-- every price the project has paid.
--
-- So `commercial` is a flag beside the role, not above or below it. Somebody
-- can be an admin who never sees an invoice, or a commenter who handles all
-- of them, and neither is a special case.
--
-- ONLY A SUPER ADMIN MAY SET IT, and that has to be enforced by a trigger
-- rather than a policy. Row-level security decides whether a ROW may be
-- written, not which COLUMNS - so the existing rule letting an admin manage
-- people below admin would otherwise let any admin tick this box on a viewer,
-- or a viewer they had just created, and read every invoice through them.
--
-- No implicit grant for super admins. They can set the flag on themselves in
-- one click, so refusing them would be theatre - but writing it down means
-- "who can see the prices" is answerable by one query with no exceptions,
-- which is the sort of question that gets asked in a year by somebody who
-- was not here.
-- ============================================================================

set local search_path = gp1, public;

alter table gp1.register_user
  add column commercial boolean not null default false;

comment on column gp1.register_user.commercial is
  'May see, add and remove invoices. Independent of role: an admin without it '
  'never sees a price, a commenter with it handles them all. Only a super '
  'admin may change it (enforced by the register_user_guard trigger).';

-- Preserve exactly who can see invoices today. They were admin-and-above, and
-- the only people at that level are the two super admins - so this changes
-- nobody's access on the day it is applied, which is what makes it safe to
-- apply to a register already in use.
update gp1.register_user
   set commercial = true
 where role = 'super_admin';

create or replace function gp1.is_commercial() returns boolean as $fn$
  select coalesce(
    (select u.commercial from gp1.register_user u
      where u.email = lower(btrim(coalesce(auth.jwt() ->> 'email', '')))),
    false);
$fn$ language sql stable security definer set search_path = gp1, public;

grant execute on function gp1.is_commercial() to authenticated;

-- ----------------------------------------------------------------------------
-- The column guard, folded into the trigger that already refuses the other
-- two ways to break this table.
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
  -- Policies cannot restrict a single column, and an admin may edit the rows
  -- below theirs. Without this, any admin could tick this on somebody and
  -- read every invoice through them.
  if new.commercial is distinct from old.commercial
     and not gp1.role_at_least('super_admin') then
    raise exception 'Only a super admin can change commercial access';
  end if;
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

-- A row created with the flag already set would go round the guard, which
-- only sees updates.
create or replace function gp1.guard_register_user_insert() returns trigger as $fn$
begin
  if new.commercial and not gp1.role_at_least('super_admin') then
    raise exception 'Only a super admin can grant commercial access';
  end if;
  return new;
end;
$fn$ language plpgsql security definer set search_path = gp1, public;

create trigger register_user_guard_insert
  before insert on gp1.register_user
  for each row execute function gp1.guard_register_user_insert();

-- ----------------------------------------------------------------------------
-- Invoices now ask about the flag instead of the rung.
-- ----------------------------------------------------------------------------
drop policy if exists item_invoice_read  on gp1.item_invoice;
drop policy if exists item_invoice_write on gp1.item_invoice;
drop policy if exists item_invoice_edit  on gp1.item_invoice;
drop policy if exists item_invoice_del   on gp1.item_invoice;

create policy item_invoice_read on gp1.item_invoice for select to authenticated
  using (gp1.is_commercial());
create policy item_invoice_write on gp1.item_invoice for insert to authenticated
  with check (gp1.is_commercial());
create policy item_invoice_edit on gp1.item_invoice for update to authenticated
  using (gp1.is_commercial()) with check (gp1.is_commercial());
create policy item_invoice_del on gp1.item_invoice for delete to authenticated
  using (gp1.is_commercial());

-- The bucket moves with the table. An admin allowed the file but refused the
-- row leaves an orphan in storage; allowed the row but refused the file
-- uploads nothing. They have to agree.
drop policy if exists invoices_read   on storage.objects;
drop policy if exists invoices_write  on storage.objects;
drop policy if exists invoices_delete on storage.objects;

create policy invoices_read on storage.objects for select to authenticated
  using (bucket_id = 'invoices' and gp1.is_commercial());
create policy invoices_write on storage.objects for insert to authenticated
  with check (bucket_id = 'invoices' and gp1.is_commercial());
create policy invoices_delete on storage.objects for delete to authenticated
  using (bucket_id = 'invoices' and gp1.is_commercial());
