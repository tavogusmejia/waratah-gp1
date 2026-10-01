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
  /* Invoices hang off a flag beside the role, so the harness drives the two
     independently: ?money=1 grants it to whatever role is in play. Declared
     HERE, above DB, because DB reads it - `var` hoists the name and not the
     value, so below it every seeded row got `undefined`. */
  var MONEY = /[?&]money=1/.test(location.search);

  var DB = {
    item_status_public: [
      {item_key:"a-a1", status:"submitted", status_note:"", decided_at:null, updated_at:"2026-09-20T10:00:00Z"},
      {item_key:"a-a2", status:"approved", status_note:"", decided_at:"2026-09-22T10:00:00Z", updated_at:"2026-09-22T10:00:00Z"},
      {item_key:"a-a3", status:"approved_as_noted", status_note:"No objection to the equipment as scheduled, subject to the following: the final finish colour is to be confirmed with the architect before any order is placed, the mounting detail is to be coordinated with the structural drawings issued 12 September, and the contractor is to confirm that the unit clears the maintenance access shown on A11-02. Resubmit the coordination drawing for record only.", decided_at:"2026-09-23T10:00:00Z", updated_at:"2026-09-23T10:00:00Z"},
      {item_key:"a-a4", status:"revise_resubmit", status_note:"Wrong voltage", decided_at:"2026-09-24T10:00:00Z", updated_at:"2026-09-24T10:00:00Z"},
      {item_key:"a-a5", status:"rejected", status_note:"", decided_at:"2026-09-25T10:00:00Z", updated_at:"2026-09-25T10:00:00Z"}
    ],
    item_state: [],
    item_note_public: [],
    item_picture: [],
    /* The page reads the VIEW now, not the table - the table carries an
       address and anon no longer sees it. */
    item_picture_public: [],
    item_discontinued: [],
    maker_link: [],
    /* a-a1's build-time link points at Pentair. This overrides it, so the
       sheet footer showing THIS url is the proof that the table wins over
       datasheets.json - which is the whole point of the live link. */
    maker_link_public: [
      {item_key:"a-a1", url:"https://example.com/confirmed-by-hand", at:"2026-10-01T09:00:00Z"}
    ],
    /* a-a1 is the first card, which is the one ?open=1 opens, so every role
       case also exercises the banner. a-a2 is APPROVED, so the card grid
       shows the pairing this feature exists for: approved and gone. */
    item_discontinued_public: [
      {item_key:"a-a1", note:"The manufacturer has moved this to their product archive. Checked 30 Sep 2026.", at:"2026-09-30T09:00:00Z", author:"The register build"},
      {item_key:"a-a2", note:"", at:"2026-09-30T09:00:00Z", author:"Gus"}
    ],
    register_user: [
      {email:EMAIL, role:ROLE === "none" ? null : ROLE, name:"Gus", note:"Project lead",
       commercial:MONEY,
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
      {domain:"waratahtci.com", role:"commenter", company:"Waratah TCI", note:"The company", added_by:EMAIL}
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
    if (table === "item_note_public") {
      DB.item_note_public = DB.item_note.map(function (n) {
        var u = DB.register_user.filter(function (x) { return x.email === n.by_email; })[0];
        var local = String(n.by_email).split("@")[0].replace(/[._]/g, " ");
        return {id: n.id, item_key: n.item_key, body: n.body, at: n.at,
                edited_at: n.edited_at,
                author: (u && u.name) || local.split(" ").map(function (w) {
                  return w ? w.charAt(0).toUpperCase() + w.slice(1) : w;
                }).join(" "),
                mine: !OUT_ && n.by_email === EMAIL};
      });
    }
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
      if (table === "item_invoice" && !MONEY) return {data:null, error:DENIED};
      if (table === "item_note" && !may("viewer")) return {data:null, error:DENIED};
      /* item_note_public is deliberately NOT gated: anyone may read it. */
      if (table === "register_domain" && !may("admin")) return {data:null, error:DENIED};
      /* item_picture is world-readable through its view: it is what the page
         shows everyone. The TABLE is not - it carries by_email. */
      if (table === "item_picture" && !may("viewer")) return {data:null, error:DENIED};
      if (table === "item_discontinued" && !may("viewer")) return {data:null, error:DENIED};
      if (table === "maker_link" && !may("viewer")) return {data:null, error:DENIED};
      /* maker_link_public is not gated either: the register shows these to
         everyone, signed in or not. */
      /* ...and item_discontinued_public, like item_note_public, is not gated:
         the red card is for everyone, signed in or not. */
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
        if (table === "item_invoice") {
          if (!MONEY) return thenable({data:null, error:DENIED});
        } else {
          var need = table === "item_note" ? "commenter" : "admin";
          if (!may(need)) return thenable({data:null, error:DENIED});
        }
        row.id = "new-" + Date.now();
        row.at = new Date().toISOString();
        row.by_email = EMAIL;
        DB[table].push(row);
        return thenable({data:[row], error:null});
      },
      /* Writes land in whatever the page reads back, which is not always the
         table it wrote to: status goes to item_state and is read from
         item_status_public. Hard-wiring one destination here meant a new
         table's write path silently did nothing under the harness. */
      upsert: function (row) {
        if (!may("admin")) return thenable({data:null, error:DENIED});
        var into = table === "item_state" ? "item_status_public"
                 : table === "item_discontinued" ? "item_discontinued_public"
                 : table === "item_picture" ? "item_picture_public"
                 : table === "maker_link" ? "maker_link_public"
                 : table;
        if (into === "item_status_public") row.decided_at = new Date().toISOString();
        if (!row.at) row.at = new Date().toISOString();
        DB[into] = DB[into] || [];
        var i = DB[into].findIndex(function (r) { return r.item_key === row.item_key; });
        if (i < 0) DB[into].push(row); else DB[into][i] = row;
        return thenable({data:[row], error:null});
      },
      update: function (patch) {
        if (!may("admin")) return thenable({data:null, error:DENIED});
        return thenable({data:[Object.assign({}, rows[0], patch)], error:null});
      },
      "delete": function () {
        if (!may("admin") && table !== "item_note") return thenable({data:null, error:DENIED});
        /* It has to really remove the row. The flag IS the row, so a delete
           that quietly kept it would make un-flagging look like it worked and
           leave the card red. */
        var gone = table === "item_discontinued" ? "item_discontinued_public"
                 : table === "item_picture" ? "item_picture_public"
                 : table === "maker_link" ? "maker_link_public" : null;
        if (gone) {
          return { eq: function (k, v) {
                     DB[gone] = (DB[gone] || []).filter(function (r) {
                       return String(r[k]) !== String(v);
                     });
                     return thenable({data:[], error:null});
                   },
                   then: function (ok, no) {
                     return Promise.resolve({data:[], error:null}).then(ok, no);
                   } };
        }
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
              getPublicUrl: function (p) {
                return {data:{publicUrl:"https://stub.example.co/pic/"+p}};
              },
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
