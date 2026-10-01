-- ============================================================================
-- The orphan check could not be run by the server.
--
-- gp1.orphan_item_state() exists to list the notes, statuses, pictures, flags
-- and links left behind by a renamed item. Execute was granted to
-- `authenticated` and revoked from everyone else, which reads as careful and
-- is not: the caller who would actually run it is a scheduled job or a
-- maintenance script holding the service key, and the service key is not
-- `authenticated`. So the function had never once been called since it was
-- written - it answered 403 to the only caller who wanted it.
--
-- NOTE ON WHAT IS NOT HERE. This migration was going to add indexes on
-- item_note, item_status_log and item_invoice, because the backlog said they
-- were unindexed beyond the primary key. They are not: all three were indexed
-- on (item_key, at desc) in the original submittals migration, lines 182, 196
-- and 228. The claim was wrong, and a duplicate index is not a harmless
-- mistake - it costs a write on every insert and misleads the next reader
-- about what the planner is doing. Nothing added.
-- ============================================================================

set local search_path = gp1, public;

grant execute on function gp1.orphan_item_state(text[]) to service_role;
