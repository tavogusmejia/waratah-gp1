/* ==========================================================================
   GP1-MUR Material & Hardware Register.

   Read-only. There is no backend, no sign-in and nothing to save: the whole
   register is data/datasheets.json, generated from the curated PDFs by
   "Data Sheets/extract_datasheets.py". Change a datasheet, re-run that, and
   this page is correct again — there is no second place to update.

   The page is built around one question: what still needs an engineer to sign
   it off? Nine of the 45 are substitutions, deviations or not yet reviewed,
   and those are the only things here allowed to be red.
   ========================================================================== */

(function () {
  "use strict";

  var DATA = "./data/datasheets.json";

  /* The four states, in the order a reviewer cares about them. `act` marks
     the ones that need a decision — it is what drives every red thing on the
     page, so it is declared once, here. */
  var STATUS = {
    deviation:    { label: "Deviation",    act: true,
                    blurb: "Differs from the specification. Needs engineer confirmation before release." },
    substitution: { label: "Substitution", act: true,
                    blurb: "Offered in place of the specified product. Needs engineer confirmation before release." },
    to_review:    { label: "To review",    act: true,
                    blurb: "Submitted but not yet reviewed. Confirm acceptance and sizes." },
    as_specified: { label: "As specified", act: false, blurb: "" },
    not_stated:   { label: "No status",    act: false, blurb: "" }
  };

  var state = { items: [], groups: [], q: "", group: "", act: false, open: null };
  var els = {};

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function icon(d) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true">' + d + "</svg>";
  }
  var I = {
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/>',
    close:  '<path d="M6 6l12 12M18 6L6 18"/>',
    out:    '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
    sun:    '<circle cx="12" cy="12" r="4.2"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>',
    moon:   '<path d="M20 13.5A8 8 0 1 1 10.5 4a6.5 6.5 0 0 0 9.5 9.5Z"/>'
  };

  /* ------------------------------------------------------------ theming */

  function recall(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* Light is not a theme here so much as the absence of the dark one: the
     stylesheet's canvas is white with no attribute set, which is what keeps the
     page matching the landing for a reader who has never touched this control.
     An "auto" option is gone with the media query it depended on. */
  function setTheme(t) {
    if (t !== "dark") t = "light";
    if (t === "light") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    store("gp1.theme", t);
    var q = document.querySelectorAll(".themeq button");
    for (var i = 0; i < q.length; i++) {
      q[i].setAttribute("aria-pressed", String(q[i].dataset.t === t));
    }
  }

  /* -------------------------------------------------------------- filter */

  function acting(it) { return STATUS[it.status] && STATUS[it.status].act; }

  function haystack(it) {
    if (it._h) return it._h;
    var parts = [it.code, it.title, it.manufacturer, it.group_name,
                 it.notes, it.submittal, STATUS[it.status].label];
    for (var i = 0; i < it.specs.length; i++) {
      parts.push(it.specs[i].label, it.specs[i].value);
    }
    it._h = parts.join(" ").toLowerCase();
    return it._h;
  }

  function visible() {
    var q = state.q.trim().toLowerCase();
    return state.items.filter(function (it) {
      if (state.group && it.group !== state.group) return false;
      if (state.act && !acting(it)) return false;
      if (q && haystack(it).indexOf(q) < 0) return false;
      return true;
    });
  }

  /* -------------------------------------------------------------- render */

  function card(it) {
    var st = STATUS[it.status];
    return '<button class="card' + (st.act ? " act" : "") + '" data-id="' + esc(it.id) + '">' +
      '<span class="card-h"><code>' + esc(it.code) + "</code>" +
      (it.manufacturer ? "<b>" + esc(it.manufacturer) + "</b>" : "") + "</span>" +
      '<span class="card-t">' + esc(it.title) + "</span>" +
      (it.specs.length
        ? '<span class="card-s">' + esc(it.specs[0].value.slice(0, 96)) + "</span>"
        : "") +
      '<span class="card-f">' +
        '<span class="tag' + (st.act ? " act" : " ok") + '">' + esc(st.label) + "</span>" +
        '<span class="pages">' + it.pages + (it.pages === 1 ? " page" : " pages") + "</span>" +
      "</span></button>";
  }

  function render() {
    var rows = visible();
    els.count.textContent = rows.length === state.items.length
      ? state.items.length + " datasheets"
      : rows.length + " of " + state.items.length;

    if (!rows.length) {
      els.list.innerHTML = '<p class="none">Nothing matches that. ' +
        '<button class="chip" data-clear="1">Clear the filters</button></p>';
      return;
    }

    /* Grouped, always — the submittal letters are how the team refers to
       these items out loud, so they are the spine of the page rather than a
       filter you have to find. */
    var html = "", seen = {};
    for (var g = 0; g < state.groups.length; g++) {
      var grp = state.groups[g];
      var mine = rows.filter(function (r) { return r.group === grp.key; });
      if (!mine.length) continue;
      seen[grp.key] = mine.length;
      html += '<section class="group" id="g-' + grp.key + '"><h3>' +
        "<em>" + esc(grp.key) + "</em> " + esc(grp.name) +
        (grp.submittal ? " &middot; " + esc(grp.submittal) : "") +
        "</h3><div class=\"cards\">";
      for (var i = 0; i < mine.length; i++) html += card(mine[i]);
      html += "</div></section>";
    }
    els.list.innerHTML = html;

    var btns = els.rail.querySelectorAll("button[data-g]");
    for (var b = 0; b < btns.length; b++) {
      var k = btns[b].dataset.g;
      btns[b].setAttribute("aria-pressed", String(state.group === k));
    }
  }

  function renderRail() {
    var html = "<h3>Groups</h3>" +
      '<button data-g="" aria-pressed="true">All groups<b>' +
      state.items.length + "</b></button>";
    for (var i = 0; i < state.groups.length; i++) {
      var g = state.groups[i];
      if (!g.count) continue;
      html += '<button data-g="' + esc(g.key) + '" aria-pressed="false"><kbd>' +
        esc(g.key) + "</kbd> " + esc(g.name) + "<b>" + g.count + "</b></button>";
    }
    els.rail.innerHTML = html;
  }

  function renderAlarm() {
    var n = state.items.filter(acting).length;
    var el = els.alarm;
    if (!n) {
      el.className = "alarm clear";
      el.innerHTML = "<b>0</b><span>Nothing is waiting on an engineer.</span>";
      return;
    }
    el.className = "alarm";
    el.innerHTML = "<b>" + n + "</b><span>" +
      (n === 1 ? "datasheet needs" : "datasheets need") +
      " engineer confirmation before release &mdash; substitutions, deviations " +
      "and items not yet reviewed.</span>" +
      '<button data-act="1">Show me</button>';
  }

  /* --------------------------------------------------------------- sheet */

  /* Where a datasheet actually opens. `drive_url` wins when it is there, and
     the file shipped beside the page is the fallback.

     The point of the two is that moving 40 MB of PDFs off this deploy and onto
     Drive should be a data change, not a code change: fill the field in
     datasheets.json and stop shipping web/datasheets/. Nothing here has to
     know which of the two happened. */
  function href(it) {
    return it.drive_url ? it.drive_url : "./" + it.pdf;
  }

  function openSheet(id) {
    var it = null;
    for (var i = 0; i < state.items.length; i++) {
      if (state.items[i].id === id) { it = state.items[i]; break; }
    }
    if (!it) return;
    state.open = it;
    var st = STATUS[it.status];

    var rows = "";
    for (var s = 0; s < it.specs.length; s++) {
      rows += "<tr><th>" + esc(it.specs[s].label) + "</th><td>" +
        esc(it.specs[s].value) + "</td></tr>";
    }

    els.sheet.innerHTML =
      '<div class="sheet-h">' +
        '<button class="sheet-x" data-close="1" aria-label="Close">' + icon(I.close) + "</button>" +
        '<span class="card-h"><code>' + esc(it.code) + "</code>" +
          (it.manufacturer ? "<b>" + esc(it.manufacturer) + "</b>" : "") +
          '<span class="tag' + (st.act ? " act" : " ok") + '">' + esc(st.label) + "</span>" +
        "</span>" +
        "<h2>" + esc(it.title) + "</h2>" +
      "</div>" +
      '<div class="sheet-b">' +
        (st.act
          ? '<div class="warn"><h4>' + esc(st.label) + "</h4><p>" +
            esc(it.notes || st.blurb) + "</p></div>"
          : "") +
        (rows ? '<table class="specs">' + rows + "</table>"
              : '<p class="sheet-note">This one is the manufacturer’s own sheet with no ' +
                "curated summary in front of it, so there is nothing to tabulate. " +
                "Open the datasheet.</p>") +
        (it.notes && !st.act
          ? '<p class="sheet-note">' + esc(it.notes) + "</p>" : "") +
        '<div class="sheet-meta">' +
          (it.submittal ? "<span>Submittal " + esc(it.submittal) + "</span>" : "") +
          "<span>Group " + esc(it.group) + " &middot; " + esc(it.group_name) + "</span>" +
          "<span>" + esc(it.discipline) + "</span>" +
        "</div>" +
      "</div>" +
      '<div class="sheet-f">' +
        '<a class="open" href="' + esc(href(it)) + '" target="_blank" rel="noopener">' +
          icon(I.out) + "Open the datasheet <em>" + it.pages +
          (it.pages === 1 ? " page" : " pages") + " &middot; " +
          Math.round(it.bytes / 1024) + " KB</em></a>" +
      "</div>";

    els.sheet.classList.add("on");
    els.scrim.classList.add("on");
    els.sheet.querySelector(".sheet-x").focus();
    document.documentElement.style.overflow = "hidden";
  }

  function closeSheet() {
    state.open = null;
    els.sheet.classList.remove("on");
    els.scrim.classList.remove("on");
    document.documentElement.style.overflow = "";
  }

  /* ---------------------------------------------------------------- wire */

  function wire() {
    els.search.addEventListener("input", function () {
      state.q = els.search.value; render();
    });

    els.rail.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-g]");
      if (!b) return;
      state.group = b.dataset.g;
      render();
    });

    document.addEventListener("click", function (e) {
      var c = e.target.closest(".card");
      if (c) { openSheet(c.dataset.id); return; }
      if (e.target.closest("[data-close]") || e.target === els.scrim) { closeSheet(); return; }
      if (e.target.closest("[data-act]")) {
        state.act = true; state.group = "";
        els.actChip.setAttribute("aria-pressed", "true");
        render();
        els.list.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      if (e.target.closest("[data-clear]")) {
        state.q = ""; state.group = ""; state.act = false;
        els.search.value = "";
        els.actChip.setAttribute("aria-pressed", "false");
        render();
      }
    });

    els.actChip.addEventListener("click", function () {
      state.act = !state.act;
      els.actChip.setAttribute("aria-pressed", String(state.act));
      render();
    });

    document.querySelector(".themeq").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-t]");
      if (b) setTheme(b.dataset.t);
    });

    addEventListener("keydown", function (e) {
      if (e.key === "Escape" && state.open) closeSheet();
      if (e.key === "/" && document.activeElement !== els.search) {
        e.preventDefault(); els.search.focus();
      }
    });
  }

  /* ---------------------------------------------------------------- boot */

  function ready() { document.dispatchEvent(new Event("gp1:ready")); }

  function boot(data) {
    state.items = data.items;
    state.groups = data.groups;

    els.lede.innerHTML =
      "<h2>Material &amp; Hardware Register</h2>" +
      "<p>Every curated datasheet for GP1-MUR mockup room 1 &mdash; " +
      data.items.length + " items across " +
      data.groups.filter(function (g) { return g.count; }).length +
      " groups, each with the manufacturer’s sheet attached. " +
      "Read-only: it is generated from the submittal record.</p>";

    renderAlarm();
    renderRail();
    render();
    wire();
    setTheme(recall("gp1.theme") || "light");
    ready();
  }

  els.lede = document.getElementById("lede");
  els.alarm = document.getElementById("alarm");
  els.rail = document.getElementById("rail");
  els.list = document.getElementById("list");
  els.count = document.getElementById("count");
  els.search = document.getElementById("q");
  els.actChip = document.getElementById("actchip");
  els.sheet = document.getElementById("sheet");
  els.scrim = document.getElementById("scrim");

  document.getElementById("i-search").innerHTML = I.search;
  var tq = document.querySelectorAll(".themeq button");
  tq[0].innerHTML = icon(I.sun); tq[1].innerHTML = icon(I.moon);

  fetch(DATA, { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("datasheets.json returned " + r.status);
      return r.json();
    })
    .then(boot)
    .catch(function (err) {
      /* Say what went wrong and leave a way through. A register that renders
         an empty page is indistinguishable from one with nothing in it. */
      els.list.innerHTML = '<p class="none"><b>The register could not load.</b> ' +
        esc(String(err && err.message || err)) +
        ' &mdash; the data is still readable as <a href="./data/datasheets.json">' +
        "datasheets.json</a>.</p>";
      if (window.console) console.error(err);
      ready();
    });
})();
