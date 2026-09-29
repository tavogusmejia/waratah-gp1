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

  /* Every panel carries one. Cancel and Save are the considered ways out;
     this is the one for changing your mind, and it has to be somewhere the
     eye already goes - which is the corner, not the bottom row. */
  var MODAL_X = '<button type="button" class="modal-x" data-x="1" ' +
                'aria-label="Close">×</button>';

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
    if (e.code === "weak_password" || (e.message || "").indexOf("Password should") === 0) {
      return "That password is too simple. " + PW_RULE;
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
        '<button type="button" data-pw="1">Set a password</button>' +
        '<button type="button" data-out="1">Sign out</button>' +
      "</div></details>";
  }

  /* The project requires a lower-case letter, an upper-case letter and a
     digit, so promising "at least 8 characters" and then being refused by the
     server is a small lie told at the worst moment. Checked here to say it
     before the round trip; the server still decides. */
  function weak(pw) {
    if (pw.length < 8) return "At least 8 characters.";
    if (!/[a-z]/.test(pw)) return "Needs a lower-case letter.";
    if (!/[A-Z]/.test(pw)) return "Needs a capital letter.";
    if (!/[0-9]/.test(pw)) return "Needs a digit.";
    return "";
  }
  var PW_RULE = "8 characters or more, with a capital, a lower-case letter and a digit.";

  /* ---- setting a password ----

     Two ways here, and the quick one matters more than it looks.

     From the MENU, while already signed in: no email, no waiting, no link to
     click. An account that has only ever used a mailed link can be given a
     password in about ten seconds this way, which is the whole answer to
     "how do I set up passwords for these two addresses".

     From a RECOVERY LINK: Supabase puts the page into a recovery session and
     fires PASSWORD_RECOVERY. Without something listening for that, the mail
     from "Forgot your password?" lands the reader back on a register with no
     way to finish - which is what this file did until now. The link signs you
     in and then nothing happens, and nothing says why. */
  function passwordPanel(recovery) {
    var wrap = document.createElement("div");
    wrap.className = "modal";
    wrap.innerHTML =
      '<div class="modal-in" role="dialog" aria-modal="true" aria-label="Set a password">' +
        MODAL_X + "<h3>" + (recovery ? "Set a new password" : "Set a password") + "</h3>" +
        "<p>" + (recovery
          ? "You came in on a recovery link. Choose a password and it takes effect straight away."
          : "You can keep using the mailed link. A password is simply quicker " +
            "if you open this often.") + "</p>" +
        "<form novalidate>" +
          '<label for="wf-np">New password</label>' +
          '<input id="wf-np" type="password" autocomplete="new-password" minlength="8">' +
          '<p class="wf-hint" style="margin:6px 0 0">' + PW_RULE + "</p>" +
          '<label for="wf-np2" style="margin-top:12px">Once more</label>' +
          '<input id="wf-np2" type="password" autocomplete="new-password" minlength="8">' +
          '<div class="modal-f">' +
            '<button type="button" data-x="1">' + (recovery ? "Later" : "Cancel") + "</button>" +
            '<button type="submit" class="go">Save password</button>' +
          "</div>" +
        "</form>" +
        '<p class="msg" role="status"></p>' +
      "</div>";
    document.body.appendChild(wrap);

    var a = wrap.querySelector("#wf-np");
    var b = wrap.querySelector("#wf-np2");
    var msg = wrap.querySelector(".msg");
    a.focus();
    function say(t, bad) {
      msg.textContent = t || "";
      msg.className = "msg" + (t ? (bad ? " bad" : " ok") : "");
    }
    wrap.addEventListener("click", function (e) {
      if (e.target.closest("[data-x]")) wrap.remove();
    });
    wrap.querySelector("form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var bad = weak(a.value);
      if (bad) { say(bad, true); return; }
      if (a.value !== b.value) { say("Those two do not match.", true); return; }
      var go = wrap.querySelector(".go");
      go.disabled = true;
      say("Saving…");
      var r = await sb.auth.updateUser({ password: a.value });
      go.disabled = false;
      if (r.error) { say(fail(r.error), true); return; }
      say("Saved. You can sign in with this password from now on.");
      setTimeout(function () { wrap.remove(); }, 1600);
    });
  }

  /* ------------------------------------------------------------- sign in */

  /* Three ways in, because they suit different people. A password is what
     somebody who opens this daily wants; a mailed link is what somebody who
     opens it twice a year wants, and is also the recovery path when the
     password has gone. At 300 people the difference is email volume: magic
     links mean a mail per sign-in, which needs real SMTP and patience.

     Sign-up is open on purpose. It grants NOTHING on its own - rights come
     from a roster row or a domain rule, and both of those depend on the
     address being confirmed. */
  function signInPanel() {
    var wrap = document.createElement("div");
    wrap.className = "modal";
    wrap.innerHTML =
      '<div class="modal-in" role="dialog" aria-modal="true" aria-label="Sign in">' +
        MODAL_X + "<h3>Sign in</h3>" +
        "<p>Reading the register needs no account. Signing in is what it " +
        "takes to add a note, attach an invoice or move an item’s status.</p>" +
        '<div class="wf-tabs" role="tablist">' +
          '<button type="button" data-tab="password" aria-pressed="true">Password</button>' +
          '<button type="button" data-tab="link" aria-pressed="false">Email me a link</button>' +
          '<button type="button" data-tab="new" aria-pressed="false">Create account</button>' +
        "</div>" +
        '<form novalidate>' +
          '<label for="wf-email">Your email</label>' +
          '<input id="wf-email" type="email" autocomplete="email" placeholder="you@example.com">' +
          '<div class="wf-pw">' +
            '<label for="wf-pass">Password</label>' +
            '<input id="wf-pass" type="password" autocomplete="current-password">' +
            '<p class="wf-hint wf-rule" style="margin:6px 0 0" hidden>' + PW_RULE + "</p>" +
          "</div>" +
          '<div class="modal-f">' +
            '<button type="button" data-x="1">Cancel</button>' +
            '<button type="submit" class="go">Sign in</button>' +
          "</div>" +
        "</form>" +
        '<p class="wf-forgot"><button type="button" class="linkish" data-forgot="1">' +
          "Forgot your password?</button></p>" +
        '<p class="msg" role="status"></p>' +
      "</div>";
    document.body.appendChild(wrap);

    var form = wrap.querySelector("form");
    var email = wrap.querySelector("#wf-email");
    var pass = wrap.querySelector("#wf-pass");
    var pwBox = wrap.querySelector(".wf-pw");
    var forgot = wrap.querySelector(".wf-forgot");
    var go = wrap.querySelector(".go");
    var msg = wrap.querySelector(".msg");
    var mode = "password";
    email.focus();

    function say(t, bad) {
      msg.textContent = t || "";
      msg.className = "msg" + (t ? (bad ? " bad" : " ok") : "");
    }

    function setMode(m) {
      mode = m;
      var tabs = wrap.querySelectorAll("[data-tab]");
      for (var i = 0; i < tabs.length; i++) {
        tabs[i].setAttribute("aria-pressed", String(tabs[i].dataset.tab === m));
      }
      pwBox.hidden = m === "link";
      wrap.querySelector(".wf-rule").hidden = m !== "new";
      forgot.hidden = m !== "password";
      pass.setAttribute("autocomplete",
        m === "new" ? "new-password" : "current-password");
      go.textContent = m === "link" ? "Email me a link"
                     : m === "new" ? "Create account" : "Sign in";
      say("");
    }
    setMode("password");

    wrap.addEventListener("click", function (e) {
      if (e.target.closest("[data-x]")) { wrap.remove(); return; }
      var t = e.target.closest("[data-tab]");
      if (t) { setMode(t.dataset.tab); return; }
      var tr = e.target.closest("[data-try]");
      if (tr) {
        if (tr.dataset.try === "link") {
          setMode("link");
          form.dispatchEvent(new Event("submit", { cancelable: true }));
        } else {
          wrap.querySelector("[data-forgot]").click();
        }
        return;
      }
      if (e.target.closest("[data-forgot]")) {
        var a = email.value.trim();
        if (!a) { say("Put your email in first.", true); email.focus(); return; }
        say("Sending…");
        sb.auth.resetPasswordForEmail(a, {
          redirectTo: location.origin + location.pathname
        }).then(function (r) {
          say(r.error ? fail(r.error)
                      : "Check " + a + " for a link to set a new password.",
              !!r.error);
        });
      }
    });

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      var a = email.value.trim().toLowerCase();
      if (!a) { say("Your email, please.", true); return; }
      if (mode === "new") {
        var bad2 = weak(pass.value);
        if (bad2) { say(bad2, true); return; }
      } else if (mode === "password" && !pass.value) {
        say("Your password, please.", true); return;
      }
      go.disabled = true;
      say("…");
      var r;
      if (mode === "link") {
        r = await sb.auth.signInWithOtp({
          email: a, options: { emailRedirectTo: location.origin + location.pathname }
        });
      } else if (mode === "new") {
        r = await sb.auth.signUp({
          email: a, password: pass.value,
          options: { emailRedirectTo: location.origin + location.pathname }
        });
      } else {
        r = await sb.auth.signInWithPassword({ email: a, password: pass.value });
      }
      go.disabled = false;

      if (r.error) {
        /* Supabase answers "wrong password" and "this account has no password"
           with the SAME invalid_credentials, on purpose - telling them apart
           would tell a stranger which addresses have accounts. So the page
           cannot know which it is, and the honest thing is to name both and
           hand over the way out of either. Both of these accounts reached
           this state by being created with a mailed link and never given a
           password, which is exactly the case that looks like a dead end. */
        if (r.error.code === "invalid_credentials" || r.error.status === 400) {
          msg.className = "msg bad";
          msg.innerHTML =
            "That did not work. Either the password is wrong, or this " +
            "account has never had one set — an account made with a " +
            "mailed link has no password until somebody adds it." +
            '<span class="wf-out">' +
              '<button type="button" class="linkish" data-try="link">Email me a link instead</button>' +
              '<button type="button" class="linkish" data-try="reset">Send me a password reset</button>' +
            "</span>";
          return;
        }
        say(fail(r.error), true);
        return;
      }
      if (mode === "link") {
        say("Check " + a + " — the link signs you in. It expires in an hour.");
      } else if (mode === "new") {
        /* Supabase returns a user with no session when confirmation is on,
           which is the configuration domain rules depend on. */
        say(r.data && r.data.session
          ? "Account created."
          : "Account created. Confirm it from the mail we just sent " + a +
            ", then sign in.");
      } else {
        wrap.remove();   /* onAuthStateChange redraws everything else */
      }
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
    /* Notes are readable by anyone now, so the list is unconditional and only
       the composer inside it is gated. */
    wf.appendChild(notesBlock(it, mine));
    if (can("super_admin")) wf.appendChild(pictureBlock(it, mine));
    if (can("admin")) wf.appendChild(invoiceBlock(it, mine));
    if (!can("commenter")) {
      /* Deliberately says nothing about invoices. Their existence is not
         something to advertise to a reader who cannot open them and may not
         be on the team - the word should not be in the DOM at all. */
      var p = document.createElement("p");
      p.className = "wf-quiet";
      p.innerHTML = me
        ? "You can read the register and its notes. Adding one needs an " +
          "admin to give you access."
        : '<button class="linkish" type="button" data-signin="1">Sign in</button>' +
          " to add a note.";
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

  /* A reviewer's remark can be a sentence or a paragraph, and the register
     has both. Showing all of it pushes the datasheet button off the screen;
     showing a fixed slice of it hides the part that matters. So: the first
     PREVIEW characters, and a control to see the rest - and no control at all
     when there is no rest, because a "show more" that reveals nothing is
     worse than no button.

     Cut at a word, not mid-syllable: "Color to be confir…" reads as damage. */
  var PREVIEW = 140;

  function noteBlock(n) {
    if (!n) return "";
    if (n.length <= PREVIEW) {
      return '<p class="wf-note-full">' + esc(n) + "</p>";
    }
    var cut = n.slice(0, PREVIEW);
    var sp = cut.lastIndexOf(" ");
    if (sp > PREVIEW * 0.6) cut = cut.slice(0, sp);
    return '<div class="wf-note" data-open="0">' +
      '<p class="wf-note-short">' + esc(cut) + "…</p>" +
      '<p class="wf-note-full" hidden>' + esc(n) + "</p>" +
      '<button type="button" class="linkish wf-note-more">Show the rest</button>' +
      "</div>";
  }

  function wireNote(root) {
    var b = root.querySelector(".wf-note-more");
    if (!b) return;
    b.addEventListener("click", function () {
      var box = b.closest(".wf-note");
      var open = box.dataset.open === "1";
      box.dataset.open = open ? "0" : "1";
      box.querySelector(".wf-note-short").hidden = !open;
      box.querySelector(".wf-note-full").hidden = open;
      b.textContent = open ? "Show the rest" : "Show less";
    });
  }

  function statusBlock(it, mine) {
    var sec = section("Submittal status");
    var cur = approval[it.key] || { status: "not_submitted", status_note: "" };

    if (!can("admin")) {
      /* Everyone can see where it stands; only an admin moves it. */
      var n = (cur.status_note || "").trim();
      sec.innerHTML +=
        '<p class="wf-read"><span class="st st-' + esc(cur.status) + '">' +
        "<i></i>" + esc(STATUS_WORDS[cur.status] || cur.status) + "</span>" +
        (cur.decided_at ? ' <em>' + esc(when(cur.decided_at)) + "</em>" : "") +
        "</p>" + noteBlock(n);
      wireNote(sec);
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
      '<textarea rows="1" placeholder="Note — what was noted, or why" ' +
      'aria-label="Status note">' + esc(cur.status_note || "") + "</textarea>";
    sec.appendChild(box);
    var say = msgLine(sec);

    var sel = box.querySelector("select");
    var note = box.querySelector("textarea");

    /* Grows to what it holds. A single line was fine for "Color to be
       confirmed" and useless for a paragraph, where you could see about a
       fifth of what you were editing. */
    function fit() {
      note.style.height = "auto";
      /* Full width now, so a paragraph reaches this far less often - and
         when it does, scrolling a note is better than a sheet whose Open the
         datasheet button has been pushed off the bottom. */
      note.style.height = Math.min(note.scrollHeight, 260) + "px";
    }
    note.addEventListener("input", fit);
    setTimeout(fit, 0);

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
    /* The view, not the table: it carries the author as a NAME rather than an
       address, and a `mine` flag so ownership is known without by_email ever
       reaching the page. Anonymous readers can read it; the table they
       cannot. */
    var r = await sb.from("item_note_public").select("*")
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
      html += '<li data-note="' + esc(n.id) + '"><p>' + esc(n.body) + "</p>" +
        '<span class="wf-by">' +
        esc(n.author || "Someone") + " &middot; " + esc(when(n.at)) +
        (n.edited_at ? " &middot; edited" : "") + "</span>" +
        (n.mine || can("admin")
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

  /* ---- pictures ----

     The pictures in web/img are extracted from the PDFs, and plenty of them
     are the wrong thing or a poor showing of the right one. Replacing one has
     meant staging it in the audit artifact, pulling it down with a script,
     dropping it into tools/images, re-extracting and redeploying. This does
     it where the item is, with the sign-in and storage the register already
     has.

     The bucket is public, unlike invoices: this picture is displayed on a
     page anybody can open, and a signed URL would expire and leave a broken
     image behind. */
  var pictures = {};

  async function loadPictures() {
    var r = await sb.from("item_picture").select("item_key, url");
    if (r.error) {
      if (window.console) console.warn("GP1 pictures:", fail(r.error));
      return;
    }
    pictures = {};
    for (var i = 0; i < r.data.length; i++) {
      pictures[r.data[i].item_key] = r.data[i].url;
    }
    window.GP1.setPictures(pictures);
  }

  function pictureBlock(it, mine) {
    var sec = section("Picture", ' <em>super admin</em>');
    var has = !!pictures[it.key];
    var box = document.createElement("div");
    box.className = "wf-pic";
    box.innerHTML =
      '<label class="wf-upbtn"><input type="file" accept="image/png,' +
      'image/jpeg,image/webp,image/gif" hidden>' +
      (has ? "Replace it again" : "Replace this picture") + "</label>" +
      (has ? '<button type="button" class="linkish wf-pic-rm">Put the ' +
             "original back</button>" : "");
    sec.appendChild(box);
    var say = msgLine(sec);
    if (!has) {
      var hint = document.createElement("p");
      hint.className = "wf-hint";
      hint.style.marginTop = "6px";
      hint.textContent = "The one showing now was lifted out of the datasheet. "
        + "Anything dropped here replaces it for everybody, straight away.";
      sec.insertBefore(hint, box);
    }

    box.querySelector("input").addEventListener("change", async function () {
      var file = this.files[0];
      if (!file) return;
      box.classList.add("busy");
      say("Uploading…");
      var path = it.key + "/" + safeName(file.name);
      var up = await sb.storage.from("item-pictures")
                       .upload(path, file, { upsert: true });
      if (up.error) { box.classList.remove("busy"); say(fail(up.error), true); return; }

      var pub = sb.storage.from("item-pictures").getPublicUrl(up.data.path);
      var url = pub && pub.data && pub.data.publicUrl;
      if (!url) {
        box.classList.remove("busy");
        say("Uploaded, but the storage gave no public address for it.", true);
        return;
      }
      var r = await sb.from("item_picture").upsert({
        item_key: it.key, storage_path: up.data.path, url: url,
        filename: file.name, bytes: file.size
      }, { onConflict: "item_key" }).select("item_key, url");
      box.classList.remove("busy");
      if (r.error) {
        /* The file is in the bucket and the row is not, so nothing on the
           page changed. Say so rather than leaving a silent orphan. */
        say(fail(r.error) + " The file uploaded but the record did not save, "
            + "so the picture has not changed.", true);
        return;
      }
      var got = r.data && r.data[0];
      if (!got || !got.url) { say("The database did not take that.", true); return; }
      pictures[it.key] = got.url;
      say("");
      /* Redraws the tile and reopens the sheet, so the new picture is
         visible without anybody reloading. */
      window.GP1.setPictures(pictures);
    });

    var rm = box.querySelector(".wf-pic-rm");
    if (rm) {
      rm.addEventListener("click", async function () {
        if (!confirm("Put the extracted picture back? The replacement is "
                   + "removed for everybody.")) return;
        rm.disabled = true;
        var r = await sb.from("item_picture").delete().eq("item_key", it.key);
        rm.disabled = false;
        if (r.error) { say(fail(r.error), true); return; }
        delete pictures[it.key];
        window.GP1.setPictures(pictures);
      });
    }
    return sec;
  }

  /* ---- invoices ----

     A file, and nothing else to fill in. The first version asked for a label,
     a supplier, an invoice number, an amount and a date before it would take
     anything, which is a form standing between somebody and the one thing
     they came to do. The columns are still there and still carry what the old
     rows put in them - they are simply not asked for.

     Several files at once, because invoices arrive in batches. */
  function invoiceBlock(it, mine) {
    var sec = section("Invoices", ' <em>admin only</em>');
    var list = document.createElement("ul");
    list.className = "wf-inv";
    list.innerHTML = '<li class="wf-wait">Loading…</li>';
    sec.appendChild(list);

    var box = document.createElement("div");
    box.className = "wf-up";
    box.innerHTML =
      '<label class="wf-upbtn"><input type="file" multiple ' +
      'accept="application/pdf,image/png,image/jpeg,image/webp" hidden>' +
      "Upload an invoice</label>";
    sec.appendChild(box);
    var say = msgLine(sec);
    var input = box.querySelector("input");

    input.addEventListener("change", async function () {
      var files = Array.prototype.slice.call(input.files || []);
      if (!files.length) return;
      box.classList.add("busy");
      var done = 0;
      for (var i = 0; i < files.length; i++) {
        var f = files[i];
        say("Uploading " + (i + 1) + " of " + files.length + "…");
        var up = await sb.storage.from("invoices")
                         .upload(it.key + "/" + safeName(f.name), f);
        if (up.error) { say(fail(up.error), true); break; }
        var r = await sb.from("item_invoice").insert({
          item_key: it.key, storage_path: up.data.path, filename: f.name,
          label: "", supplier: "", invoice_no: "", drive_url: null
        }).select("id");
        if (r.error) {
          /* The file is in the bucket and the row is not. Say so - a silent
             orphan in storage is worse than a visible one. */
          say(fail(r.error) + " The file uploaded but the record did not save.",
              true);
          break;
        }
        done++;
      }
      box.classList.remove("busy");
      input.value = "";
      if (done) { say(""); fillInvoices(it, list, mine); }
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
                    .eq("item_key", it.key).order("at", { ascending: false });
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
      /* label and amount are no longer asked for, but rows written when they
         were still carry them, and dropping them from the display would look
         like data loss. */
      html += '<li><span class="wf-inv-t">' +
        esc(v.filename || v.label || "Invoice") +
        (v.label && v.filename ? ' <em>' + esc(v.label) + "</em>" : "") + "</span>" +
        '<span class="wf-inv-m">' + esc(who(v.by_email)) +
          " &middot; " + esc(when(v.dated || v.at)) + "</span>" +
        (v.amount != null
          ? '<span class="wf-inv-a">' + esc(money(v.amount, v.currency)) + "</span>"
          : "") +
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

  /* ---- inviting ----

     Adding somebody to the roster creates no account and sends nothing - it
     records what they will get when they make one. An invitation is the
     separate act of telling them to.

     Sent with signInWithOtp rather than the admin invite API on purpose:
     that one needs a service_role key, which would have to live in the
     deployment, and this does the same job with the public key. The mail is
     a sign-in link; shouldCreateUser makes it work for somebody with no
     account yet. */
  async function invite(email) {
    var r = await sb.auth.signInWithOtp({
      email: email,
      options: {
        shouldCreateUser: true,
        emailRedirectTo: location.origin + location.pathname
      }
    });
    return r.error ? fail(r.error) : "";
  }

  /* ---- one person ---- */

  function personPanel(u, done) {
    var wrap = document.createElement("div");
    wrap.className = "modal";
    wrap.innerHTML =
      '<div class="modal-in" role="dialog" aria-modal="true" aria-label="Edit person">' +
        MODAL_X + "<h3>" + esc(u.name || who(u.email)) + "</h3>" +
        "<form>" +
          '<label for="pp-name">Name</label>' +
          '<input id="pp-name" type="text" value="' + esc(u.name || "") + '">' +
          '<label for="pp-email" style="margin-top:12px">Email</label>' +
          '<input id="pp-email" type="email" value="' + esc(u.email) + '">' +
          '<p class="wf-hint" style="margin:6px 0 0">This is the roster entry, ' +
          'not their account. Changing it fixes a typo made before they signed ' +
          'up — if they already have an account at the old address, their ' +
          'rights move to the new one and the old one keeps none.</p>' +
          '<label for="pp-co" style="margin-top:12px">Company</label>' +
          '<input id="pp-co" type="text" value="' + esc(u.company || "") + '">' +
          '<label for="pp-note" style="margin-top:12px">Note</label>' +
          '<input id="pp-note" type="text" value="' + esc(u.note || "") + '">' +
          '<div class="modal-f">' +
            '<button type="button" data-inv="1">' +
              (u.last_seen_at ? "Send a sign-in link" : "Send an invitation") + "</button>" +
            '<button type="button" data-x="1">Cancel</button>' +
            '<button type="submit" class="go">Save</button>' +
          "</div>" +
        "</form>" +
        '<p class="msg" role="status"></p>' +
      "</div>";
    document.body.appendChild(wrap);

    var msg = wrap.querySelector(".msg");
    function say(t, bad) {
      msg.textContent = t || "";
      msg.className = "msg" + (t ? (bad ? " bad" : " ok") : "");
    }
    wrap.addEventListener("click", async function (e) {
      if (e.target.closest("[data-x]")) { wrap.remove(); return; }
      var inv = e.target.closest("[data-inv]");
      if (!inv) return;
      inv.disabled = true;
      say("Sending…");
      var bad = await invite(wrap.querySelector("#pp-email").value.trim().toLowerCase());
      inv.disabled = false;
      say(bad || "Sent. The link in that mail signs them in and lets them set " +
                 "a password.", !!bad);
    });

    wrap.querySelector("form").addEventListener("submit", async function (e) {
      e.preventDefault();
      var email = wrap.querySelector("#pp-email").value.trim().toLowerCase();
      if (!email || email.indexOf("@") < 1) { say("That is not an email.", true); return; }
      var patch = {
        name: wrap.querySelector("#pp-name").value.trim(),
        company: wrap.querySelector("#pp-co").value.trim(),
        note: wrap.querySelector("#pp-note").value.trim()
      };
      if (email !== u.email) patch.email = email;
      var go = wrap.querySelector(".go");
      go.disabled = true;
      say("Saving…");
      var r = await sb.from("register_user").update(patch)
                      .eq("email", u.email).select("email");
      go.disabled = false;
      if (r.error) { say(fail(r.error), true); return; }
      if (!r.data || !r.data.length) {
        say("That change was refused. Nothing was saved.", true); return;
      }
      wrap.remove();
      done();
    });
  }

  /* -------------------------------------------------------------- people */

  /* Built for a roster of hundreds, which changes what the screen has to be:
     searchable, paged, and able to act on many rows at once. Naming 300
     people one at a time through a single-row form is not a thing anybody
     does twice.

     Domain rules are the real answer to scale though - one line covering
     everyone at a company - so they sit at the top rather than buried. */

  var PER = 50;

  /* PostgREST's `or` takes a comma-separated filter list, so a comma or a
     paren in the search box would be read as syntax. Only these survive. */
  function safeQ(s) { return String(s || "").replace(/[^A-Za-z0-9@.\- ]+/g, " ").trim(); }

  async function peoplePanel() {
    var wrap = document.createElement("div");
    wrap.className = "modal";
    wrap.innerHTML =
      '<div class="modal-in wide" role="dialog" aria-modal="true" aria-label="People">' +
        MODAL_X + "<h3>People</h3>" +
        '<p class="wf-counts">Loading…</p>' +

        (can("super_admin")
          ? '<details class="wf-fold"><summary>Domain rules</summary>' +
            '<p class="wf-hint">Everyone with a confirmed address at these ' +
            'domains gets at least this role, and the company name, with no ' +
            'entry of their own. One line here is usually worth a hundred ' +
            'rows below. A person who names their own company keeps it.</p>' +
            '<ul class="wf-domains"><li class="wf-wait">Loading…</li></ul>' +
            '<form class="wf-add wf-domain-add">' +
              '<input type="text" name="domain" placeholder="waratahtci.com" required aria-label="Domain">' +
              '<input type="text" name="company" placeholder="Company" aria-label="Company">' +
              '<select name="role" aria-label="Role">' +
                '<option value="viewer">Viewer</option>' +
                '<option value="commenter" selected>Commenter</option>' +
                '<option value="admin">Admin</option>' +
              "</select>" +
              '<input type="text" name="note" placeholder="Note" aria-label="Note">' +
              "<button type=\"submit\">Add rule</button>" +
            "</form></details>"
          : "") +

        '<div class="wf-toolbar">' +
          '<input type="search" class="wf-q" placeholder="Search name, email, company…" aria-label="Search people">' +
          '<select class="wf-filter" aria-label="Filter by role">' +
            '<option value="">Every role</option>' +
            '<option value="viewer">Viewer</option>' +
            '<option value="commenter">Commenter</option>' +
            '<option value="admin">Admin</option>' +
            '<option value="super_admin">Super admin</option>' +
            '<option value="blocked">Blocked</option>' +
          "</select>" +
        "</div>" +

        '<div class="wf-bulk" hidden><span></span>' +
          '<select aria-label="Set role for selected">' +
            '<option value="">Set role…</option>' +
            '<option value="viewer">Viewer</option>' +
            '<option value="commenter">Commenter</option>' +
            (can("super_admin")
              ? '<option value="admin">Admin</option>' +
                '<option value="super_admin">Super admin</option>'
              : "") +
          "</select>" +
          '<button type="button" data-bulk="invite">Invite</button>' +
          '<button type="button" data-bulk="block">Block</button>' +
          '<button type="button" data-bulk="unblock">Unblock</button>' +
          '<button type="button" data-bulk="remove" class="wf-danger">Remove</button>' +
        "</div>" +

        '<ul class="wf-people"><li class="wf-wait">Loading…</li></ul>' +
        '<div class="wf-pager"><button type="button" data-page="-1">←</button>' +
          "<span></span>" +
          '<button type="button" data-page="1">→</button></div>' +

        '<details class="wf-fold"><summary>Add people</summary>' +
          '<p class="wf-hint">One address per line, or separated by commas. ' +
          'Adding somebody here does not create an account for them — it ' +
          'says what they get when they make one themselves.</p>' +
          '<form class="wf-add wf-people-add">' +
            '<textarea name="emails" rows="3" placeholder="someone@example.com" aria-label="Email addresses"></textarea>' +
            '<input type="text" name="company" placeholder="Company" aria-label="Company">' +
            '<select name="role" aria-label="Access">' +
              '<option value="viewer">Viewer</option>' +
              '<option value="commenter" selected>Commenter</option>' +
              (can("super_admin")
                ? '<option value="admin">Admin</option>' +
                  '<option value="super_admin">Super admin</option>'
                : "") +
            "</select><button type=\"submit\">Add</button>" +
          "</form></details>" +

        '<p class="msg" role="status"></p>' +
        '<div class="modal-f"><button type="button" data-x="1">Done</button></div>' +
      "</div>";
    document.body.appendChild(wrap);

    var list = wrap.querySelector(".wf-people");
    var pager = wrap.querySelector(".wf-pager");
    var bulk = wrap.querySelector(".wf-bulk");
    var msg = wrap.querySelector(".msg");
    var qBox = wrap.querySelector(".wf-q");
    var filterBox = wrap.querySelector(".wf-filter");
    var page = 0, total = 0, sel = {}, shown = {};

    function say(t, bad) {
      msg.textContent = t || "";
      msg.className = "msg" + (t ? (bad ? " bad" : " ok") : "");
    }
    wrap.addEventListener("click", function (e) {
      if (e.target.closest("[data-x]")) wrap.remove();
    });

    /* ---- counts ---- */
    async function counts() {
      var r = await sb.rpc("people_counts");
      var el = wrap.querySelector(".wf-counts");
      if (r.error || !r.data) { el.textContent = ""; return; }
      var c = r.data;
      el.innerHTML =
        "<b>" + c.total + "</b> on the roster — " +
        c.super_admin + " super admin, " + c.admin + " admin, " +
        c.commenter + " commenter, " + c.viewer + " viewer" +
        (c.blocked ? ", <b>" + c.blocked + " blocked</b>" : "") +
        (c.domains ? " · " + c.domains +
          (c.domains === 1 ? " domain rule" : " domain rules") : "");
    }

    /* ---- the list ---- */
    async function fill() {
      var q = safeQ(qBox.value);
      var f = filterBox.value;
      var sel_ = sb.from("register_user").select("*", { count: "exact" });
      if (q) {
        sel_ = sel_.or("email.ilike.*" + q + "*,name.ilike.*" + q +
                       "*,company.ilike.*" + q + "*,note.ilike.*" + q + "*");
      }
      if (f === "blocked") sel_ = sel_.eq("blocked", true);
      else if (f) sel_ = sel_.eq("role", f).eq("blocked", false);
      var r = await sel_.order("email").range(page * PER, page * PER + PER - 1);

      if (r.error) {
        list.innerHTML = '<li class="wf-bad">' + esc(fail(r.error)) + "</li>";
        return;
      }
      total = r.count == null ? r.data.length : r.count;
      shown = {};
      for (var z = 0; z < r.data.length; z++) shown[r.data[z].email] = r.data[z];
      if (!r.data.length) {
        list.innerHTML = '<li class="wf-none">' +
          (q || f ? "Nobody matches that." : "Nobody yet.") + "</li>";
      } else {
        var html = "";
        for (var i = 0; i < r.data.length; i++) {
          var u = r.data[i];
          var mayEdit = can("super_admin") ||
                        ROLES.indexOf(u.role) < ROLES.indexOf("admin");
          var opts = "";
          for (var j = 0; j < ROLES.length; j++) {
            var allowed = can("super_admin") ||
                          ROLES.indexOf(ROLES[j]) < ROLES.indexOf("admin");
            if (!allowed && ROLES[j] !== u.role) continue;
            opts += '<option value="' + ROLES[j] + '"' +
              (ROLES[j] === u.role ? " selected" : "") + ">" +
              ROLE_WORDS[ROLES[j]] + "</option>";
          }
          html += '<li' + (u.blocked ? ' class="wf-blocked"' : "") + ">" +
            (mayEdit
              ? '<input type="checkbox" data-pick="' + esc(u.email) + '"' +
                (sel[u.email] ? " checked" : "") + ' aria-label="Select ' + esc(u.email) + '">'
              : '<span class="wf-pick-gap"></span>') +
            (mayEdit
              ? '<button type="button" class="wf-p-n wf-p-edit" data-edit="' +
                esc(u.email) + '">' + esc(u.name || who(u.email)) +
                "<em>" + esc(u.email) +
                (u.company ? " · " + esc(u.company) : "") +
                (u.note ? " · " + esc(u.note) : "") + "</em></button>"
              : '<span class="wf-p-n">' + esc(u.name || who(u.email)) +
                "<em>" + esc(u.email) +
                (u.company ? " · " + esc(u.company) : "") +
                (u.note ? " · " + esc(u.note) : "") + "</em></span>") +
            '<span class="wf-p-s">' + (u.blocked ? "blocked"
              : u.last_seen_at ? "seen " + esc(when(u.last_seen_at))
              : "never signed in") + "</span>" +
            '<select data-role="' + esc(u.email) + '"' + (mayEdit ? "" : " disabled") +
              ">" + opts + "</select>" +
            (mayEdit
              ? '<button type="button" class="wf-del" data-rm="' + esc(u.email) +
                '" aria-label="Remove">×</button>'
              : "") +
            "</li>";
        }
        list.innerHTML = html;
      }

      var from = total ? page * PER + 1 : 0;
      var to = Math.min(total, (page + 1) * PER);
      pager.querySelector("span").textContent =
        total <= PER ? (total === 1 ? "1 person" : total + " people")
                     : from + "–" + to + " of " + total;
      pager.querySelector('[data-page="-1"]').disabled = page === 0;
      pager.querySelector('[data-page="1"]').disabled = to >= total;
      pager.hidden = total <= PER;
      showBulk();
    }

    function picked() { return Object.keys(sel).filter(function (k) { return sel[k]; }); }
    function showBulk() {
      var n = picked().length;
      bulk.hidden = !n;
      bulk.querySelector("span").textContent =
        n + (n === 1 ? " selected" : " selected");
    }

    /* ---- events ---- */
    var timer = null;
    qBox.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () { page = 0; fill(); }, 250);
    });
    filterBox.addEventListener("change", function () { page = 0; fill(); });
    pager.addEventListener("click", function (e) {
      var b = e.target.closest("[data-page]");
      if (!b || b.disabled) return;
      page += Number(b.dataset.page);
      if (page < 0) page = 0;
      fill();
    });

    list.addEventListener("change", async function (e) {
      var p = e.target.closest("[data-pick]");
      if (p) { sel[p.dataset.pick] = p.checked; showBulk(); return; }
      var s = e.target.closest("[data-role]");
      if (!s) return;
      say("Saving…");
      var r = await sb.from("register_user").update({ role: s.value })
                      .eq("email", s.dataset.role).select("email, role");
      if (r.error) { say(fail(r.error), true); fill(); return; }
      if (!r.data || !r.data.length) {
        say("That change was refused. Nothing was saved.", true); fill(); return;
      }
      say(who(s.dataset.role) + " is now " + ROLE_WORDS[r.data[0].role] + ".");
      counts();
    });

    list.addEventListener("click", async function (e) {
      var ed = e.target.closest("[data-edit]");
      if (ed) {
        var u = shown[ed.dataset.edit];
        if (u) personPanel(u, function () { fill(); counts(); });
        return;
      }
      var b = e.target.closest("[data-rm]");
      if (!b) return;
      if (!confirm("Remove " + b.dataset.rm + "? They keep their account and " +
                   "lose every right on this register.")) return;
      b.disabled = true;
      var r = await sb.from("register_user").delete().eq("email", b.dataset.rm);
      if (r.error) { b.disabled = false; say(fail(r.error), true); return; }
      delete sel[b.dataset.rm];
      say(""); fill(); counts();
    });

    bulk.addEventListener("change", async function (e) {
      if (e.target.tagName !== "SELECT" || !e.target.value) return;
      await bulkDo({ role: e.target.value },
                   "set to " + ROLE_WORDS[e.target.value]);
      e.target.value = "";
    });
    bulk.addEventListener("click", async function (e) {
      var b = e.target.closest("[data-bulk]");
      if (!b) return;
      if (b.dataset.bulk === "invite") {
        var list_ = picked();
        b.disabled = true;
        var sent = 0, err = "";
        for (var i = 0; i < list_.length; i++) {
          say("Sending " + (i + 1) + " of " + list_.length + "…");
          var bad = await invite(list_[i]);
          if (bad) { err = bad; break; }
          sent++;
        }
        b.disabled = false;
        /* Stopping at the first failure is deliberate: the usual cause is the
           mail rate limit, and carrying on would burn the rest against it. */
        say(err ? sent + " sent, then: " + err : sent + " invited.", !!err);
        return;
      }
      if (b.dataset.bulk === "remove") {
        if (!confirm("Remove " + picked().length + " people from the register?")) return;
        var who_ = picked();
        b.disabled = true;
        var r = await sb.from("register_user").delete().in("email", who_);
        b.disabled = false;
        if (r.error) { say(fail(r.error), true); return; }
        sel = {}; say(who_.length + " removed."); fill(); counts();
        return;
      }
      await bulkDo({ blocked: b.dataset.bulk === "block" },
                   b.dataset.bulk === "block" ? "blocked" : "unblocked");
    });

    async function bulkDo(patch, word) {
      var who_ = picked();
      if (!who_.length) return;
      say("Saving…");
      /* .select() so the reply says how many rows the policies ACTUALLY let
         through - asking for 40 and being given 12 is a thing the person
         needs told, not a silent partial success. */
      var r = await sb.from("register_user").update(patch)
                      .in("email", who_).select("email");
      if (r.error) { say(fail(r.error), true); return; }
      var n = r.data ? r.data.length : 0;
      say(n === who_.length
        ? n + " " + word + "."
        : n + " of " + who_.length + " " + word +
          " — the rest were refused, most likely admins you cannot manage.",
        n !== who_.length);
      sel = {}; fill(); counts();
    }

    wrap.querySelector(".wf-people-add").addEventListener("submit", async function (e) {
      e.preventDefault();
      var f = e.target.elements;
      var raw = String(f.emails.value || "").split(/[\s,;]+/);
      var seen = {}, rows = [];
      for (var i = 0; i < raw.length; i++) {
        var a = raw[i].trim().toLowerCase();
        if (!a || seen[a] || a.indexOf("@") < 1) continue;
        seen[a] = 1;
        rows.push({ email: a, role: f.role.value,
                    company: f.company.value.trim(), note: "" });
      }
      if (!rows.length) { say("No addresses in that.", true); return; }
      var b = e.target.querySelector("button");
      b.disabled = true;
      say("Adding " + rows.length + "…");
      /* Upsert rather than insert: pasting a list that overlaps the roster is
         the normal case, not an error worth losing the whole paste over. */
      var r = await sb.from("register_user")
                      .upsert(rows, { onConflict: "email" }).select("email");
      b.disabled = false;
      if (r.error) { say(fail(r.error), true); return; }
      e.target.reset();
      say((r.data ? r.data.length : 0) + " added or updated.");
      fill(); counts();
    });

    /* ---- domain rules ---- */
    if (can("super_admin")) {
      var dlist = wrap.querySelector(".wf-domains");
      var dfill = async function () {
        var r = await sb.from("register_domain").select("*").order("domain");
        if (r.error) { dlist.innerHTML = '<li class="wf-bad">' + esc(fail(r.error)) + "</li>"; return; }
        if (!r.data.length) { dlist.innerHTML = '<li class="wf-none">No domain rules.</li>'; return; }
        var h = "";
        for (var i = 0; i < r.data.length; i++) {
          var d = r.data[i];
          h += "<li><span class=\"wf-p-n\">@" + esc(d.domain) +
            "<em>" + esc([d.company, d.note].filter(Boolean).join(" · ")) +
            "</em></span>" +
            '<span class="wf-p-s">' + esc(ROLE_WORDS[d.role]) + "</span>" +
            '<button type="button" class="wf-del" data-drm="' + esc(d.domain) +
            '" aria-label="Remove rule">×</button></li>';
        }
        dlist.innerHTML = h;
      };
      dlist.addEventListener("click", async function (e) {
        var b = e.target.closest("[data-drm]");
        if (!b) return;
        if (!confirm("Remove the rule for @" + b.dataset.drm +
                     "? Anyone relying on it loses their access.")) return;
        var r = await sb.from("register_domain").delete().eq("domain", b.dataset.drm);
        if (r.error) { say(fail(r.error), true); return; }
        dfill(); counts();
      });
      wrap.querySelector(".wf-domain-add").addEventListener("submit", async function (e) {
        e.preventDefault();
        var f = e.target.elements;
        say("Saving…");
        var r = await sb.from("register_domain").insert({
          domain: f.domain.value.trim(),
          role: f.role.value,
          company: f.company.value.trim(),
          note: f.note.value.trim()
        }).select("domain");
        if (r.error) { say(fail(r.error), true); return; }
        e.target.reset(); say(""); dfill(); counts();
      });
      dfill();
    }

    counts();
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

    loadPictures();

    var s = await sb.auth.getSession();
    me = s.data && s.data.session ? s.data.session.user : null;
    await readRole();
    authBox();
    loadApproval();

    sb.auth.onAuthStateChange(async function (evt, session) {
      /* Arriving on a "forgot your password" link. Checked first: the test
         below is for a CHANGE of user, and a recovery is the same person, so
         it would return before ever getting here. */
      if (evt === "PASSWORD_RECOVERY") {
        me = session ? session.user : me;
        authBox();
        passwordPanel(true);
        return;
      }
      var was = me && me.email;
      me = session ? session.user : null;
      if ((me && me.email) === was) return;
      await readRole();
      authBox();
      /* A sheet open across a sign-in is showing the wrong set of controls. */
      window.GP1.reopen();
    });
  }

  /* Deliberately kept, and deliberately not the same thing as clicking
     outside: Escape is a key somebody means to press, and a keyboard user
     needs a way out that is not a mouse. Closes the topmost panel only. */
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    var open = document.querySelectorAll(".modal");
    if (!open.length) return;
    e.stopPropagation();
    open[open.length - 1].remove();
  }, true);

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
      return;
    }
    if (e.target.closest("[data-pw]")) {
      var d2 = e.target.closest("details");
      if (d2) d2.open = false;
      passwordPanel(false);
    }
  });

  boot();
})();
