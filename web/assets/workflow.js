/* ==========================================================================
   The workflow layer: sign-in, submittal status, notes, invoices, people.

   Everything here sits ON TOP of the read-only register. register.js knows
   nothing about Supabase; the whole of the connection between them is the
   window.GP1 seam. Delete this file and the register is exactly what it was.

   THREE RULES THIS FILE IS BUILT AROUND

   1. The catalogue is not ours. Items come from data/datasheets.json, which
      is generated from the source folder. We attach to items by `key` - the
      code, e.g. 'd-dh15' - and we never write item data anywhere.

   2. A write is not saved until the database says so. This register has
      already lost a day of typed-in links to a page that showed green on a
      write it never checked. So: every write is awaited, every failure is
      shown in words next to the control that caused it, and nothing reports
      success on the strength of having been attempted.

   3. Absent is a normal state. No config, no network, no session, no role -
      each of those renders a sensible page rather than an error. Anonymous
      readers are the majority of this page's traffic and must never see a
      spinner that does not resolve.

   Written with async/await, unlike register.js, which is deliberately ES5.
   This file is almost entirely sequenced I/O and the .then() version of it
   would be harder to check for the one thing that matters: that every await
   has its error looked at.
   ========================================================================== */

(function () {
  "use strict";

  /* No register to layer onto - it failed to load and has said so already. */
  if (!window.GP1) return;

  var CFG = window.GP1_CONFIG || {};
  var LIB = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js";

  var sb = null;         /* the client, once the library is in */
  var me = null;         /* {email} once signed in */
  var role = null;       /* 'viewer' | 'commenter' | 'admin' | 'super_admin' */
  var approval = {};     /* item_key -> row, mirrored into the register */

  /* Must stay in step with the gp1.role enum, weakest first. */
  var ROLES = ["viewer", "commenter", "admin", "super_admin"];
  var ROLE_WORDS = {
    viewer: "Viewer", commenter: "Commenter",
    admin: "Admin", super_admin: "Super admin"
  };
  var STATUS = ["not_submitted", "submitted", "approved",
                "approved_as_noted", "revise_resubmit", "rejected"];
  var STATUS_WORDS = {
    not_submitted: "Not submitted", submitted: "Submitted",
    approved: "Approved", approved_as_noted: "Approved as noted",
    revise_resubmit: "Revise & resubmit", rejected: "Rejected"
  };

  function can(r) { return !!role && ROLES.indexOf(role) >= ROLES.indexOf(r); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function when(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d)) return "";
    return d.toLocaleDateString(undefined,
      { year: "numeric", month: "short", day: "numeric" });
  }

  /* Who wrote this, short. Full addresses turn a list of six notes into a
     column of noise, and the whole address is one hover away. */
  function who(email) { return String(email || "").split("@")[0] || "someone"; }

  /* ------------------------------------------------------------- plumbing */

  function script(src) {
    return new Promise(function (ok, no) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = ok;
      s.onerror = function () { no(new Error("could not load " + src)); };
      document.head.appendChild(s);
    });
  }

  /* One shape for every failure, so a caller never has to guess whether it
     got a row or a problem. PostgREST reports permission denials as errors
     with codes; the message is what a human needs to see. */
  function fail(e) {
    if (!e) return "";
    if (e.code === "PGRST301" || e.code === "42501") {
      return "You do not have permission to do that.";
    }
    if (e.code === "PGRST106") {
      return "The gp1 schema is not exposed in the project's API settings.";
    }
    return e.message || String(e);
  }

  /* --------------------------------------------------------------- status */

  async function loadApproval() {
    /* The public view: status without the address book. Anonymous readers
       get exactly this and nothing else. */
    var r = await sb.from("item_status_public").select("*");
    if (r.error) {
      if (window.console) console.warn("GP1 status:", fail(r.error));
      return;
    }
    approval = {};
    for (var i = 0; i < r.data.length; i++) {
      approval[r.data[i].item_key] = r.data[i];
    }
    window.GP1.setApproval(approval);
  }

  /* ------------------------------------------------------------------ auth */

  async function readRole() {
    role = null;
    if (!me) return;
    /* Your own row is always readable, whatever your role - that is what
       makes "why can I not edit this" answerable. No row means no rights,
       which is the default for anyone who has merely signed in. */
    var r = await sb.from("register_user").select("role").eq("email", me.email);
    if (r.error) {
      if (window.console) console.warn("GP1 role:", fail(r.error));
      return;
    }
    role = r.data && r.data.length ? r.data[0].role : null;
    if (role) sb.rpc("touch_me").then(function () {}, function () {});
  }

  function authBox() {
    var el = document.getElementById("auth");
    if (!el) return;

    if (!me) {
      el.innerHTML = '<button class="auth-in" type="button">Sign in</button>';
      return;
    }
    el.innerHTML =
      '<details class="auth-me"><summary title="' + esc(me.email) + '">' +
        '<span>' + esc(who(me.email)) + "</span>" +
        '<em>' + esc(role ? ROLE_WORDS[role] : "No access") + "</em>" +
      "</summary><div class=\"auth-menu\">" +
        '<p>' + esc(me.email) + "</p>" +
        (role
          ? ""
          : "<p class=\"auth-warn\">Signed in, but nobody has given you a " +
            "role yet, so you can read the register and nothing more. Ask an " +
            "admin to add you.</p>") +
        (can("admin") ? '<button type="button" data-people="1">Manage people</button>' : "") +
        '<button type="button" data-out="1">Sign out</button>' +
      "</div></details>";
  }

  async function signIn(email, say) {
    var r = await sb.auth.signInWithOtp({
      email: email,
      options: { emailRedirectTo: location.origin + location.pathname }
    });
    if (r.error) { say(fail(r.error), true); return; }
    say("Check " + email + " — the link signs you in. It expires in an hour.");
  }

  function signInPanel() {
    var wrap = document.createElement("div");
    wrap.className = "modal";
    wrap.innerHTML =
      '<div class="modal-in" role="dialog" aria-modal="true" aria-label="Sign in">' +
        "<h3>Sign in</h3>" +
        "<p>Reading the register needs no account. Signing in is what it " +
        "takes to add a note, attach an invoice or move an item's status.</p>" +
        '<form><label for="wf-email">Your email</label>' +
        '<input id="wf-email" type="email" autocomplete="email" required ' +
        'placeholder="you@example.com">' +
        '<div class="modal-f"><button type="button" data-x="1">Cancel</button>' +
        '<button type="submit" class="go">Email me a link</button></div></form>' +
        '<p class="msg" role="status"></p>' +
      "</div>";
    document.body.appendChild(wrap);
    var msg = wrap.querySelector(".msg");
    var input = wrap.querySelector("#wf-email");
    input.focus();

    function say(t, bad) {
      msg.textContent = t;
      msg.className = "msg" + (bad ? " bad" : " ok");
    }
    wrap.addEventListener("click", function (e) {
      if (e.target === wrap || e.target.closest("[data-x]")) wrap.remove();
    });
    wrap.querySelector("form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var b = wrap.querySelector(".go");
      b.disabled = true;
      say("Sending…");
      await signIn(input.value.trim(), say);
      b.disabled = false;
    });
  }

  /* ------------------------------------------------------------ the panel */

  /* Rebuilt every time a sheet opens, because the sheet itself is. Async
     fills guard on `token`: by the time a query returns the reader may have
     closed the sheet or opened a different item, and writing the first
     item's notes into the second item's panel is exactly the class of bug
     this register has been bitten by before. */
  var token = 0;

  function decorate(it, sheet) {
    var body = sheet.querySelector(".sheet-b");
    if (!body) return;
    var mine = ++token;

    var wf = document.createElement("div");
    wf.className = "wf";
    body.appendChild(wf);

    if (!sb) { return; }

    /* A code that names two items cannot carry one item's record. */
    if (it.shared_key) {
      wf.innerHTML = '<p class="wf-block"><b>No status, notes or invoices ' +
        "for this one yet.</b> The code " + esc(it.code) + " is on more than " +
        "one item in the register, so anything saved here would be saved " +
        "against both. Give one of them its own number in the source folder " +
        "and re-extract.</p>";
      return;
    }

    wf.appendChild(statusBlock(it, mine));
    if (can("viewer")) wf.appendChild(notesBlock(it, mine));
    if (can("admin")) wf.appendChild(invoiceBlock(it, mine));
    if (!me) {
      var p = document.createElement("p");
      p.className = "wf-quiet";
      p.innerHTML = 'Notes and invoices are for signed-in people. ' +
        '<button class="linkish" type="button" data-signin="1">Sign in</button>';
      wf.appendChild(p);
    }
  }

  function section(title, extra) {
    var s = document.createElement("section");
    s.className = "wf-sec";
    s.innerHTML = "<h4>" + esc(title) + (extra || "") + "</h4>";
    return s;
  }

  function msgLine(sec) {
    var m = document.createElement("p");
    m.className = "msg";
    m.setAttribute("role", "status");
    sec.appendChild(m);
    return function (t, bad) {
      m.textContent = t || "";
      m.className = "msg" + (t ? (bad ? " bad" : " ok") : "");
    };
  }

  /* ---- status ---- */

  function statusBlock(it, mine) {
    var sec = section("Submittal status");
    var cur = approval[it.key] || { status: "not_submitted", status_note: "" };

    if (!can("admin")) {
      /* Everyone can see where it stands; only an admin moves it. */
      sec.innerHTML +=
        '<p class="wf-read"><span class="st st-' + esc(cur.status) + '">' +
        "<i></i>" + esc(STATUS_WORDS[cur.status] || cur.status) + "</span>" +
        (cur.status_note ? " " + esc(cur.status_note) : "") +
        (cur.decided_at ? ' <em>' + esc(when(cur.decided_at)) + "</em>" : "") +
        "</p>";
      return sec;
    }

    var opts = "";
    for (var i = 0; i < STATUS.length; i++) {
      opts += '<option value="' + STATUS[i] + '"' +
        (STATUS[i] === cur.status ? " selected" : "") + ">" +
        esc(STATUS_WORDS[STATUS[i]]) + "</option>";
    }
    var box = document.createElement("div");
    box.className = "wf-status";
    box.innerHTML =
      '<select aria-label="Submittal status">' + opts + "</select>" +
      '<input type="text" placeholder="Note — what was noted, or why" ' +
      'value="' + esc(cur.status_note || "") + '" aria-label="Status note">';
    sec.appendChild(box);
    var say = msgLine(sec);

    var sel = box.querySelector("select");
    var note = box.querySelector("input");

    /* The select saves on change and the note on blur, rather than behind a
       Save button. A button is how the manufacturer links were lost: typed,
       looked saved, never sent. */
    async function put() {
      if (mine !== token) return;
      say("Saving…");
      var row = { item_key: it.key, status: sel.value, status_note: note.value.trim() };
      var r = await sb.from("item_state").upsert(row, { onConflict: "item_key" })
                      .select("item_key, status, status_note, decided_at");
      if (r.error) { say(fail(r.error), true); return; }
      /* Read back what the database actually holds, not what we sent. */
      var got = r.data && r.data[0];
      if (!got || got.status !== sel.value) {
        say("The database did not take that. Nothing was saved.", true);
        return;
      }
      approval[it.key] = got;
      window.GP1.setApproval(approval);
      say("Saved — " + STATUS_WORDS[got.status] + ".");
    }

    sel.addEventListener("change", put);
    note.addEventListener("blur", function () {
      if ((note.value.trim() || "") !== (cur.status_note || "")) put();
    });
    return sec;
  }

  /* ---- notes ---- */

  function notesBlock(it, mine) {
    var sec = section("Notes");
    var list = document.createElement("ul");
    list.className = "wf-notes";
    list.innerHTML = '<li class="wf-wait">Loading…</li>';
    sec.appendChild(list);

    if (can("commenter")) {
      var form = document.createElement("form");
      form.className = "wf-add";
      form.innerHTML =
        '<textarea rows="2" placeholder="Add a note" aria-label="Add a note"></textarea>' +
        '<button type="submit">Add</button>';
      sec.appendChild(form);
      var say = msgLine(sec);
      form.addEventListener("submit", async function (e) {
        e.preventDefault();
        var ta = form.querySelector("textarea");
        var body = ta.value.trim();
        if (!body) return;
        var b = form.querySelector("button");
        b.disabled = true;
        say("Saving…");
        var r = await sb.from("item_note")
                        .insert({ item_key: it.key, body: body })
                        .select("*");
        b.disabled = false;
        if (r.error) { say(fail(r.error), true); return; }
        ta.value = "";
        say("");
        fillNotes(it, list, mine);
      });
    }

    fillNotes(it, list, mine);
    return sec;
  }

  async function fillNotes(it, list, mine) {
    var r = await sb.from("item_note").select("*")
                    .eq("item_key", it.key).order("at", { ascending: false });
    if (mine !== token) return;
    if (r.error) {
      list.innerHTML = '<li class="wf-bad">' + esc(fail(r.error)) + "</li>";
      return;
    }
    if (!r.data.length) {
      list.innerHTML = '<li class="wf-none">No notes on this one.</li>';
      return;
    }
    var html = "";
    for (var i = 0; i < r.data.length; i++) {
      var n = r.data[i];
      var own = me && n.by_email === me.email;
      html += '<li data-note="' + esc(n.id) + '"><p>' + esc(n.body) + "</p>" +
        '<span class="wf-by" title="' + esc(n.by_email) + '">' +
        esc(who(n.by_email)) + " &middot; " + esc(when(n.at)) +
        (n.edited_at ? " &middot; edited" : "") + "</span>" +
        (own || can("admin")
          ? '<button type="button" class="wf-del" data-del="' + esc(n.id) +
            '" aria-label="Delete note">×</button>'
          : "") +
        "</li>";
    }
    list.innerHTML = html;
    list.onclick = async function (e) {
      var b = e.target.closest("[data-del]");
      if (!b) return;
      b.disabled = true;
      var r2 = await sb.from("item_note").delete().eq("id", b.dataset.del);
      if (r2.error) { b.disabled = false; alert(fail(r2.error)); return; }
      fillNotes(it, list, mine);
    };
  }

  /* ---- invoices ---- */

  function invoiceBlock(it, mine) {
    var sec = section("Invoices", ' <em>admin only</em>');
    var list = document.createElement("ul");
    list.className = "wf-inv";
    list.innerHTML = '<li class="wf-wait">Loading…</li>';
    sec.appendChild(list);

    var form = document.createElement("form");
    form.className = "wf-add wf-inv-add";
    form.innerHTML =
      '<input type="text" name="label" placeholder="Label — Deposit, Final" aria-label="Label">' +
      '<input type="text" name="supplier" placeholder="Supplier" aria-label="Supplier">' +
      '<input type="text" name="invoice_no" placeholder="Invoice no." aria-label="Invoice number">' +
      '<input type="number" name="amount" step="0.01" placeholder="Amount" aria-label="Amount">' +
      '<input type="date" name="dated" aria-label="Date">' +
      '<input type="file" name="file" accept="application/pdf,image/*" aria-label="Invoice file">' +
      '<input type="url" name="drive_url" placeholder="…or paste a Google Drive link" aria-label="Drive link">' +
      '<button type="submit">Attach</button>';
    sec.appendChild(form);
    var say = msgLine(sec);

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = form.elements;
      var file = f.file.files[0];
      var drive = f.drive_url.value.trim();
      if (!file && !drive) { say("Pick a file, or paste a Drive link.", true); return; }
      if (file && drive) { say("One or the other — a file or a link, not both.", true); return; }

      var b = form.querySelector("button");
      b.disabled = true;
      var row = {
        item_key: it.key,
        label: f.label.value.trim(),
        supplier: f.supplier.value.trim(),
        invoice_no: f.invoice_no.value.trim(),
        amount: f.amount.value ? Number(f.amount.value) : null,
        dated: f.dated.value || null,
        drive_url: drive || null,
        storage_path: null,
        filename: file ? file.name : ""
      };

      if (file) {
        say("Uploading…");
        var path = it.key + "/" + safeName(file.name);
        var up = await sb.storage.from("invoices").upload(path, file);
        if (up.error) { b.disabled = false; say(fail(up.error), true); return; }
        row.storage_path = up.data.path;
      }

      say("Saving…");
      var r = await sb.from("item_invoice").insert(row).select("id");
      b.disabled = false;
      if (r.error) {
        /* The file is already in the bucket and the row is not. Say so -
           a silent orphan in storage is worse than a visible one. */
        say(fail(r.error) + (row.storage_path
          ? " The file uploaded but the record did not save; try again."
          : ""), true);
        return;
      }
      form.reset();
      say("");
      fillInvoices(it, list, mine);
    });

    fillInvoices(it, list, mine);
    return sec;
  }

  /* Storage keys are a path grammar, not a filename. A uuid keeps two
     invoices called "invoice.pdf" apart, and the readable tail is what makes
     the bucket browsable in the dashboard. */
  function safeName(n) {
    var id = (crypto && crypto.randomUUID) ? crypto.randomUUID()
                                           : String(Date.now());
    return id + "-" + String(n).replace(/[^A-Za-z0-9._-]+/g, "_").slice(-60);
  }

  function money(v, cur) {
    if (v == null) return "";
    try {
      return new Intl.NumberFormat(undefined,
        { style: "currency", currency: cur || "USD" }).format(v);
    } catch (e) { return String(v); }
  }

  async function fillInvoices(it, list, mine) {
    var r = await sb.from("item_invoice").select("*")
                    .eq("item_key", it.key).order("dated", { ascending: false });
    if (mine !== token) return;
    if (r.error) {
      list.innerHTML = '<li class="wf-bad">' + esc(fail(r.error)) + "</li>";
      return;
    }
    if (!r.data.length) {
      list.innerHTML = '<li class="wf-none">Nothing attached.</li>';
      return;
    }
    var html = "";
    for (var i = 0; i < r.data.length; i++) {
      var v = r.data[i];
      html += '<li><span class="wf-inv-t">' +
        esc(v.label || v.filename || "Invoice") +
        (v.invoice_no ? ' <code>' + esc(v.invoice_no) + "</code>" : "") + "</span>" +
        '<span class="wf-inv-m">' +
          (v.supplier ? esc(v.supplier) + " &middot; " : "") +
          (v.dated ? esc(when(v.dated)) + " &middot; " : "") +
          esc(who(v.by_email)) +
        "</span>" +
        '<span class="wf-inv-a">' + esc(money(v.amount, v.currency)) + "</span>" +
        (v.drive_url
          ? '<a href="' + esc(v.drive_url) + '" target="_blank" rel="noopener">Open</a>'
          : '<button type="button" data-open="' + esc(v.storage_path) + '">Open</button>') +
        '<button type="button" class="wf-del" data-rm="' + esc(v.id) +
        '" data-path="' + esc(v.storage_path || "") + '" aria-label="Remove">×</button>' +
        "</li>";
    }
    list.innerHTML = html;

    list.onclick = async function (e) {
      var o = e.target.closest("[data-open]");
      if (o) {
        o.disabled = true;
        /* Signed, and short-lived. A link that keeps working after it is
           forwarded is not a private invoice. */
        var s = await sb.storage.from("invoices")
                        .createSignedUrl(o.dataset.open, 120);
        o.disabled = false;
        if (s.error) { alert(fail(s.error)); return; }
        window.open(s.data.signedUrl, "_blank", "noopener");
        return;
      }
      var d = e.target.closest("[data-rm]");
      if (!d) return;
      if (!confirm("Remove this invoice? The file goes too.")) return;
      d.disabled = true;
      var r2 = await sb.from("item_invoice").delete().eq("id", d.dataset.rm);
      if (r2.error) { d.disabled = false; alert(fail(r2.error)); return; }
      if (d.dataset.path) await sb.storage.from("invoices").remove([d.dataset.path]);
      fillInvoices(it, list, mine);
    };
  }

  /* ------------------------------------------------------------- people */

  async function peoplePanel() {
    var wrap = document.createElement("div");
    wrap.className = "modal";
    wrap.innerHTML =
      '<div class="modal-in wide" role="dialog" aria-modal="true" aria-label="People">' +
        "<h3>People</h3>" +
        "<p>Anyone can sign in; a role is what lets them change something. " +
        "Nobody can change their own role, and the last super admin cannot " +
        "be removed.</p>" +
        '<ul class="wf-people"><li class="wf-wait">Loading…</li></ul>' +
        '<form class="wf-add wf-people-add">' +
          '<input type="email" name="email" placeholder="name@example.com" required aria-label="Email">' +
          '<input type="text" name="name" placeholder="Name" aria-label="Name">' +
          '<input type="text" name="note" placeholder="Role on the project" aria-label="Note">' +
          '<select name="role" aria-label="Access">' +
            '<option value="viewer">Viewer</option>' +
            '<option value="commenter">Commenter</option>' +
            (can("super_admin")
              ? '<option value="admin">Admin</option>' +
                '<option value="super_admin">Super admin</option>'
              : "") +
          "</select><button type=\"submit\">Add</button>" +
        "</form>" +
        '<p class="msg" role="status"></p>' +
        '<div class="modal-f"><button type="button" data-x="1">Done</button></div>' +
      "</div>";
    document.body.appendChild(wrap);

    var list = wrap.querySelector(".wf-people");
    var msg = wrap.querySelector(".msg");
    function say(t, bad) {
      msg.textContent = t || "";
      msg.className = "msg" + (t ? (bad ? " bad" : " ok") : "");
    }

    wrap.addEventListener("click", function (e) {
      if (e.target === wrap || e.target.closest("[data-x]")) wrap.remove();
    });

    async function fill() {
      var r = await sb.from("register_user").select("*").order("email");
      if (r.error) { list.innerHTML = '<li class="wf-bad">' + esc(fail(r.error)) + "</li>"; return; }
      var html = "";
      for (var i = 0; i < r.data.length; i++) {
        var u = r.data[i];
        /* An admin may manage the people below them; only a super admin may
           touch another admin. The database enforces this - the disabled
           control is just honesty about what will be refused. */
        var mayEdit = can("super_admin") ||
                      ROLES.indexOf(u.role) < ROLES.indexOf("admin");
        var opts = "";
        for (var j = 0; j < ROLES.length; j++) {
          var allowed = can("super_admin") || ROLES.indexOf(ROLES[j]) < ROLES.indexOf("admin");
          if (!allowed && ROLES[j] !== u.role) continue;
          opts += '<option value="' + ROLES[j] + '"' +
            (ROLES[j] === u.role ? " selected" : "") + ">" +
            ROLE_WORDS[ROLES[j]] + "</option>";
        }
        html += "<li>" +
          '<span class="wf-p-n">' + esc(u.name || who(u.email)) +
          '<em>' + esc(u.email) + (u.note ? " · " + esc(u.note) : "") + "</em></span>" +
          '<span class="wf-p-s">' + (u.last_seen_at
            ? "last here " + esc(when(u.last_seen_at))
            : "never signed in") + "</span>" +
          '<select data-role="' + esc(u.email) + '"' + (mayEdit ? "" : " disabled") +
          ">" + opts + "</select>" +
          (mayEdit
            ? '<button type="button" class="wf-del" data-rm="' + esc(u.email) +
              '" aria-label="Remove">×</button>'
            : "") +
          "</li>";
      }
      list.innerHTML = html || '<li class="wf-none">Nobody yet.</li>';
    }

    list.addEventListener("change", async function (e) {
      var s = e.target.closest("[data-role]");
      if (!s) return;
      say("Saving…");
      var r = await sb.from("register_user")
                      .update({ role: s.value }).eq("email", s.dataset.role)
                      .select("email, role");
      if (r.error) { say(fail(r.error), true); fill(); return; }
      if (!r.data || !r.data.length) {
        say("That change was refused. Nothing was saved.", true); fill(); return;
      }
      say("Saved — " + who(s.dataset.role) + " is now " + ROLE_WORDS[r.data[0].role] + ".");
    });

    list.addEventListener("click", async function (e) {
      var b = e.target.closest("[data-rm]");
      if (!b) return;
      if (!confirm("Remove " + b.dataset.rm + "? They keep their account and " +
                   "lose every right on this register.")) return;
      b.disabled = true;
      var r = await sb.from("register_user").delete().eq("email", b.dataset.rm);
      if (r.error) { b.disabled = false; say(fail(r.error), true); return; }
      say("");
      fill();
    });

    wrap.querySelector("form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = e.target.elements;
      var b = e.target.querySelector("button");
      b.disabled = true;
      say("Saving…");
      var r = await sb.from("register_user").insert({
        email: f.email.value.trim().toLowerCase(),
        name: f.name.value.trim(),
        note: f.note.value.trim(),
        role: f.role.value
      }).select("email");
      b.disabled = false;
      if (r.error) { say(fail(r.error), true); return; }
      e.target.reset();
      say("");
      fill();
    });

    fill();
  }

  /* ---------------------------------------------------------------- boot */

  async function boot() {
    if (!CFG.url || !CFG.anonKey) {
      /* The ordinary state before the project is wired up, and a perfectly
         good page. Said once, quietly, for whoever is wiring it. */
      if (window.console) {
        console.info("GP1: no backend configured (web/assets/config.js) — " +
                     "the register is read-only, which is the default.");
      }
      return;
    }

    /* Only fetch the library if it is not already here. Re-fetching would
       replace a copy the page may have loaded itself - self-hosted, pinned,
       or a stand-in under test - with a different one, and the page would
       then be running against something other than what it set up. */
    if (!window.supabase || !window.supabase.createClient) {
      try { await script(LIB); }
      catch (e) {
        if (window.console) console.warn("GP1:", e.message);
        return;
      }
    }

    sb = window.supabase.createClient(CFG.url, CFG.anonKey, {
      db: { schema: "gp1" },
      auth: { persistSession: true, detectSessionInUrl: true }
    });

    var s = await sb.auth.getSession();
    me = s.data && s.data.session ? s.data.session.user : null;
    await readRole();
    authBox();
    loadApproval();

    sb.auth.onAuthStateChange(async function (_evt, session) {
      var was = me && me.email;
      me = session ? session.user : null;
      if ((me && me.email) === was) return;
      await readRole();
      authBox();
      /* A sheet open across a sign-in is showing the wrong set of controls. */
      window.GP1.reopen();
    });
  }

  window.GP1.onSheet = decorate;

  document.addEventListener("click", function (e) {
    if (e.target.closest(".auth-in, [data-signin]")) { signInPanel(); return; }
    if (e.target.closest("[data-out]")) {
      sb.auth.signOut().then(function () { location.reload(); });
      return;
    }
    if (e.target.closest("[data-people]")) {
      var d = e.target.closest("details");
      if (d) d.open = false;
      peoplePanel();
    }
  });

  boot();
})();
