/* ==========================================================================
   GP1-MUR Material & Hardware Register.

   The CATALOGUE is read-only and has no backend: the whole of it is
   data/datasheets.json, generated from the curated PDFs by
   "tools/extract_datasheets.py", which reads the submittal folder. Change a
   datasheet there, re-run that, and this page is correct again — there is no
   second place to update.

   The WORKFLOW laid over it — submittal status, notes, invoices — is not in
   this file. It lives in workflow.js, talks to Supabase, and reaches this
   file through the small window.GP1 seam at the bottom. That split is the
   point: with workflow.js absent, unconfigured or unreachable, everything
   here still renders exactly as it did when the register was read-only, which
   is what an anonymous reader gets and what the test harness checks.

   So: a fast way to find an item, see what it looks like, read its
   specification and open its datasheet — and, if someone has set one, a badge
   saying where it stands.
   ========================================================================== */

(function () {
  "use strict";

  var DATA = "./data/datasheets.json";

  /* `approval` is item_key -> {status, status_note, ...}, handed over by
     workflow.js. Empty until it arrives, and empty forever if it does not.

     Named approval, not status: an item already carries `status` (the curated
     sheet's spec position - "submitted as specified", "substitution",
     "deviation") and `submittal` (the package number, JANU-SUB-003). Three
     different things behind one word is how the wrong one gets rendered. */
  var state = { items: [], groups: [], q: "", view: "cards", open: null,
                approval: {},
                /* One bag of chosen values per facet. Empty means "no
                   opinion", which is not the same as "none of them". */
                facets: { discipline: {}, group: {}, maker: {}, status: {} } };
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
    moon:   '<path d="M20 13.5A8 8 0 1 1 10.5 4a6.5 6.5 0 0 0 9.5 9.5Z"/>',
    grid:   '<rect x="3.5" y="3.5" width="7" height="7" rx="1.4"/>' +
            '<rect x="13.5" y="3.5" width="7" height="7" rx="1.4"/>' +
            '<rect x="3.5" y="13.5" width="7" height="7" rx="1.4"/>' +
            '<rect x="13.5" y="13.5" width="7" height="7" rx="1.4"/>',
    rows:   '<path d="M3.5 6h17M3.5 12h17M3.5 18h17"/>'
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

  function setView(v) {
    state.view = v === "rows" ? "rows" : "cards";
    store("gp1.view", state.view);
    var q = document.querySelectorAll(".viewq button");
    for (var i = 0; i < q.length; i++) {
      q[i].setAttribute("aria-pressed", String(q[i].dataset.v === state.view));
    }
  }

  /* -------------------------------------------------------------- filter */

  /* ------------------------------------------------------------- facets

     Four filters that behave identically, which is the whole point: the page
     used to carry five controls in four idioms - a text box, a list in the
     rail, two dropdowns, and a strip of chips - with the group filter
     existing twice, once for wide screens and once for narrow. Nothing said
     what was currently on, and dropping one meant finding the control that
     set it.

     Within a facet the values are OR: Pool and Doors shows both. Between
     facets they are AND: Lighting and LedFlex shows LedFlex's lighting. */
  var FACETS = [
    { key: "discipline", label: "Discipline",
      of: function (it) { return [it.discipline || "Other"]; } },
    { key: "group", label: "Group",
      of: function (it) { return [it.group]; },
      name: function (v) {
        for (var i = 0; i < state.groups.length; i++) {
          if (state.groups[i].key === v) {
            return '<kbd>' + esc(v) + "</kbd>" + esc(state.groups[i].name);
          }
        }
        return esc(v);
      } },
    { key: "maker", label: "Maker", search: true,
      /* 45 of the 147 name no maker, every Lutron sheet among them. Leaving
         them out of the facet would make it unable to reach a third of the
         register, and "which of these has nobody recorded a maker for" is
         one of the more useful things to be able to ask of it. */
      of: function (it) { return [it.manufacturer || NO_MAKER]; },
      name: function (v) {
        return v === NO_MAKER ? '<em class="dim">None recorded</em>' : esc(v);
      } },
    { key: "status", label: "Status", order: true,
      of: function (it) { return [statusOf(it)]; },
      name: function (v) {
        return '<s class="st-' + esc(v) + '"></s>' +
               esc(WORDS[v] || "Not submitted");
      } }
  ];

  /* Distinct from the manufacturer literally named "Not stated" on the
     manhole covers, which is a maker somebody wrote down. */
  var NO_MAKER = "—";

  function facetOf(key) {
    for (var i = 0; i < FACETS.length; i++) {
      if (FACETS[i].key === key) return FACETS[i];
    }
    return null;
  }

  /* The plain-text name of one value, for the Showing row and for sorting.
     `name` returns markup, which a pill cannot use as a label. */
  function valueLabel(f, v) {
    if (f.key === "group") {
      for (var i = 0; i < state.groups.length; i++) {
        if (state.groups[i].key === v) return v + " · " + state.groups[i].name;
      }
      return v;
    }
    if (f.key === "status") return WORDS[v] || "Not submitted";
    if (v === NO_MAKER) return "No manufacturer recorded";
    return v;
  }

  function any(o) { for (var k in o) { if (o[k]) return true; } return false; }

  function hay(it) {
    if (it._h) return it._h;
    var parts = [it.code, it.title, it.manufacturer, it.group_name,
                 it.category, it.notes, it.submittal];
    for (var i = 0; i < it.specs.length; i++) {
      parts.push(it.specs[i].label, it.specs[i].value);
    }
    it._h = parts.join(" ").toLowerCase();
    return it._h;
  }

  /* Does this item survive the search and every facet EXCEPT `skip`?

     Skipping one facet is what makes its own counts honest. A facet counted
     against its own selection would show 1 beside the thing you just picked
     and 0 beside everything else, which tells you nothing about what you
     could pick instead. */
  function passes(it, skip) {
    var q = state.q.trim().toLowerCase();
    if (q && hay(it).indexOf(q) < 0) return false;
    for (var i = 0; i < FACETS.length; i++) {
      var f = FACETS[i];
      if (f.key === skip) continue;
      var sel = state.facets[f.key];
      if (!any(sel)) continue;
      var vals = f.of(it), hit = false;
      for (var v = 0; v < vals.length; v++) {
        if (sel[vals[v]]) { hit = true; break; }
      }
      if (!hit) return false;
    }
    return true;
  }

  function visible() {
    return state.items.filter(function (it) { return passes(it, null); });
  }

  /* What this facet could offer, given everything else that is already on.

     Counted this way a value that would produce nothing is simply not there,
     so no combination of clicks can land on an empty page. This reverses the
     status strip's rule of counting over every item regardless: that showed
     "Approved 7" while Lighting was selected and only two lighting items were
     approved, which is a number describing a result you cannot reach. */
  function tally(f) {
    var n = {};
    for (var i = 0; i < state.items.length; i++) {
      var it = state.items[i];
      if (!passes(it, f.key)) continue;
      var vals = f.of(it);
      for (var v = 0; v < vals.length; v++) n[vals[v]] = (n[vals[v]] || 0) + 1;
    }
    var keys = Object.keys(n);
    if (f.order) {
      keys.sort(function (a, b) { return ORDER.indexOf(a) - ORDER.indexOf(b); });
    } else if (f.key === "group") {
      var seq = state.groups.map(function (g) { return g.key; });
      keys.sort(function (a, b) { return seq.indexOf(a) - seq.indexOf(b); });
    } else {
      /* Biggest first, then alphabetical. Eighteen of the makers name a
         single item; leading with them buries the ten that matter. */
      keys.sort(function (a, b) {
        return n[b] - n[a] || a.localeCompare(b);
      });
    }
    return { keys: keys, n: n };
  }

  function renderFacets() {
    if (!els.facets) return;
    var html = "";
    for (var i = 0; i < FACETS.length; i++) {
      var f = FACETS[i];
      var on = 0, sel = state.facets[f.key];
      for (var k in sel) { if (sel[k]) on++; }
      html += '<div class="facet" data-facet="' + f.key + '">' +
        '<button class="fbtn" type="button" aria-expanded="false">' +
        esc(f.label) + (on ? '<i>' + on + "</i>" : "") +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>' +
        "</button></div>";
    }
    els.facets.innerHTML = html;
  }

  /* The open popover is built on demand, so its counts are always current -
     they depend on every other facet and change as those are used. */
  function openFacet(box) {
    closeFacets(box);
    var f = facetOf(box.dataset.facet);
    var got = tally(f), sel = state.facets[f.key];
    var html = '<div class="pop">';
    if (f.search) {
      html += '<input class="fsearch" type="search" placeholder="Search makers" ' +
              'aria-label="Search makers">';
    }
    html += '<div class="popl">';
    for (var i = 0; i < got.keys.length; i++) {
      var v = got.keys[i];
      html += '<label class="fopt"><input type="checkbox" value="' + esc(v) + '"' +
        (sel[v] ? " checked" : "") + "><span>" +
        (f.name ? f.name(v) : esc(v)) + "</span><b>" + got.n[v] + "</b></label>";
    }
    html += "</div>";
    /* A selection can always be undone from inside the thing that made it. */
    html += '<button class="fclear" type="button">Clear ' + esc(f.label) + "</button>";
    html += "</div>";
    box.insertAdjacentHTML("beforeend", html);
    box.classList.add("on");
    box.querySelector(".fbtn").setAttribute("aria-expanded", "true");
    var s = box.querySelector(".fsearch");
    if (s) s.focus();
  }

  function closeFacets(except) {
    var open = document.querySelectorAll(".facet.on");
    for (var i = 0; i < open.length; i++) {
      if (open[i] === except) continue;
      var p = open[i].querySelector(".pop");
      if (p) p.remove();
      open[i].classList.remove("on");
      open[i].querySelector(".fbtn").setAttribute("aria-expanded", "false");
    }
  }

  /* Every active filter, named, each droppable on its own. */
  function renderShowing() {
    if (!els.showing) return;
    var bits = [];
    for (var i = 0; i < FACETS.length; i++) {
      var f = FACETS[i], sel = state.facets[f.key];
      for (var v in sel) {
        if (!sel[v]) continue;
        bits.push('<button class="pill" type="button" data-drop="' + f.key +
          '" data-v="' + esc(v) + '">' + esc(valueLabel(f, v)) +
          '<em aria-hidden="true">×</em></button>');
      }
    }
    if (state.q.trim()) {
      bits.push('<button class="pill" type="button" data-drop="q">' +
        "“" + esc(state.q.trim()) + "”<em aria-hidden=\"true\">×</em></button>");
    }
    els.showing.hidden = !bits.length;
    if (!bits.length) { els.showing.innerHTML = ""; return; }
    els.showing.innerHTML = "<b>Showing</b>" + bits.join("") +
      '<button class="clearall" type="button" data-clear="1">Clear all</button>';
  }

  function clearFilters() {
    state.q = "";
    if (els.search) els.search.value = "";
    for (var i = 0; i < FACETS.length; i++) state.facets[FACETS[i].key] = {};
    closeFacets(null);
    render();
  }

  /* -------------------------------------------------------------- render */

  /* The thumbnail. Eleven of the 45 have no picture, and they get the item
     code on a tinted square rather than a placeholder icon: it keeps every
     card the same shape, and it says "no photograph" instead of miming one. */
  function thumb(it) {
    if (!it.image) {
      return '<span class="thumb none">' + esc(it.code) + "</span>";
    }
    return '<span class="thumb"><img src="./' + esc(it.image) + '" alt="" ' +
           'loading="lazy" decoding="async"></span>';
  }

  /* Nothing for an item nobody has ruled on yet - 'not_submitted' is the
     absence of a badge rather than a grey one, so an untriaged register looks
     untouched instead of uniformly flagged. */
  var WORDS = {
    submitted: "Submitted", approved: "Approved",
    approved_as_noted: "Approved as noted", revise_resubmit: "Revise & resubmit",
    rejected: "Rejected"
  };

  /* Lifecycle order, with the default last: it is always the biggest count
     and the least interesting, and leading with it would bury the five that
     someone actually came to look for. */
  var ORDER = ["submitted", "approved", "approved_as_noted",
               "revise_resubmit", "rejected", "not_submitted"];

  function statusOf(it) {
    var st = state.approval[it.key];
    return (st && st.status) || "not_submitted";
  }

  function pill(it) {
    var st = state.approval[it.key];
    var k = st && st.status;
    if (!k || !WORDS[k]) return "";
    /* A tooltip is a glance, not a document. A paragraph in one covers the
       page it is describing and cannot be scrolled; the sheet is where the
       whole remark lives. */
    var n = (st.status_note || "").trim();
    if (n.length > 120) n = n.slice(0, 120).replace(/\s+\S*$/, "") + "…";
    return '<span class="st st-' + k + '" title="' + esc(WORDS[k]) +
      (n ? " — " + esc(n) : "") +
      '"><i></i>' + esc(WORDS[k]) + "</span>";
  }

  function card(it) {
    return '<button class="card" data-id="' + esc(it.id) + '">' +
      thumb(it) +
      '<span class="card-body">' +
        '<span class="card-h"><code>' + esc(it.code) + "</code>" +
        (it.manufacturer ? "<b>" + esc(it.manufacturer) + "</b>" : "") + "</span>" +
        '<span class="card-t">' + esc(it.title) + "</span>" +
        (it.specs.length
          ? '<span class="card-s">' + esc(it.specs[0].value.slice(0, 96)) + "</span>"
          : "") +
        '<span class="card-f">' +
          pill(it) +
          '<span class="pages">' + it.pages +
          (it.pages === 1 ? " page" : " pages") + "</span>" +
        "</span>" +
      "</span></button>";
  }

  /* List view carries no pictures on purpose. It is the view for when you know
     what you are looking for and want the most items on screen at once. */
  function row(it) {
    return '<button class="row" data-id="' + esc(it.id) + '">' +
      "<code>" + esc(it.code) + "</code>" +
      '<span class="row-t">' + esc(it.title) + "</span>" +
      '<span class="row-m">' + esc(it.manufacturer || "") + "</span>" +
      (pill(it) || '<span class="st-gap"></span>') +
      '<span class="pages">' + it.pages +
      (it.pages === 1 ? " page" : " pages") + "</span>" +
      "</button>";
  }

  function render() {
    renderFacets();
    renderShowingAndList();
  }

  /* Everything except the facet buttons. Rebuilding those would throw away
     the popover the reader is standing in, so a tick inside one redraws the
     results and the Showing row and leaves the bar alone - except for the
     count on the button that owns the popover, which is updated in place. */
  function renderShowingAndList() {
    for (var i = 0; i < FACETS.length; i++) {
      var box = els.facets.querySelector('[data-facet="' + FACETS[i].key + '"]');
      if (!box) continue;
      var on = 0, sel = state.facets[FACETS[i].key];
      for (var k in sel) { if (sel[k]) on++; }
      var b = box.querySelector(".fbtn i");
      if (on && b) b.textContent = on;
      else if (on) {
        /* Before the chevron, which is where a full render puts it. Adding it
           at the front instead read as "1 Discipline" - the badge in place of
           the label rather than beside it. */
        box.querySelector(".fbtn svg")
           .insertAdjacentHTML("beforebegin", "<i>" + on + "</i>");
      } else if (b) b.remove();
    }
    renderShowing();
    paintList();
  }

  function paintList() {
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
      var list = state.view === "rows";
      html += '<section class="group" id="g-' + grp.key + '"><h3>' +
        "<em>" + esc(grp.key) + "</em> " + esc(grp.name) +
        (grp.submittal ? " &middot; " + esc(grp.submittal) : "") +
        "</h3><div class=\"" + (list ? "rows" : "cards") + "\">";
      for (var i = 0; i < mine.length; i++) {
        html += list ? row(mine[i]) : card(mine[i]);
      }
      html += "</div></section>";
    }
    els.list.innerHTML = html;
  }

  /* Counted over every item, not over what is currently on screen: a filter
     whose numbers move as you use it cannot be read. */
  /* --------------------------------------------------------------- sheet */

  /* Where a datasheet actually opens. `drive_url` wins when it is there, and
     the file shipped beside the page is the fallback.

     The point of the two is that moving 40 MB of PDFs off this deploy and onto
     Drive should be a data change, not a code change: fill the field in
     datasheets.json and stop shipping web/datasheets/. Nothing here has to
     know which of the two happened. */
  function size(b) {
    return b >= 1048576 ? (b / 1048576).toFixed(1) + " MB"
                        : Math.round(b / 1024) + " KB";
  }

  /* Drive only. The PDFs stopped shipping when they moved to Drive, and
     web/datasheets/ is ignored by both git and Vercel, so falling back to
     "./" + it.pdf handed out a link that 404s. Seven items were doing
     exactly that, live, after their source files were renamed and their
     Drive links stopped matching. No link now means the disabled state,
     which is at least true. */
  function href(it) {
    return it.drive_url || "";
  }

  function openSheet(id) {
    var it = null;
    for (var i = 0; i < state.items.length; i++) {
      if (state.items[i].id === id) { it = state.items[i]; break; }
    }
    if (!it) return;
    state.open = it;

    var rows = "";
    for (var s = 0; s < it.specs.length; s++) {
      rows += "<tr><th>" + esc(it.specs[s].label) + "</th><td>" +
        esc(it.specs[s].value) + "</td></tr>";
    }

    els.sheet.innerHTML =
      '<div class="grab" aria-hidden="true"><i></i></div>' +
      '<div class="sheet-h">' +
        '<button class="sheet-x" data-close="1" aria-label="Close">' + icon(I.close) + "</button>" +
        '<span class="card-h"><code>' + esc(it.code) + "</code>" +
          (it.manufacturer ? "<b>" + esc(it.manufacturer) + "</b>" : "") +
        "</span>" +
        "<h2>" + esc(it.title) + "</h2>" +
      "</div>" +
      '<div class="sheet-b">' +
        /* The picture first. Often it is the only thing somebody opened this
           for - they know the item, they just want to see it. Lazy, because
           the sheet is built before it is slid into view. */
        (it.image
          ? '<figure class="shot"><img src="./' + esc(it.image) + '" alt="' +
            esc(it.title) + '" loading="lazy" decoding="async"></figure>'
          : "") +
        (rows ? '<table class="specs">' + rows + "</table>"
              : '<p class="sheet-note">This one is the manufacturer’s own sheet with no ' +
                "curated summary in front of it, so there is nothing to tabulate. " +
                "Open the datasheet.</p>") +
        (it.notes ? '<p class="sheet-note">' + esc(it.notes) + "</p>" : "") +
        '<div class="sheet-meta">' +
          (it.category ? "<span>" + esc(it.category) + "</span>" : "") +
          (it.submittal ? "<span>Submittal " + esc(it.submittal) + "</span>" : "") +
          "<span>Group " + esc(it.group) + " &middot; " + esc(it.group_name) + "</span>" +
          "<span>" + esc(it.discipline) + "</span>" +
        "</div>" +
      "</div>" +
      '<div class="sheet-f">' +
        /* Everything else this item comes with, above the datasheet button:
           the manufacturer's own page (the submittal PDF is a snapshot, the
           page is what stays current), then whatever the source ships
           alongside - an installation guide, the vendor datasheet. Worth
           having in front of somebody standing at the door with a
           screwdriver. */
        '<div class="extras">' +
        (it.maker_url
          ? '<a class="extra maker" href="' + esc(it.maker_url) + '" ' +
            'target="_blank" rel="noopener noreferrer">' + icon(I.out) +
            esc(it.manufacturer || "Manufacturer") + " page</a>"
          : "") +
        (it.extras && it.extras.length
          ? it.extras.map(function (x) {
              var u = href(x);
              if (!u) {
                return '<span class="extra off">' + icon(I.out) +
                  esc(x.kind) + "<em>not linked</em></span>";
              }
              return '<a class="extra" href="' + esc(u) + '" ' +
                'target="_blank" rel="noopener">' + icon(I.out) +
                esc(x.kind) + "<em>" + size(x.bytes) + "</em></a>";
            }).join("")
          : "") +
        "</div>" +
        /* A gap has to read as a gap. With neither a link nor a local copy
           there is nothing to open, so say so rather than hand over a button
           that 404s - the extent still says what you are missing. */
        (href(it)
          ? '<a class="open" href="' + esc(href(it)) + '" target="_blank" ' +
            'rel="noopener">' + icon(I.out) + "Open the datasheet <em>" +
            it.pages + (it.pages === 1 ? " page" : " pages") + " &middot; " +
            size(it.bytes) + "</em></a>"
          : '<span class="open off">Not linked yet <em>' + it.pages +
            (it.pages === 1 ? " page" : " pages") + " &middot; " +
            size(it.bytes) + "</em></span>") +
      "</div>";

    /* workflow.js appends the status control, the notes and the invoices
       here. Wrapped because a throw inside it must not leave the sheet
       half-open with no focus and no way back out. */
    if (GP1.onSheet) {
      try { GP1.onSheet(it, els.sheet); }
      catch (e) { if (window.console) console.error(e); }
    }

    els.sheet.classList.add("on");
    els.scrim.classList.add("on");
    els.sheet.querySelector(".sheet-x").focus();
    document.documentElement.style.overflow = "hidden";
  }

  function closeSheet() {
    state.open = null;
    els.sheet.classList.remove("on", "dragging");
    els.scrim.classList.remove("on", "dragging");
    els.sheet.style.transform = "";
    els.scrim.style.opacity = "";
    document.documentElement.style.overflow = "";
  }

  /* ---- pull the sheet down to dismiss it (phone layout only) ----------

     On a phone the sheet rises from the bottom, so pulling it back down is
     the gesture people arrive expecting - and it beats stretching for a
     close button in the opposite corner one-handed.

     Two rules keep it from fighting the page. It only engages on the phone
     layout, where the sheet is a bottom sheet rather than a side panel. And
     a drag that starts inside the scrolling body only counts when that body
     is already at the top, so pulling down to scroll up through the specs
     never drags the sheet away instead. */
  function pullToDismiss() {
    var phone = window.matchMedia("(max-width: 560px)");
    var startY = 0, dy = 0, live = false;
    var lastY = 0, lastT = 0, vy = 0;
    var H = function () { return els.sheet.offsetHeight || 1; };

    function begin(ev) {
      if (!phone.matches || !state.open || ev.touches.length !== 1) return;
      var body = ev.target.closest(".sheet-b");
      if (body && body.scrollTop > 0) return;
      startY = lastY = ev.touches[0].clientY;
      lastT = Date.now();
      dy = 0;
      vy = 0;
      live = true;
      els.sheet.classList.add("dragging");
      els.scrim.classList.add("dragging");
    }

    function move(ev) {
      if (!live) return;
      dy = ev.touches[0].clientY - startY;
      if (dy < 0) {
        /* Pulling up does nothing, but the finger is still down - let the
           body scroll rather than rubber-banding a sheet that cannot rise. */
        dy = 0;
        return;
      }
      if (ev.cancelable) ev.preventDefault();
      /* Speed over the LAST move, not the whole gesture. A drag that dawdles
         and then flicks is a flick, and a long slow haul is not - averaging
         from touchstart gets both backwards. */
      var now = Date.now(), y = ev.touches[0].clientY;
      if (now > lastT) vy = (y - lastY) / (now - lastT);
      lastY = y;
      lastT = now;
      els.sheet.style.transform = "translateY(" + dy + "px)";
      els.scrim.style.opacity = String(Math.max(0, 1 - dy / H()));
    }

    function end() {
      if (!live) return;
      live = false;
      els.sheet.classList.remove("dragging");
      els.scrim.classList.remove("dragging");
      els.sheet.style.transform = "";
      els.scrim.style.opacity = "";
      /* Far enough, or thrown hard enough. A flick should close even when it
         barely moved - that is what makes it feel like a sheet rather than a
         drawer with a minimum. */
      if (dy > H() * 0.28 || (dy > 40 && vy > 0.45)) closeSheet();
      dy = 0;
    }

    els.sheet.addEventListener("touchstart", begin, { passive: true });
    els.sheet.addEventListener("touchmove", move, { passive: false });
    els.sheet.addEventListener("touchend", end);
    els.sheet.addEventListener("touchcancel", end);
  }

  /* ---------------------------------------------------------------- wire */

  function wire() {
    els.search.addEventListener("input", function () {
      state.q = els.search.value; render();
    });

    /* One delegated handler for all four facets: the popovers are built on
       demand and thrown away, so binding to them individually would mean
       rebinding on every open. */
    els.facets.addEventListener("click", function (e) {
      var btn = e.target.closest(".fbtn");
      if (btn) {
        var box = btn.closest(".facet");
        if (box.classList.contains("on")) closeFacets(null);
        else openFacet(box);
        return;
      }
      var clear = e.target.closest(".fclear");
      if (clear) {
        state.facets[clear.closest(".facet").dataset.facet] = {};
        closeFacets(null);
        render();
      }
    });

    /* Thirty-six makers, eighteen of them naming one item: the list needs
       narrowing, and it narrows in place rather than redrawing the popover,
       so a tick already made does not move under the pointer. */
    els.facets.addEventListener("input", function (e) {
      var box = e.target.closest(".facet");
      if (!box || !e.target.classList.contains("fsearch")) return;
      var q = e.target.value.trim().toLowerCase();
      var opts = box.querySelectorAll(".fopt");
      for (var i = 0; i < opts.length; i++) {
        var v = opts[i].querySelector("input").value.toLowerCase();
        /* A ticked value stays visible whatever is typed - hiding one would
           read as having lost it. */
        opts[i].hidden = !!q && v.indexOf(q) < 0 &&
                         !opts[i].querySelector("input").checked;
      }
    });

    els.facets.addEventListener("change", function (e) {
      var cb = e.target.closest('input[type="checkbox"]');
      if (!cb) return;
      var box = cb.closest(".facet");
      state.facets[box.dataset.facet][cb.value] = cb.checked;
      /* The popover stays open: picking two makers in a row is the normal
         thing to do, and closing after each would make it four clicks. The
         counts behind it go stale until it is reopened, which is the price
         of not having the list reorder itself under the pointer. */
      renderShowingAndList();
    });

    els.showing.addEventListener("click", function (e) {
      if (e.target.closest("[data-clear]")) { clearFilters(); return; }
      var pill = e.target.closest("[data-drop]");
      if (!pill) return;
      if (pill.dataset.drop === "q") {
        state.q = "";
        els.search.value = "";
      } else {
        delete state.facets[pill.dataset.drop][pill.dataset.v];
      }
      render();
    });

    /* Anywhere else closes an open facet. Right here and wrong for the
       editing panels: a popover holds nothing anybody typed. */
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".facet")) closeFacets(null);
    });

    /* Opening a datasheet, and closing it. This sat among the filter wiring
       the facet bar replaced and went out with it - every card was inert and
       every test that opens one failed, which is how it was caught. */
    document.addEventListener("click", function (e) {
      var c = e.target.closest(".card, .row");
      if (c) { openSheet(c.dataset.id); return; }
      if (e.target.closest("[data-close]") || e.target === els.scrim) {
        closeSheet();
        return;
      }
      if (e.target.closest("[data-clear]")) clearFilters();
    });

    document.querySelector(".themeq").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-t]");
      if (b) setTheme(b.dataset.t);
    });

    document.querySelector(".viewq").addEventListener("click", function (e) {
      var b = e.target.closest("button[data-v]");
      if (!b || b.dataset.v === state.view) return;
      setView(b.dataset.v);
      render();
    });

    pullToDismiss();

    addEventListener("keydown", function (e) {
      if (e.key === "Escape" && state.open) closeSheet();
      if (e.key === "/" && document.activeElement !== els.search) {
        e.preventDefault(); els.search.focus();
      }
    });
  }

  /* ---------------------------------------------------------------- boot */

  function ready() { document.dispatchEvent(new Event("gp1:ready")); }

  /* ---------------------------------------------------------------- seam

     Everything workflow.js is allowed to touch, and nothing else. Kept
     deliberately small: this file stays the read-only register, and the
     whole of the workflow layer's reach into it is these five entries. */
  var GP1 = window.GP1 = {
    items:   function () { return state.items; },
    open:    function () { return state.open; },
    render:  function () { render(); },
    onSheet: null,          /* workflow.js sets this: fn(item, sheetElement) */

    /* Rebuild the open sheet in place. Signing in or out changes which
       controls belong in it, and the sheet is built once on open. */
    reopen: function () { if (state.open) openSheet(state.open.id); },

    /* item_key -> {status, status_note, ...}. The guard matters: this can
       arrive before the catalogue has finished loading, and rendering 0 of
       139 items would flash "nothing matches that" over a working page. */
    setApproval: function (map) {
      state.approval = map || {};
      if (state.items.length) render();
    }
  };

  function boot(data) {
    state.items = data.items;
    state.groups = data.groups;

    /* A key that names two items cannot carry one item's approval. P9 is the
       live case: JM Micro-Lok fibreglass and poly pipe insulation are
       different products filed under one code. Mark both so the workflow
       layer refuses to attach anything to either, rather than quietly giving
       them a shared status, shared notes and shared invoices.

       The fix is in the source folder, not here: give one of them its own
       number and re-extract. */
    var count = {};
    for (var c = 0; c < state.items.length; c++) {
      count[state.items[c].key] = (count[state.items[c].key] || 0) + 1;
    }
    GP1.ambiguous = [];
    for (var a = 0; a < state.items.length; a++) {
      if (count[state.items[a].key] > 1) {
        state.items[a].shared_key = true;
        if (GP1.ambiguous.indexOf(state.items[a].key) < 0) {
          GP1.ambiguous.push(state.items[a].key);
        }
      }
    }
    if (GP1.ambiguous.length && window.console) {
      console.warn("GP1: these codes name more than one item, so they can " +
                   "carry no status, notes or invoices until renumbered: " +
                   GP1.ambiguous.join(", "));
    }

    els.lede.innerHTML =
      "<h2>Material &amp; Hardware Register</h2>" +
      "<p>" + data.items.length + " items across " +
      data.groups.filter(function (g) { return g.count; }).length +
      " groups for GP1-MUR mockup room 1, each with the manufacturer’s " +
      "datasheet attached. Search it, filter it, open what you need.</p>";

    setView(recall("gp1.view") || "cards");
    render();
    wire();
    setTheme(recall("gp1.theme") || "light");
    ready();
  }

  els.lede = document.getElementById("lede");

  els.list = document.getElementById("list");
  els.count = document.getElementById("count");
  els.search = document.getElementById("q");
  els.facets = document.getElementById("facets");
  els.showing = document.getElementById("showing");
  els.sheet = document.getElementById("sheet");
  els.scrim = document.getElementById("scrim");

  document.getElementById("i-search").innerHTML = I.search;
  var tq = document.querySelectorAll(".themeq button");
  tq[0].innerHTML = icon(I.sun); tq[1].innerHTML = icon(I.moon);
  var vq = document.querySelectorAll(".viewq button");
  vq[0].innerHTML = icon(I.grid); vq[1].innerHTML = icon(I.rows);

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
