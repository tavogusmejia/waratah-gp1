/* ==========================================================================
   Where the register's workflow layer finds its backend.

   Leave these empty and nothing changes: the register renders exactly as it
   did when it was read-only - no sign-in control, no badges, and not a single
   network call to anywhere. Fill them in and workflow.js wakes up.

   THE ANON KEY BELONGS IN PUBLIC CODE. It is not a password and it is not a
   secret; it identifies the project and nothing more. What decides who may
   read and write is row level security in the database, which is why the
   policies in supabase/migrations matter and this file does not. Anyone can
   read this key off the page, and that is the design.

   What must NEVER go here is the service_role key, which bypasses every
   policy. If a key is ever pasted in that is longer than the anon one or has
   "service_role" in its payload, it is the wrong key.

       Supabase dashboard -> Project Settings -> API
         Project URL   -> url
         anon / public -> anonKey

   One setting is easy to miss: Settings -> API -> Exposed schemas must list
   `gp1`, or every query comes back PGRST106 and the page looks broken for no
   visible reason.
   ========================================================================== */

window.GP1_CONFIG = {
  url: "",
  anonKey: ""
};
