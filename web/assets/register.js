/* ==========================================================================
   GP1-MUR Material & Hardware Register.

   Read-only. There is no backend, no sign-in and nothing to save: the whole
   register is data/datasheets.json, generated from the curated PDFs by
   "tools/extract_datasheets.py", which reads the submittal folder. Change a
   datasheet there, re-run that, and this page is correct again — there is no
   second place to update.

   It is a repository, not a workflow. Nothing here nags: no alerts, no status
   badges, no review state. The submittals are settled, and if something about
   the project changes it gets changed at the source and re-extracted. What the
   page owes a reader is a fast way to find an item, see what it looks like,
   read its specification and open its datasheet.
   ========================================================================== */

(function () {
  "use strict";

  var DATA = "./data/datasheets.json";

  var state = { items: [], groups: [], q: "", group: "", maker: "",
               view: "cards", open: null };
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

  function haystack(it) {
    if (it._h) return it._h;
    var parts = [it.code, it.title, it.manufacturer, it.group_name,
                 it.category, it.notes, it.submittal];
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
      if (state.maker && it.manufacturer !== state.maker) return false;
      if (q && haystack(it).indexOf(q) < 0) return false;
      return true;
    });
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
      '<span class="pages">' + it.pages +
      (it.pages === 1 ? " page" : " pages") + "</span>" +
      "</button>";
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

    var btns = els.rail.querySelectorAll("button[data-g]");
    for (var b = 0; b < btns.length; b++) {
      var k = btns[b].dataset.g;
      btns[b].setAttribute("aria-pressed", String(state.group === k));
    }
    if (els.groupsel.value !== state.group) els.groupsel.value = state.group;
  }

  function renderMakers() {
    var seen = {};
    for (var i = 0; i < state.items.length; i++) {
      var m = state.items[i].manufacturer;
      if (m) seen[m] = (seen[m] || 0) + 1;
    }
    var names = Object.keys(seen).sort(function (a, b) {
      return a.localeCompare(b);
    });
    var html = '<option value="">All manufacturers</option>';
    for (var n = 0; n < names.length; n++) {
      html += '<option value="' + esc(names[n]) + '">' + esc(names[n]) +
              " (" + seen[names[n]] + ")</option>";
    }
    els.maker.innerHTML = html;
  }

  function renderRail() {
    var html = "<h3>Groups</h3>" +
      '<button data-g="" aria-pressed="true">All groups<b>' +
      state.items.length + "</b></button>";
    /* The same choice, twice: a rail with room to breathe on a wide screen,
       and a picker on a phone. The rail used to be a horizontal scroll strip
       there, which showed two groups out of ten and gave no hint the rest
       existed - the main way round the register, effectively hidden. */
    var opts = '<option value="">All groups (' + state.items.length + ")</option>";
    for (var i = 0; i < state.groups.length; i++) {
      var g = state.groups[i];
      if (!g.count) continue;
      html += '<button data-g="' + esc(g.key) + '" aria-pressed="false"><kbd>' +
        esc(g.key) + "</kbd> " + esc(g.name) + "<b>" + g.count + "</b></button>";
      opts += '<option value="' + esc(g.key) + '">' + esc(g.name) +
              " (" + g.count + ")</option>";
    }
    els.rail.innerHTML = html;
    els.groupsel.innerHTML = opts;
  }

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

    els.rail.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-g]");
      if (!b) return;
      state.group = b.dataset.g;
      render();
    });

    document.addEventListener("click", function (e) {
      var c = e.target.closest(".card, .row");
      if (c) { openSheet(c.dataset.id); return; }
      if (e.target.closest("[data-close]") || e.target === els.scrim) { closeSheet(); return; }
      if (e.target.closest("[data-clear]")) {
        state.q = ""; state.group = ""; state.maker = "";
        els.search.value = "";
        els.maker.value = "";
        els.groupsel.value = "";
        render();
      }
    });

    els.maker.addEventListener("change", function () {
      state.maker = els.maker.value;
      render();
    });

    els.groupsel.addEventListener("change", function () {
      state.group = els.groupsel.value;
      render();
      els.list.scrollIntoView({ block: "start" });
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

  function boot(data) {
    state.items = data.items;
    state.groups = data.groups;

    els.lede.innerHTML =
      "<h2>Material &amp; Hardware Register</h2>" +
      "<p>" + data.items.length + " items across " +
      data.groups.filter(function (g) { return g.count; }).length +
      " groups for GP1-MUR mockup room 1, each with the manufacturer’s " +
      "datasheet attached. Search it, filter it, open what you need.</p>";

    renderMakers();
    renderRail();
    setView(recall("gp1.view") || "cards");
    render();
    wire();
    setTheme(recall("gp1.theme") || "light");
    ready();
  }

  els.lede = document.getElementById("lede");
  els.rail = document.getElementById("rail");
  els.list = document.getElementById("list");
  els.count = document.getElementById("count");
  els.search = document.getElementById("q");
  els.maker = document.getElementById("maker");
  els.groupsel = document.getElementById("groupsel");
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
