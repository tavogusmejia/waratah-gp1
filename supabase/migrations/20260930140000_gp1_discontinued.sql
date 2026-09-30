-- ============================================================================
-- An item can be approved and no longer exist.
--
-- LUM3.3, LUM4.3 and LUM5.2 are the LedFlex Pro Profile 0209; LUM6.2 and
-- LUM9.2 are the Pro 0409. LedFlex have folded their US catalogue into the
-- group site and added a Product Archive for "previous generation products",
-- and the Pro Profile pages for these codes no longer resolve. The register
-- has no way to say so: it shows the approval and stays silent about the rest,
-- which is the one case worth shouting about.
--
-- DISCONTINUED IS NOT A SUBMITTAL STATUS. Collapsing it into that enum would
-- hide the worst case behind the best-looking pill - an item cannot be both
-- 'approved' and 'discontinued' if there is only one field. It is a separate
-- axis, so it gets its own table, its own badge and its own facet.
--
-- A NEW TABLE, NOT TWO COLUMNS ON item_state. item_state carries the
-- log_item_status trigger, which fires after insert or update and writes a
-- status-log row. A column there would stamp a phantom submittal entry into
-- the audit log every time somebody ticked this box.
--
-- THE ROW'S EXISTENCE IS THE FLAG. No boolean: a discontinued = false row is a
-- row that means nothing, and two ways to say "not discontinued" is one too
-- many. Un-flagging deletes the row, exactly as putting the original picture
-- back already does.
-- ============================================================================

set local search_path = gp1, public;

create table gp1.item_discontinued (
  item_key text primary key,
  note     text not null default '',
  at       timestamptz not null default now(),
  by_email text not null
);

comment on table gp1.item_discontinued is
  'One row per item believed to be out of production. The row IS the flag - '
  'remove it to un-flag. Independent of submittal status: an item can be '
  'approved and discontinued at once, which is the case worth flagging.';

create trigger item_discontinued_stamp
  before insert on gp1.item_discontinued
  for each row execute function gp1.stamp_email();

alter table gp1.item_discontinued enable row level security;

-- NOT anon. The table carries by_email, and anonymous readers get the view.
grant select                 on gp1.item_discontinued to authenticated;
grant insert, update, delete on gp1.item_discontinued to authenticated;
grant all                    on gp1.item_discontinued to service_role;

create policy item_discontinued_read on gp1.item_discontinued for select
  to authenticated using (gp1.role_at_least('viewer'));
create policy item_discontinued_write on gp1.item_discontinued for insert
  to authenticated with check (gp1.role_at_least('admin'));
create policy item_discontinued_edit on gp1.item_discontinued for update
  to authenticated using (gp1.role_at_least('admin'))
  with check (gp1.role_at_least('admin'));
create policy item_discontinued_del on gp1.item_discontinued for delete
  to authenticated using (gp1.role_at_least('admin'));

-- ----------------------------------------------------------------------------
-- What a signed-out visitor sees.
--
-- The red card is for everyone, not just the people with a login - that is the
-- whole point of flagging it. But the table holds an address, so anon reads a
-- view that does not, the same shape item_note_public already uses.
--
-- 'system' is what stamp_email() writes when there is no token, so a row this
-- migration seeds says so plainly rather than borrowing somebody's name.
-- ----------------------------------------------------------------------------
create view gp1.item_discontinued_public with (security_invoker = false) as
  select item_key, note, at,
         case when by_email = 'system' then 'the register build'
              else initcap(split_part(by_email, '@', 1)) end as author
    from gp1.item_discontinued;

grant select on gp1.item_discontinued_public to anon, authenticated;

comment on view gp1.item_discontinued_public is
  'item_discontinued without the address. security_invoker = false, so anon '
  'reads this while the table itself stays closed.';

-- ----------------------------------------------------------------------------
-- Pictures stop leaking addresses while we are here.
--
-- gp1.item_picture grants select to anon with using (true), and it carries
-- by_email - so a signed-out visitor can read the address of whoever replaced
-- each picture. item_state and item_note both sit behind a view for exactly
-- this reason; this was the one table that did not.
--
-- One transaction, so there is no window where the table is revoked and the
-- view does not exist yet. workflow.js must ship with it: loadPictures() now
-- reads the view.
-- ----------------------------------------------------------------------------
create view gp1.item_picture_public with (security_invoker = false) as
  select item_key, url, at from gp1.item_picture;

grant select on gp1.item_picture_public to anon, authenticated;

drop policy if exists item_picture_read on gp1.item_picture;
create policy item_picture_read on gp1.item_picture for select
  to authenticated using (gp1.role_at_least('viewer'));

revoke select on gp1.item_picture from anon;

comment on view gp1.item_picture_public is
  'item_picture without the address. The write path still uses the table.';

-- ----------------------------------------------------------------------------
-- Orphan checks have to see the new table, or a renamed item leaves a flag
-- behind that nothing reports. item_picture was never in this list either, so
-- a replaced picture on a renamed item has been invisible to it all along.
--
-- DROP first: this changes the return type, and `create or replace` cannot.
-- ----------------------------------------------------------------------------
drop function if exists gp1.orphan_item_state(text[]);

create function gp1.orphan_item_state(live text[])
  returns table (item_key text, notes bigint, invoices bigint,
                 status gp1.submittal, picture boolean, discontinued boolean) as $fn$
  select k.item_key,
         (select count(*) from gp1.item_note    n where n.item_key = k.item_key),
         (select count(*) from gp1.item_invoice v where v.item_key = k.item_key),
         (select s.status from gp1.item_state   s where s.item_key = k.item_key),
         exists (select 1 from gp1.item_picture      p where p.item_key = k.item_key),
         exists (select 1 from gp1.item_discontinued d where d.item_key = k.item_key)
    from (
      select item_key from gp1.item_state
      union select item_key from gp1.item_note
      union select item_key from gp1.item_invoice
      union select item_key from gp1.item_picture
      union select item_key from gp1.item_discontinued
    ) k
   where not (k.item_key = any (live))
   order by 1;
$fn$ language sql stable security definer set search_path = gp1, public;

revoke execute on function gp1.orphan_item_state(text[]) from public, anon;
grant  execute on function gp1.orphan_item_state(text[]) to authenticated;

-- ----------------------------------------------------------------------------
-- The five LedFlex profiles.
--
-- The note carries the evidence AND the date it was checked, so a reader in
-- six months can tell judgement from fact. This is not confirmed by LedFlex -
-- it is what their own site said, read on one day.
-- ----------------------------------------------------------------------------
insert into gp1.item_discontinued (item_key, note)
select k, 'LedFlex have folded ledflexusa.com into ledflexgroup.com and added '
       || 'a Product Archive for previous-generation products; the Pro Profile '
       || 'page for this code no longer resolves on the group site. Checked '
       || '30 Sep 2026. Confirm the current equivalent with LedFlex before '
       || 'ordering - the strip and the driver are unaffected, this is the '
       || 'extrusion only.'
  from unnest(array['lum-lum3.3', 'lum-lum4.3', 'lum-lum5.2',
                    'lum-lum6.2', 'lum-lum9.2']) as k
on conflict (item_key) do nothing;
