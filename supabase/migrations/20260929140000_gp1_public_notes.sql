-- ============================================================================
-- Notes become readable by anyone with the link.
--
-- The register is shared with trades and consultants who will never have an
-- account, and "confirmed with Pentair that this ships with the CC150
-- cartridge, not the CC100" is exactly what they need. The submittal status
-- is already public; notes join it.
--
-- BE CLEAR ABOUT WHAT THIS WIDENS. After this, a note is world-readable by
-- anyone holding the register's link. A note naming a price, a lead time
-- somebody gave in confidence, or a negotiating position is public. That is
-- the intent, not an oversight - but it is worth the team knowing before they
-- write the next one.
--
-- WHAT IT DOES NOT WIDEN, and this is the point of doing it with a view
-- rather than a policy on the table:
--
--   * No email address is published. The author is a NAME - the roster's if
--     it has one, otherwise the email's local part title-cased, so
--     "dana.ruiz" reads "Dana Ruiz". A register shared on a link should not
--     also hand over the team's address book, which is why
--     gp1.item_status_public exists and why this follows it exactly.
--   * Writing is untouched. Adding a note still needs `commenter`, editing
--     one still means it has to be yours. Those policies are on the table and
--     the table stays closed.
--
-- security_invoker = false is deliberate: the view runs as its owner, which
-- is what lets `anon` read it while gp1.item_note itself grants anon nothing.
-- ============================================================================

set local search_path = gp1, public;

create view gp1.item_note_public with (security_invoker = false) as
  select n.id,
         n.item_key,
         n.body,
         n.at,
         n.edited_at,
         coalesce(nullif(u.name, ''),
                  initcap(replace(replace(split_part(n.by_email, '@', 1),
                                          '.', ' '), '_', ' '))) as author,
         -- Saves the page a second query and the reader an address: it can
         -- still tell which notes are the caller's own, so the edit and
         -- delete controls know when to appear, without by_email ever
         -- leaving the database. Null for an anonymous reader, which reads
         -- as false.
         (n.by_email = nullif(auth.jwt() ->> 'email', '')) as mine
    from gp1.item_note n
    left join gp1.register_user u on u.email = n.by_email;

comment on view gp1.item_note_public is
  'The readable half of item_note: the words, when, and who by name. No email '
  'addresses. This is what anonymous readers get; the table stays closed.';

grant select on gp1.item_note_public to anon, authenticated;
