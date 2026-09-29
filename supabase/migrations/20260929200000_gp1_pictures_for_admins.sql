-- ============================================================================
-- Replacing a picture drops from super admin to admin.
--
-- It was set at super admin on the reasoning that this changes what the
-- register shows the world rather than what the team records about an item.
-- True, but it made one person the bottleneck on 74 pictures - and the people
-- who would fix them are the ones already trusted to move an item's submittal
-- status and read its invoices, which are the more consequential powers by
-- some distance.
--
-- A wrong picture is also the most visible, most self-correcting kind of
-- mistake there is: anybody looking at the item can see it is wrong, and
-- putting the extracted one back is one click.
-- ============================================================================

set local search_path = gp1, public;

drop policy if exists item_picture_write on gp1.item_picture;
drop policy if exists item_picture_edit  on gp1.item_picture;
drop policy if exists item_picture_del   on gp1.item_picture;

create policy item_picture_write on gp1.item_picture for insert to authenticated
  with check (gp1.role_at_least('admin'));
create policy item_picture_edit on gp1.item_picture for update to authenticated
  using (gp1.role_at_least('admin')) with check (gp1.role_at_least('admin'));
create policy item_picture_del on gp1.item_picture for delete to authenticated
  using (gp1.role_at_least('admin'));

-- The bucket has to move with the table, or an admin uploads the file and is
-- then refused the row - leaving an orphan in storage and no picture changed.
drop policy if exists item_pictures_write on storage.objects;
drop policy if exists item_pictures_del   on storage.objects;

create policy item_pictures_write on storage.objects for insert to authenticated
  with check (bucket_id = 'item-pictures' and gp1.role_at_least('admin'));
create policy item_pictures_del on storage.objects for delete to authenticated
  using (bucket_id = 'item-pictures' and gp1.role_at_least('admin'));
