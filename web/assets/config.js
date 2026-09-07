/* ==========================================================================
   GP1-MUR Material Register - deployment configuration.

   This file is committed on purpose. The Supabase anon key is a PUBLIC
   credential: it identifies the project, it does not grant anything. Every
   permission is decided by row level security in supabase/policies.sql -
   anyone may read the register, only an address listed in `register_editor`
   may write to it. Hiding the key would buy nothing and there is no build
   step here that could inject it.

   NEVER put the service_role key in this file. It bypasses RLS entirely.

   Leave the values empty to run the register straight from data/seed.json,
   which is exactly what happens on a first clone and in local preview.
   ========================================================================== */

window.GP1_CONFIG = {
  SUPABASE_URL: "",
  SUPABASE_ANON_KEY: "",

  /* This project's tables live in their own schema, not `public`, because the
     Waratah database is meant to carry other projects later and they would
     otherwise collide. The schema must also be listed under
     Settings -> API -> Exposed schemas, or PostgREST reports PGRST106 and the
     register quietly falls back to the committed seed. */
  SUPABASE_SCHEMA: "gp1",

  /* Where the register reads from before - and instead of - the network.
     It must stay a complete copy of the schedule: the page is required to be
     useful with no backend at all. */
  SEED_URL: "./data/seed.json"
};
