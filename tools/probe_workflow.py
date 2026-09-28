"""Build web/__probe_workflow.html: the real page, against a fake Supabase.

The workflow layer cannot be checked against the live project from here, and
shipping 600 lines of unexercised UI is how the picture audit ended up with 24
passing tests over a page that was broken - that harness faked the store's
shape WRONGLY (it made DocumentSnapshot.data a property; it is a method), so
the tests agreed with the bug instead of catching it.

So this stub is written against the shapes supabase-js actually returns:

  * a query builder is chainable AND awaitable, and resolves to
    {data, error} - where `data` IS a property, unlike the artifact store;
  * .select() after a write resolves to the rows written, which is what the
    read-back checks in workflow.js depend on;
  * an RLS refusal comes back as a resolved promise with `error` set, never
    as a rejection - code that only catches rejections would miss every
    permission failure, and that is the failure mode that matters here.

The page is generated FROM index.html rather than copied, so it cannot drift.

    python tools/probe_workflow.py
    # then open web/__probe_workflow.html?role=admin

Query string: role=viewer|commenter|admin|super_admin|none|out, open=1.
"""
import io, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "web/index.html"
OUT = REPO / "web/__probe_workflow.html"

STUB = r"""
<script>
/* ---- a stand-in for supabase-js, faithful to the shapes that matter ---- */
(function () {
  var Q = new URLSearchParams(location.search);
  var ROLE = Q.get("role") || "admin";
  var OUT_ = ROLE === "out";
  var EMAIL = "gus@example.com";

  var DB = {
    item_status_public: [
      {item_key:"a-a1", status:"submitted", status_note:"", decided_at:null, updated_at:"2026-09-20T10:00:00Z"},
      {item_key:"a-a2", status:"approved", status_note:"", decided_at:"2026-09-22T10:00:00Z", updated_at:"2026-09-22T10:00:00Z"},
      {item_key:"a-a3", status:"approved_as_noted", status_note:"Finish to be confirmed", decided_at:"2026-09-23T10:00:00Z", updated_at:"2026-09-23T10:00:00Z"},
      {item_key:"a-a4", status:"revise_resubmit", status_note:"Wrong voltage", decided_at:"2026-09-24T10:00:00Z", updated_at:"2026-09-24T10:00:00Z"},
      {item_key:"a-a5", status:"rejected", status_note:"", decided_at:"2026-09-25T10:00:00Z", updated_at:"2026-09-25T10:00:00Z"}
    ],
    item_state: [],
    register_user: [
      {email:EMAIL, role:ROLE === "none" ? null : ROLE, name:"Gus", note:"Project lead",
       last_seen_at:"2026-09-28T08:00:00Z"},
      {email:"lighting@example.com", role:"commenter", name:"Dana Ruiz",
       note:"Lighting designer", last_seen_at:null},
      {email:"trade@example.com", role:"viewer", name:"", note:"Pool contractor",
       last_seen_at:"2026-09-12T08:00:00Z"}
    ].concat(Array.from({length: 120}, function (_, i) {
      /* Enough to page and search through - the screen this was rebuilt for. */
      return {email: "person" + (i + 1) + "@waratahtci.com",
              role: i % 7 === 0 ? "commenter" : "viewer",
              name: "Person " + (i + 1), company: "Waratah TCI",
              note: "", blocked: i % 23 === 0, last_seen_at: null};
    })),
    item_note: [
      {id:"n1", item_key:"a-a1", body:"Confirmed with Pentair that the 150 sq ft body ships with the CC150 cartridge, not the CC100.", at:"2026-09-21T09:30:00Z", edited_at:null, by_email:EMAIL},
      {id:"n2", item_key:"a-a1", body:"Lead time quoted as 6 weeks from order.", at:"2026-09-19T16:02:00Z", edited_at:null, by_email:"lighting@example.com"}
    ],
    register_domain: [
      {domain:"waratahtci.com", role:"commenter", note:"The company", added_by:EMAIL}
    ],
    item_invoice: [
      {id:"v1", item_key:"a-a1", label:"Deposit 50%", invoice_no:"PN-40912",
       supplier:"Pentair", amount:2480.00, currency:"USD", dated:"2026-09-18",
       storage_path:"a-a1/uuid-deposit.pdf", drive_url:null,
       filename:"deposit.pdf", by_email:EMAIL, at:"2026-09-18T10:00:00Z"}
    ]
  };

  function rank(r){ return ["viewer","commenter","admin","super_admin"].indexOf(r); }
  function may(r){ return !OUT_ && ROLE !== "none" && rank(ROLE) >= rank(r); }
  var DENIED = {code:"42501", message:"permission denied"};

  function builder(table) {
    var rows = (DB[table] || []).slice(), filters = [], b;
    var q = null, lo = 0, hi = 1e9, counting = false;
    function resolve() {
      var out = rows;
      filters.forEach(function (f) {
        out = out.filter(function (r) { return String(r[f[0]]) === String(f[1]); });
      });
      if (q) {
        out = out.filter(function (r) {
          return ["email", "name", "company", "note"].some(function (k) {
            return String(r[k] || "").toLowerCase().indexOf(q) > -1;
          });
        });
      }
      var n = out.length;
      out = out.slice(lo, hi + 1);
      /* Reads that RLS would refuse come back as errors, not throws. */
      if (table === "item_invoice" && !may("admin")) return {data:null, error:DENIED};
      if (table === "item_note" && !may("viewer")) return {data:null, error:DENIED};
      if (table === "register_domain" && !may("admin")) return {data:null, error:DENIED};
      return {data: out, error: null, count: counting ? n : null};
    }
    b = {
      select: function (_cols, opts) { counting = !!(opts && opts.count); return b; },
      eq: function (k, v) { filters.push([k, v]); return b; },
      order: function () { return b; },
      range: function (a, z) { lo = a; hi = z; return b; },
      /* Only the shape the page builds: ilike over a few columns. */
      or: function (expr) {
        var m = /ilike\.\*([^*]*)\*/.exec(expr || "");
        q = m ? m[1].toLowerCase() : null;
        return b;
      },
      "in": function (k, vals) {
        rows = rows.filter(function (r) { return vals.indexOf(r[k]) > -1; });
        return b;
      },
      insert: function (row) {
        var need = table === "item_note" ? "commenter" : "admin";
        if (!may(need)) return thenable({data:null, error:DENIED});
        row.id = "new-" + Date.now();
        row.at = new Date().toISOString();
        row.by_email = EMAIL;
        DB[table].push(row);
        return thenable({data:[row], error:null});
      },
      upsert: function (row) {
        if (!may("admin")) return thenable({data:null, error:DENIED});
        row.decided_at = new Date().toISOString();
        var i = DB.item_status_public.findIndex(function (r) { return r.item_key === row.item_key; });
        if (i < 0) DB.item_status_public.push(row); else DB.item_status_public[i] = row;
        return thenable({data:[row], error:null});
      },
      update: function (patch) {
        if (!may("admin")) return thenable({data:null, error:DENIED});
        return thenable({data:[Object.assign({}, rows[0], patch)], error:null});
      },
      "delete": function () {
        if (!may("admin") && table !== "item_note") return thenable({data:null, error:DENIED});
        return b;
      },
      then: function (ok, no) { return Promise.resolve(resolve()).then(ok, no); }
    };
    return b;
  }
  function thenable(v) {
    return { select: function(){ return thenable(v); },
             eq: function(){ return thenable(v); },
             then: function (ok, no) { return Promise.resolve(v).then(ok, no); } };
  }

  window.supabase = {
    createClient: function () {
      return {
        from: builder,
        rpc: function (name) {
          if (name === "people_counts") {
            if (!may("admin")) return Promise.resolve({data:null, error:null});
            var c = {total: DB.register_user.length, blocked: 0, viewer: 0,
                     commenter: 0, admin: 0, super_admin: 0,
                     domains: DB.register_domain.length};
            DB.register_user.forEach(function (u) { if (c[u.role] != null) c[u.role]++; });
            return Promise.resolve({data: c, error: null});
          }
          return Promise.resolve({data:null, error:null});
        },
        auth: {
          getSession: function () {
            return Promise.resolve({data:{session: OUT_ ? null : {user:{email:EMAIL}}}});
          },
          onAuthStateChange: function () { return {data:{subscription:{unsubscribe:function(){}}}}; },
          signInWithOtp: function () { return Promise.resolve({data:{}, error:null}); },
          signOut: function () { return Promise.resolve({error:null}); }
        },
        storage: {
          from: function () {
            return {
              upload: function (p) { return Promise.resolve({data:{path:p}, error:null}); },
              createSignedUrl: function () {
                return Promise.resolve({data:{signedUrl:"about:blank"}, error:null});
              },
              remove: function () { return Promise.resolve({error:null}); }
            };
          }
        }
      };
    }
  };
  window.GP1_CONFIG = {url:"https://stub.example.co", anonKey:"stub"};

  /* Open the first card once the register has rendered, so the panel is on
     screen for a screenshot rather than one click away. */
  /* ?people=1 opens the roster screen, which is otherwise two clicks deep
     inside a <details> menu and so never in a screenshot. */
  if (/[?&]people=1/.test(location.search)) {
    document.addEventListener("gp1:ready", function () {
      setTimeout(function () {
        var d = document.querySelector(".auth-me");
        if (d) d.open = true;
        var b = document.querySelector("[data-people]");
        if (b) b.click();
      }, 500);
    });
  }

  if (/[?&]open=1/.test(location.search)) {
    document.addEventListener("gp1:ready", function () {
      setTimeout(function () {
        var c = document.querySelector(".card");
        if (c) c.click();
        /* The panel hangs off the bottom of a long sheet, so a screenshot of
           the sheet as it opens never shows it. */
        if (/[?&]scroll=1/.test(location.search)) {
          setTimeout(function () {
            var b = document.querySelector(".sheet-b");
            if (b) b.scrollTop = b.scrollHeight;
          }, 500);
        }
      }, 350);
    });
  }
})();
</script>
"""


def main():
    s = io.open(SRC, encoding="utf-8").read()
    # The stub must be installed before config.js and register.js run, and it
    # replaces config.js outright - the real one carries empty strings, which
    # would switch the whole layer off.
    s = s.replace('<script src="./assets/config.js"></script>', STUB.strip())
    s = s.replace("<title>", "<title>PROBE · ")
    if "window.supabase" not in s:
        raise SystemExit("index.html no longer loads config.js where expected")
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(s)
    print("wrote", OUT.relative_to(REPO))
    print("open web/__probe_workflow.html?role=admin&open=1")


if __name__ == "__main__":
    main()
