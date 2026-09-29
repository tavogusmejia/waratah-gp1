-- ============================================================================
-- Replace an item's picture from the register itself.
--
-- The pictures in web/img are extracted from the PDFs at build time, and a
-- fair number of them are the wrong thing or a poor showing of the right
-- thing. Fixing one has meant staging it in the audit artifact, pulling it
-- down with a script, dropping it in tools/images, re-extracting and
-- redeploying - four steps and a person who knows all four. Meanwhile the
-- artifact's own database has been refusing writes for reasons I have not
-- found, so even the first step is not reliable.
--
-- This puts it where the item already is, using the sign-in, the storage and
-- the permissions the register already has and which demonstrably work.
--
-- PUBLIC BY DESIGN, which is the one thing to be deliberate about. The
-- invoices bucket is private and reached through expiring signed URLs,
-- because an invoice carries prices. A picture of a manhole cover is on a
-- register anyone can already open, next to the datasheet it was lifted from.
-- A signed URL would also expire, and an <img> whose src has gone stale is a
-- broken picture on a public page.
--
-- THE FILE IS NOT THE TRUTH. web/data/datasheets.json still is: this is an
-- override the page prefers when there is one, exactly as tools/images/ is at
-- build time. Deleting the row puts the extracted picture back.
-- ============================================================================

set local search_path = gp1, public;

create table gp1.item_picture (
  item_key     text primary key,
  storage_path text not null,
  url          text not null,
  filename     text not null default '',
  bytes        integer,
  at           timestamptz not null default now(),
  by_email     text not null
);

comment on table gp1.item_picture is
  'One replacement picture per item, preferred by the register over the one '
  'extracted from the PDF. Remove the row to fall back to the extracted one.';

create trigger item_picture_stamp
  before insert on gp1.item_picture
  for each row execute function gp1.stamp_email();

alter table gp1.item_picture enable row level security;

grant select                 on gp1.item_picture to anon, authenticated;
grant insert, update, delete on gp1.item_picture to authenticated;
grant all on gp1.item_picture to service_role;

-- Everyone reads: the picture is on a public page, and a viewer who could not
-- read this row would see the old one while everybody else saw the new one.
create policy item_picture_read on gp1.item_picture for select
  using (true);

-- Changing what the register shows the world is a super-admin act. Widening
-- this to admin is one word in each of the three policies below.
create policy item_picture_write on gp1.item_picture for insert to authenticated
  with check (gp1.role_at_least('super_admin'));
create policy item_picture_edit on gp1.item_picture for update to authenticated
  using (gp1.role_at_least('super_admin')) with check (gp1.role_at_least('super_admin'));
create policy item_picture_del on gp1.item_picture for delete to authenticated
  using (gp1.role_at_least('super_admin'));

-- ----------------------------------------------------------------------------
-- The bucket. Public, unlike invoices, for the reasons in the header.
-- 8 MB is a generous phone photograph and a cheap guard against somebody
-- putting a print-resolution TIFF behind a 288px tile.
-- ----------------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('item-pictures', 'item-pictures', true, 8388608,
        array['image/png', 'image/jpeg', 'image/webp', 'image/gif'])
on conflict (id) do update set public = true;

create policy item_pictures_read on storage.objects for select
  using (bucket_id = 'item-pictures');
create policy item_pictures_write on storage.objects for insert to authenticated
  with check (bucket_id = 'item-pictures' and gp1.role_at_least('super_admin'));
create policy item_pictures_del on storage.objects for delete to authenticated
  using (bucket_id = 'item-pictures' and gp1.role_at_least('super_admin'));
