/* ==========================================================================
   GP1-MUR Material Register - STORE.

   The seam the original page was built around: everything above this file
   talks to Store and never to a backend. Swapping the Artifact runtime for
   Supabase changed only what is below this comment.

   Two rules this file exists to keep:

     1. SEED FIRST. The register renders from data/seed.json before the
        network is consulted, and stays complete and readable if Supabase is
        unreachable, unconfigured, or slow. A procurement schedule that shows
        a spinner on a site wifi connection is worse than a stale one.

     2. THE ONLY HONEST SIGNAL IS A REJECTED WRITE. Permission is not
        knowable client-side. Do not guess from the session who may edit -
        attempt the write and believe the answer.
   ========================================================================== */

window.Store = (function () {
  "use strict";

  var CFG = window.GP1_CONFIG || {};

  /* Columns the register is allowed to write. Anything else in a patch is
     dropped rather than sent - seq, discipline and the source_* provenance
     columns belong to the extractor, not to a person editing a row. */
  var WRITABLE = [
    "sub_category", "code_tag", "code_new", "item", "location",
    "manufacturer", "model", "qty", "qty_raw", "unit", "drawing_ref",
    "spec_url", "folder_url", "spec_status", "approved", "procured", "notes"
  ];

  var sb = null;              // supabase-js client, once loaded
  var host = null;            // { items, byId, rederive } supplied by app.js
  var listeners = [];
  var dirty = {};             // id -> { field: value } accumulated since last flush
  var saveTimer = null;
  var writeState = "unknown"; // unknown | reader | writer
  var source = "seed";        // seed | supabase
  var user = null;

  function emit() { listeners.forEach(function (f) { try { f(); } catch (e) {} }); }
  function configured() { return !!(CFG.SUPABASE_URL && CFG.SUPABASE_ANON_KEY); }

  function recall(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function remember(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* ---------------------------------------------------------------------
     Loading. Seed always wins the race; Supabase reconciles afterwards.
     --------------------------------------------------------------------- */

  function loadSeed() {
    return fetch(CFG.SEED_URL || "./data/seed.json", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("seed " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.items)) throw new Error("seed has no items");
        return data;
      });
  }

  /* supabase-js is fetched only when there is a project to talk to, so an
     unconfigured deployment makes no third-party request at all. */
  function loadClient() {
    if (sb) return Promise.resolve(sb);
    if (!configured()) return Promise.resolve(null);
    if (window.supabase && window.supabase.createClient) return Promise.resolve(mk());

    return new Promise(function (resolve) {
      var s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js";
      s.onload = function () { resolve(mk()); };
      s.onerror = function () { resolve(null); };
      document.head.appendChild(s);
    });

    function mk() {
      sb = window.supabase.createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
      });
      sb.auth.onAuthStateChange(function (_evt, session) {
        user = session ? session.user : null;
        /* A new session says nothing about permission - only a write does.
           Reset to unknown so the register probes again rather than assuming. */
        if (writeState === "reader" && user) writeState = "unknown";
        emit();
      });
      return sb;
    }
  }

  /* Rows come back as the same snake_case shape the seed uses, because the
     table columns were named to match it 1:1. No mapping layer to get wrong. */
  function fetchRemote() {
    return loadClient().then(function (client) {
      if (!client) return null;
      return client.from("register_item").select("*").order("seq", { ascending: true })
        .then(function (res) {
          if (res.error || !res.data || !res.data.length) return null;
          return res.data;
        });
    }).catch(function () { return null; });
  }

  /* ---------------------------------------------------------------------
     Writing
     --------------------------------------------------------------------- */

  function cleanPatch(fields) {
    var out = {};
    WRITABLE.forEach(function (k) {
      if (Object.prototype.hasOwnProperty.call(fields, k)) out[k] = fields[k];
    });
    return out;
  }

  function isDenied(err) {
    if (!err) return false;
    var code = String(err.code || "");
    /* 42501 insufficient_privilege, PGRST301 no rows returned under RLS. */
    return code === "42501" || code === "PGRST301" || err.status === 401 || err.status === 403;
  }

  return {
    /* app.js hands the store the three things it needs to reach the data it
       does not own. Keeps the store free of any render or DOM knowledge. */
    bind: function (h) { host = h; },

    onChange: function (f) { listeners.push(f); },
    dirtyCount: function () { return Object.keys(dirty).length; },
    writeState: function () { return writeState; },
    source: function () { return source; },
    configured: configured,
    user: function () { return user; },

    /* Editing is offered when there is somewhere to write to and a signed-in
       person, and withdrawn the moment a write is actually refused. */
    canOfferEditing: function () { return configured() && !!user && writeState !== "reader"; },

    setReader: function () { writeState = "reader"; emit(); },
    setWriter: function () { writeState = "writer"; emit(); },

    load: function () {
      return loadSeed();
    },

    /* Called after the first render. Never blocks it. */
    syncFromRemote: function () {
      if (!configured()) return Promise.resolve(false);
      return fetchRemote().then(function (rows) {
        if (!rows) return false;
        source = "supabase";
        emit();
        return rows;
      });
    },

    signIn: function (email) {
      return loadClient().then(function (client) {
        if (!client) return { error: new Error("Supabase is not configured for this deployment.") };
        return client.auth.signInWithOtp({
          email: email,
          options: { emailRedirectTo: location.origin + location.pathname }
        });
      });
    },

    signOut: function () {
      return loadClient().then(function (client) {
        if (!client) return null;
        return client.auth.signOut().then(function () {
          user = null; writeState = "unknown"; emit();
        });
      });
    },

    restoreSession: function () {
      return loadClient().then(function (client) {
        if (!client) return null;
        return client.auth.getSession().then(function (res) {
          user = res && res.data && res.data.session ? res.data.session.user : null;
          emit();
          return user;
        });
      }).catch(function () { return null; });
    },

    restoreRole: function () {
      var r = recall("gp1.role");
      if (r === "reader" || r === "writer") writeState = r;
    },

    patch: function (id, fields) {
      if (!host) return;
      var i = host.byId(id);
      if (i < 0) return;
      var clean = cleanPatch(fields);
      var item = host.items()[i];
      Object.keys(clean).forEach(function (k) { item[k] = clean[k]; });
      dirty[id] = Object.assign(dirty[id] || {}, clean);
      host.rederive();
      emit();
    },

    scheduleFlush: function (ms) {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () { window.Store.flush(); }, ms || 2500);
    },

    /* Unlike the Artifact version this no longer republishes a document, so
       the page does not reload and there is no scroll to restore. */
    flush: function () {
      clearTimeout(saveTimer);
      var ids = Object.keys(dirty);
      if (!ids.length) return Promise.resolve("noop");
      if (!configured()) return Promise.resolve("no_backend");

      return loadClient().then(function (client) {
        if (!client) return "error";

        var pending = ids.map(function (id) {
          return client.from("register_item").update(dirty[id]).eq("id", id).select("id");
        });

        return Promise.all(pending).then(function (results) {
          var denied = null, failed = null, wrote = 0;
          results.forEach(function (res, n) {
            if (res.error) {
              if (isDenied(res.error)) denied = res.error; else failed = res.error;
            } else if (!res.data || !res.data.length) {
              /* RLS filtered the row out silently: the update matched nothing
                 the caller is allowed to see written. Treat as a refusal. */
              denied = denied || { code: "PGRST301" };
            } else {
              wrote++;
              delete dirty[ids[n]];
            }
          });

          if (denied && !wrote) {
            writeState = "reader";
            remember("gp1.role", "reader");
            emit();
            return "read_only";
          }
          if (failed) { emit(); return "error"; }

          writeState = "writer";
          remember("gp1.role", "writer");
          emit();
          return "saved";
        });
      }).catch(function () { return "error"; });
    }
  };
})();
