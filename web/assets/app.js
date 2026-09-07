/* ==========================================================================
   GP1-MUR Material & Hardware Register

   A schedule of 199 procurement line items across 13 trades. The page's whole
   job is telling you what has a datasheet behind it and what does not, so
   documentation state is the one thing rendered in colour on every row.

   Structure:
     1  data + vocabulary          5  shell: masthead, rail, toolbar
     2  view state + URL hash      6  views: table, cards, by trade
     3  filter / sort / facets     7  detail sheet + editor
     4  render helpers             8  wiring + boot
   ========================================================================== */

(function () {
  "use strict";

  /* ======================================================================
     1 - DATA + VOCABULARY
     ====================================================================== */

  var SPEC_STATUS = {
    complete: "Have spec sheet",
    in_progress: "Spec sheet in progress",
    not_started: "Spec sheet not started",
    unknown: "Spec sheet not tracked"
  };
  var APPROVED = {
    not_started: "Not started", submitted: "Submitted",
    approved: "Approved", rejected: "Rejected", unknown: "Unknown"
  };
  var PROCURED = {
    not_started: "Not started", quoted: "Quoted", ordered: "Ordered",
    delivered: "Delivered", installed: "Installed", unknown: "Unknown"
  };

  var state = null;
  var derived = [];
  var DISCIPLINE_ORDER = [];

  function deriveAll(items) {
    DISCIPLINE_ORDER = [];
    var seen = {};
    derived = items.map(function (it) {
      if (!seen[it.discipline_code]) {
        seen[it.discipline_code] = 1;
        DISCIPLINE_ORDER.push({ code: it.discipline_code, name: it.discipline });
      }
      var hasSpec = !!it.spec_url, hasFolder = !!it.folder_url;
      return {
        hasSpec: hasSpec,
        hasFolder: hasFolder,
        docState: hasSpec && hasFolder ? "both" : hasSpec ? "spec" : hasFolder ? "folder" : "none",
        blob: stripAccents([
          it.code_tag, it.item, it.sub_category, it.discipline, it.manufacturer,
          it.model, it.location, it.drawing_ref, it.notes
        ].join(" ")).toLowerCase()
      };
    });
    DISCIPLINE_ORDER.sort(function (a, b) { return a.code.localeCompare(b.code); });
  }

  function byId(id) {
    for (var i = 0; i < state.items.length; i++) if (state.items[i].id === id) return i;
    return -1;
  }

  function stripAccents(s) {
    return s.normalize ? s.normalize("NFD").replace(/[̀-ͯ]/g, "") : s;
  }

  /* Does any item anywhere carry a Drive folder? Today none do, and a coverage
     model that speaks of "spec + folder" when folders do not exist reads as a
     page describing data it has not got. The concept stays in the schema and
     in the editor; it simply does not appear until something fills it. */
  function anyFolders() {
    for (var i = 0; i < derived.length; i++) if (derived[i].hasFolder) return true;
    return false;
  }

  /* ======================================================================
     2 - VIEW STATE. Filters live in the URL hash, so a filtered view is a
     shareable link and survives a reload for free.
     ====================================================================== */

  var ui = {
    view: "table",
    q: "",
    disciplines: [],
    doc: "all",
    sub: "",
    location: "",
    manufacturer: "",
    approved: "",
    procured: "",
    sort: "seq",
    showFilters: false
  };

  function remember(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function recall(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  function defaultView() {
    return window.matchMedia("(min-width: 900px)").matches ? "table" : "cards";
  }

  function readHash() {
    var h = location.hash.replace(/^#/, "");
    if (!h) return false;
    var got = false;
    h.split("&").forEach(function (pair) {
      var i = pair.indexOf("=");
      if (i < 0) return;
      var k = pair.slice(0, i), v = decodeURIComponent(pair.slice(i + 1).replace(/\+/g, " "));
      if (k === "v" && /^(table|cards|acc)$/.test(v)) { ui.view = v; got = true; }
      else if (k === "q") { ui.q = v; got = true; }
      else if (k === "d") { ui.disciplines = v ? v.split(",") : []; got = true; }
      else if (k === "doc") { ui.doc = v; got = true; }
      else if (k === "sub") { ui.sub = v; got = true; }
      else if (k === "loc") { ui.location = v; got = true; }
      else if (k === "mfr") { ui.manufacturer = v; got = true; }
      else if (k === "ap") { ui.approved = v; got = true; }
      else if (k === "pr") { ui.procured = v; got = true; }
      else if (k === "sort") { ui.sort = v; got = true; }
    });
    return got;
  }

  var writingHash = false;
  function writeHash() {
    var p = ["v=" + ui.view];
    if (ui.q) p.push("q=" + encodeURIComponent(ui.q));
    if (ui.disciplines.length) p.push("d=" + ui.disciplines.join(","));
    if (ui.doc !== "all") p.push("doc=" + ui.doc);
    if (ui.sub) p.push("sub=" + encodeURIComponent(ui.sub));
    if (ui.location) p.push("loc=" + encodeURIComponent(ui.location));
    if (ui.manufacturer) p.push("mfr=" + encodeURIComponent(ui.manufacturer));
    if (ui.approved) p.push("ap=" + ui.approved);
    if (ui.procured) p.push("pr=" + ui.procured);
    if (ui.sort !== "seq") p.push("sort=" + ui.sort);
    writingHash = true;
    history.replaceState(null, "", "#" + p.join("&"));
    setTimeout(function () { writingHash = false; }, 0);
  }

  /* ======================================================================
     3 - FILTER / SORT / FACET COUNTS (pure)
     ====================================================================== */

  function matches(it, d, opts) {
    if (opts.doc) {
      if (ui.doc === "missing" && d.docState !== "none") return false;
      if (ui.doc === "spec" && !d.hasSpec) return false;
      if (ui.doc === "folder" && !d.hasFolder) return false;
      if (ui.doc === "both" && d.docState !== "both") return false;
      if (ui.doc === "any" && d.docState === "none") return false;
    }
    if (opts.disc && ui.disciplines.length && ui.disciplines.indexOf(it.discipline_code) < 0) return false;
    if (ui.sub && it.sub_category !== ui.sub) return false;
    if (ui.location && it.location !== ui.location) return false;
    if (ui.manufacturer && it.manufacturer !== ui.manufacturer) return false;
    if (ui.approved && it.approved !== ui.approved) return false;
    if (ui.procured && it.procured !== ui.procured) return false;
    if (ui.q) {
      var terms = stripAccents(ui.q).toLowerCase().split(/\s+/).filter(Boolean);
      for (var i = 0; i < terms.length; i++) if (d.blob.indexOf(terms[i]) < 0) return false;
    }
    return true;
  }

  function currentRows() {
    var rows = [];
    for (var i = 0; i < state.items.length; i++) {
      if (matches(state.items[i], derived[i], { doc: true, disc: true })) {
        rows.push({ it: state.items[i], d: derived[i] });
      }
    }
    var s = ui.sort;
    if (s === "item") rows.sort(function (a, b) { return a.it.item.localeCompare(b.it.item); });
    else if (s === "mfr") rows.sort(function (a, b) {
      return (a.it.manufacturer || "￿").localeCompare(b.it.manufacturer || "￿") || a.it.seq - b.it.seq;
    });
    else if (s === "gaps") rows.sort(function (a, b) {
      return (rank(a.d.docState) - rank(b.d.docState)) || a.it.seq - b.it.seq;
    });
    else rows.sort(function (a, b) { return a.it.seq - b.it.seq; });
    return rows;
  }
  function rank(s) { return s === "none" ? 0 : s === "both" ? 2 : 1; }

  /* Facet counts ignore their own dimension, so a control always shows what
     picking it would actually yield. */
  function disciplineCounts() {
    var out = {};
    for (var i = 0; i < state.items.length; i++) {
      var it = state.items[i];
      if (matches(it, derived[i], { doc: true, disc: false })) {
        var e = out[it.discipline_code] || (out[it.discipline_code] = { n: 0, doc: 0 });
        e.n++;
        if (derived[i].docState !== "none") e.doc++;
      }
    }
    return out;
  }

  function docCounts() {
    var out = { all: 0, missing: 0, spec: 0, folder: 0, both: 0, any: 0 };
    for (var i = 0; i < state.items.length; i++) {
      var d = derived[i];
      if (!matches(state.items[i], d, { doc: false, disc: true })) continue;
      out.all++;
      if (d.docState === "none") out.missing++; else out.any++;
      if (d.hasSpec) out.spec++;
      if (d.hasFolder) out.folder++;
      if (d.docState === "both") out.both++;
    }
    return out;
  }

  function distinct(field) {
    var seen = {}, out = [];
    state.items.forEach(function (it) {
      var v = it[field];
      if (v && !seen[v]) { seen[v] = 1; out.push(v); }
    });
    return out.sort(function (a, b) { return a.localeCompare(b); });
  }

  function activeFilterCount() {
    return ui.disciplines.length + (ui.doc !== "all" ? 1 : 0) +
      (ui.sub ? 1 : 0) + (ui.location ? 1 : 0) + (ui.manufacturer ? 1 : 0) +
      (ui.approved ? 1 : 0) + (ui.procured ? 1 : 0);
  }

  /* ======================================================================
     4 - RENDER HELPERS
     ====================================================================== */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  var attr = esc;

  function dash() { return '<span class="dash">—</span>'; }

  var ICON = {
    search: '<svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14"/></svg>',
    ext: '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4.5 2h5.5v5.5M10 2 5 7"/><path d="M8 8.5V10H2V4h1.5"/></svg>',
    doc: '<svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M3 1.5h5L11 5v7.5H3z"/><path d="M8 1.5V5h3"/></svg>',
    folder: '<svg width="13" height="13" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M1.5 3.5h4l1 1.5h6v6h-11z"/></svg>',
    table: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1.5" y="2.5" width="13" height="11"/><path d="M1.5 6h13M6 6v7.5"/></svg>',
    cards: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1.5" y="2.5" width="5.5" height="5"/><rect x="9" y="2.5" width="5.5" height="5"/><rect x="1.5" y="9" width="5.5" height="4.5"/><rect x="9" y="9" width="5.5" height="4.5"/></svg>',
    list: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 4h12M2 8h12M2 12h12"/></svg>',
    caret: '<svg class="acc-caret" width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 2.5 8 6l-4 3.5"/></svg>',
    close: '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3l8 8M11 3l-8 8"/></svg>',
    sun: '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.6M8 13.4V15M15 8h-1.6M2.6 8H1M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1M12.9 12.9l-1.1-1.1M4.2 4.2 3.1 3.1"/></svg>',
    moon: '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1Z"/></svg>',
    auto: '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="2.5" width="13" height="9" rx="1"/><path d="M5.5 14h5"/></svg>'
  };

  function qty(it) {
    if (it.qty === null || it.qty === undefined) return esc(it.qty_raw || "");
    return esc(String(it.qty)) + (it.unit ? " " + esc(it.unit) : "");
  }

  /* The location column repeats the item name on the Stone and Plaster sheets,
     where the workbook put the zone list in both fields. Say it once. */
  function siteLocation(it) {
    var loc = it.location || "";
    if (!loc) return "";
    if (it.item && it.item.toLowerCase().indexOf(loc.toLowerCase()) >= 0) return "";
    return loc;
  }

  /* Manufacturer and model are two different facts. Separate them, and set the
     model in mono - it is the value someone retypes into a supplier enquiry. */
  function maker(it) {
    if (!it.manufacturer && !it.model) return "";
    var h = "";
    if (it.manufacturer) h += esc(it.manufacturer);
    if (it.manufacturer && it.model) h += '<br>';
    if (it.model) h += '<span class="m">' + esc(it.model) + "</span>";
    return h;
  }

  /* spec_status is not a column, but it earns its keep here: it turns a blank
     into a reason, which is what makes the chase list actionable. */
  function noDocReason(it) {
    if (it.spec_status === "complete") return "Spec sheet held, not linked";
    if (it.spec_status === "in_progress") return "Spec sheet being chased";
    return "No datasheet yet";
  }

  function isDefaultStatus(v) { return !v || v === "not_started" || v === "unknown"; }

  function pill(value, map) {
    return '<span class="pill p-' + esc(value) + '">' + esc(map[value] || value) + "</span>";
  }

  function docMark(d, it) {
    var on = d.docState !== "none";
    return '<span class="docmark' + (on ? "" : " none") + '" title="' +
      attr(on ? "Datasheet linked" : noDocReason(it)) + '"></span>';
  }

  function docLinks(it) {
    var h = '<div class="doclinks">';
    if (it.spec_url) {
      h += '<a class="doclink" href="' + attr(it.spec_url) + '" target="_blank" rel="noopener noreferrer">' +
        ICON.doc + "Datasheet" + ICON.ext + "</a>";
    }
    if (it.folder_url) {
      h += '<a class="doclink" href="' + attr(it.folder_url) + '" target="_blank" rel="noopener noreferrer">' +
        ICON.folder + "Folder" + ICON.ext + "</a>";
    }
    if (!it.spec_url && !it.folder_url) {
      h += '<span class="docnone">' + esc(noDocReason(it)) + "</span>";
    }
    return h + "</div>";
  }

  /* ======================================================================
     5 - SHELL
     ====================================================================== */

  function shell() {
    return masthead() +
      '<div class="layout">' +
        '<aside class="rail" id="rail"></aside>' +
        '<div class="content">' +
          '<div class="toolbar" id="toolbar"></div>' +
          '<div id="banner"></div>' +
          '<div class="resultbar" id="resultbar"></div>' +
          '<main id="results" tabindex="-1"></main>' +
          footer() +
        "</div>" +
      "</div>" +
      '<dialog id="sheet" aria-labelledby="sheet-title"></dialog>';
  }

  function masthead() {
    var m = state.meta || {};
    return '<header class="masthead"><div class="mast-inner">' +
      "<div>" +
        '<p class="eyebrow label">' + esc(m.project || "GP1") + " · Procurement</p>" +
        '<h1 class="mast-title">' + esc(m.title || "Material & Hardware Register") + "</h1>" +
        '<div class="mast-rule"></div>' +
        '<div class="mast-meta">' +
          "<span><b>" + state.items.length + "</b> items</span>" +
          "<span><b>" + DISCIPLINE_ORDER.length + "</b> trades</span>" +
          "<span>rev <b>" + esc(String(m.rev || 1)) + "</b></span>" +
          "<span>updated <b>" + esc((m.updated_at || "").slice(0, 10)) + "</b></span>" +
        "</div>" +
      "</div>" +
      '<div class="mast-side">' + themeSwitch() + coverage() + "</div>" +
      "</div></header>";
  }

  function themeSwitch() {
    var cur = recall("gp1.theme") || "auto";
    function b(v, icon, label) {
      return '<button type="button" data-theme-set="' + v + '" aria-pressed="' +
        (cur === v ? "true" : "false") + '" title="' + label + '">' + icon +
        '<span class="vh">' + label + "</span></button>";
    }
    return '<div class="themeswitch" role="group" aria-label="Colour theme">' +
      b("light", ICON.sun, "Light") + b("auto", ICON.auto, "Match system") + b("dark", ICON.moon, "Dark") +
      "</div>";
  }

  /* Coverage: the number the owner leads with. Documented means a datasheet
     OR a folder - which is what the SQL view computes too - and it is rendered
     as the good news it is, not as a warning. */
  function coverage() {
    var both = 0, part = 0, n = derived.length;
    derived.forEach(function (d) {
      if (d.docState === "both") both++;
      else if (d.docState !== "none") part++;
    });
    var documented = both + part;
    var pct = n ? Math.round(documented / n * 100) : 0;
    var folders = anyFolders();

    var bar = folders
      ? '<i class="b-both" style="width:' + (both / n * 100) + '%"></i>' +
        '<i class="b-part" style="width:' + (part / n * 100) + '%"></i>'
      : '<i class="b-both" style="width:' + (n ? documented / n * 100 : 0) + '%"></i>';

    var key = folders
      ? key1("both", "var(--ok)", "Datasheet + folder", both) +
        key1("any", "color-mix(in srgb, var(--ok) 55%, var(--surface-3))", "One of the two", part) +
        key1("missing", "var(--surface-3)", "Nothing yet", n - documented)
      : key1("any", "var(--ok)", "Datasheet held", documented) +
        key1("missing", "var(--surface-3)", "Nothing yet", n - documented);

    return '<div class="stat">' +
      '<div class="stat-top"><span class="stat-fig">' + pct + '%</span>' +
      '<span class="stat-of"><span class="label" style="display:block">Documented</span>' +
      "<b>" + documented + "</b> of " + n + "</span></div>" +
      '<div class="stat-bar" role="img" aria-label="' + documented + " of " + n +
      ' items have documentation">' + bar + "</div>" +
      '<div class="stat-key">' + key + "</div></div>";
  }

  function key1(filter, colour, label, count) {
    return '<button type="button" data-doc="' + filter + '" title="Filter the register to these items">' +
      '<i style="background:' + colour + '"></i>' + label + " <b>" + count + "</b></button>";
  }

  /* --- discipline rail: the dominant filter, given permanent shape --- */
  function rail() {
    var dc = disciplineCounts();
    var total = 0, totalDoc = 0;
    DISCIPLINE_ORDER.forEach(function (d) {
      var e = dc[d.code]; if (e) { total += e.n; totalDoc += e.doc; }
    });

    var h = '<div class="rail-head label">Trades</div><ul class="rail-list">';
    h += '<li class="rail-all"><button type="button" class="rail-item" data-disc-all aria-pressed="' +
      (ui.disciplines.length ? "false" : "true") + '">' +
      '<span class="rail-swatch"></span><span class="rail-name">All trades</span>' +
      '<span class="rail-n">' + total + "</span></button></li>";

    DISCIPLINE_ORDER.forEach(function (d) {
      var e = dc[d.code] || { n: 0, doc: 0 };
      var on = ui.disciplines.indexOf(d.code) >= 0;
      h += '<li data-disc="' + attr(d.code) + '"><button type="button" class="rail-item" data-disc="' +
        attr(d.code) + '" aria-pressed="' + (on ? "true" : "false") +
        '" title="' + attr(e.doc + " of " + e.n + " documented") + '">' +
        '<span class="rail-swatch"></span>' +
        '<span class="rail-name">' + esc(d.name) + "</span>" +
        '<span class="rail-n">' + e.n + "</span>" +
        '<span class="rail-bar"><i style="width:' + (e.n ? e.doc / e.n * 100 : 0) + '%"></i></span>' +
        "</button></li>";
    });
    return h + "</ul>";
  }

  function toolbar() {
    return '<div class="tb-row">' +
      '<label class="search">' + ICON.search +
      '<input id="q" type="search" placeholder="Search items, tags, manufacturers…" value="' +
      attr(ui.q) + '" aria-label="Search the register"></label>' +
      '<div class="seg" role="group" aria-label="View">' +
        viewBtn("table", ICON.table, "Table") +
        viewBtn("cards", ICON.cards, "Cards") +
        viewBtn("acc", ICON.list, "By trade") +
      "</div>" +
      '<button type="button" class="btn" id="filters-toggle" aria-pressed="' +
      (ui.showFilters ? "true" : "false") + '">Filters' +
      (activeFilterCount() ? ' <span class="count">' + activeFilterCount() + "</span>" : "") + "</button>" +
      '<span class="spacer"></span>' +
      '<span id="actions"></span>' +
      "</div>" +
      '<div id="filterpanel">' + (ui.showFilters ? filterPanel() : "") + "</div>";
  }

  function viewBtn(v, icon, label) {
    return '<button type="button" data-view="' + v + '" aria-pressed="' +
      (ui.view === v ? "true" : "false") + '" title="' + label + '">' + icon +
      '<span class="lbl">' + label + "</span></button>";
  }

  function filterPanel() {
    var doc = docCounts();
    var folders = anyFolders();
    var h = '<div class="filters">';

    h += '<div class="fgroup"><div class="label">Documentation</div><div class="chips">' +
      docChip("all", "All items", doc.all) +
      docChip("missing", "Missing", doc.missing) +
      docChip("any", "Documented", doc.any);
    /* The folder chips describe a dimension that does not exist yet on this
       project. Showing them at a permanent zero is a dead control. */
    if (folders) {
      h += docChip("spec", "Has datasheet", doc.spec) +
           docChip("folder", "Has folder", doc.folder) +
           docChip("both", "Has both", doc.both);
    }
    h += "</div></div>";

    h += '<div class="fgroup"><div class="label">Narrow by</div><div class="selects">' +
      sel("sub", "Sub-category", distinct("sub_category"), ui.sub) +
      sel("loc", "Location / zone", distinct("location"), ui.location) +
      sel("mfr", "Manufacturer", distinct("manufacturer"), ui.manufacturer) +
      selMap("ap", "Approved", APPROVED, ui.approved) +
      selMap("pr", "Procured", PROCURED, ui.procured) +
      selSort() +
      "</div></div>";

    h += '<div><button type="button" class="btn" id="clear">Clear all filters</button></div>';
    return h + "</div>";
  }

  function docChip(v, label, n) {
    return '<button type="button" class="chip" data-doc="' + v + '" aria-pressed="' +
      (ui.doc === v ? "true" : "false") + '">' + label + '<span class="n">' + n + "</span></button>";
  }
  function sel(name, label, values, current) {
    var h = '<label><span class="label">' + label + '</span><select data-sel="' + name +
      '"><option value="">Any</option>';
    values.forEach(function (v) {
      h += '<option value="' + attr(v) + '"' + (v === current ? " selected" : "") + ">" + esc(v) + "</option>";
    });
    return h + "</select></label>";
  }
  function selMap(name, label, map, current) {
    var h = '<label><span class="label">' + label + '</span><select data-sel="' + name +
      '"><option value="">Any</option>';
    Object.keys(map).forEach(function (k) {
      h += '<option value="' + k + '"' + (k === current ? " selected" : "") + ">" + esc(map[k]) + "</option>";
    });
    return h + "</select></label>";
  }
  function selSort() {
    var opts = [["seq", "Schedule order"], ["gaps", "Missing docs first"],
                ["item", "Item A–Z"], ["mfr", "Manufacturer"]];
    var h = '<label><span class="label">Sort</span><select data-sel="sort">';
    opts.forEach(function (o) {
      h += '<option value="' + o[0] + '"' + (ui.sort === o[0] ? " selected" : "") + ">" + o[1] + "</option>";
    });
    return h + "</select></label>";
  }

  function footer() {
    var m = state.meta || {};
    return "<footer>" +
      '<span class="mono">rev ' + esc(String(m.rev || 1)) + " · updated " +
      esc((m.updated_at || "").slice(0, 10)) + "</span>" +
      "<span>Source: " + esc(m.source || "procurement tracker") + "</span>" +
      '<span id="src-note"></span>' +
      '<span class="spacer"></span>' +
      '<span><button type="button" class="linky" data-dl="csv">Download CSV</button>' +
      ' <span class="sep">·</span> ' +
      '<button type="button" class="linky" data-dl="json">Download JSON</button></span>' +
      "</footer>";
  }

  /* ======================================================================
     6 - VIEWS
     ====================================================================== */

  /* Columns declare when they apply and how wide they are, so the table can
     drop what is empty and what will not fit instead of scrolling sideways.
     `has` is evaluated against the VISIBLE rows: Approved and Procured read
     not_started on all 199 items today, so they simply are not columns - and
     they come back the moment anyone fills one in. */
  var COLUMNS = [
    { key: "code_tag", label: "Tag", cls: "c-code", w: 118, min: 0,
      has: function (it) { return !!it.code_tag; },
      cell: function (it) { return esc(it.code_tag); } },

    { key: "item", label: "Item", cls: "c-item", w: null, min: 0,
      has: function () { return true; },
      cell: function (it) {
        return "<strong>" + esc(it.item) + "</strong>" +
          (it.sub_category ? '<div class="sub">' + esc(it.sub_category) + "</div>" : "");
      } },

    { key: "manufacturer", label: "Manufacturer", cls: "c-mfr", w: 190, min: 820,
      has: function (it) { return !!(it.manufacturer || it.model); },
      cell: maker },

    { key: "qty", label: "Qty", cls: "c-num", w: 88, min: 900,
      has: function (it) { return it.qty !== null && it.qty !== undefined || !!it.qty_raw; },
      cell: function (it) { return qty(it) || dash(); } },

    { key: "location", label: "Location", cls: "c-loc", w: 132, min: 1120,
      has: function (it) { return !!siteLocation(it); },
      cell: function (it) { return esc(siteLocation(it)) || dash(); } },

    { key: "notes", label: "Notes", cls: "c-notes", w: 200, min: 1360,
      has: function (it) { return !!it.notes; },
      cell: function (it) { return esc(it.notes) || dash(); } },

    { key: "drawing_ref", label: "Drawing", cls: "c-code", w: 108, min: 1500,
      has: function (it) { return !!it.drawing_ref; },
      cell: function (it) { return esc(it.drawing_ref) || dash(); } },

    { key: "approved", label: "Approved", cls: "c-status", w: 122, min: 1200,
      has: function (it) { return !isDefaultStatus(it.approved); },
      cell: function (it) { return isDefaultStatus(it.approved) ? dash() : pill(it.approved, APPROVED); } },

    { key: "procured", label: "Procured", cls: "c-status", w: 122, min: 1200,
      has: function (it) { return !isDefaultStatus(it.procured); },
      cell: function (it) { return isDefaultStatus(it.procured) ? dash() : pill(it.procured, PROCURED); } },

    /* Always present: it is what the page is for. */
    { key: "doc", label: "Docs", cls: "c-doc", w: 64, min: 0,
      has: function () { return true; },
      cell: function (it, d) { return docMark(d, it); } }
  ];

  function activeColumns(rows) {
    var w = window.innerWidth;
    return COLUMNS.filter(function (c) {
      if (w < c.min) return false;
      for (var i = 0; i < rows.length; i++) if (c.has(rows[i].it)) return true;
      return false;
    });
  }

  var lastColumnKeys = "";

  function tableView(rows) {
    var cols = activeColumns(rows);
    lastColumnKeys = cols.map(function (c) { return c.key; }).join(",");

    var h = '<div class="tablewrap"><table><colgroup>';
    cols.forEach(function (c) { h += "<col" + (c.w ? ' style="width:' + c.w + 'px"' : "") + ">"; });
    h += "</colgroup><thead><tr>";
    cols.forEach(function (c) { h += '<th class="' + c.cls + '">' + esc(c.label) + "</th>"; });
    h += "</tr></thead><tbody>";

    var lastDisc = null, alt = false;
    var grouped = ui.sort === "seq";

    rows.forEach(function (r) {
      var it = r.it;
      if (grouped && it.discipline_code !== lastDisc) {
        lastDisc = it.discipline_code;
        alt = false;
        var n = 0;
        rows.forEach(function (x) { if (x.it.discipline_code === lastDisc) n++; });
        h += '<tr class="grouprow" data-disc="' + attr(lastDisc) + '"><th colspan="' + cols.length + '">' +
          esc(it.discipline) + '<span class="gcount">' + n + " items</span></th></tr>";
      }
      /* Zebra is emitted, never nth-child: the group rows break parity. */
      h += '<tr class="row' + (alt ? " alt" : "") + '" data-disc="' + attr(it.discipline_code) +
        '" data-id="' + attr(it.id) + '" tabindex="0">';
      alt = !alt;
      cols.forEach(function (c) {
        h += '<td class="' + c.cls + '">' + (c.cell(it, r.d) || dash()) + "</td>";
      });
      h += "</tr>";
    });

    return h + "</tbody></table></div>";
  }

  function cardsView(rows) {
    var h = '<div class="cards">';
    rows.forEach(function (r) {
      var it = r.it;
      var bits = [];
      var q = qty(it);
      if (q) bits.push('<span class="num">' + q + "</span>");
      if (siteLocation(it)) bits.push(esc(siteLocation(it)));
      if (it.drawing_ref) bits.push('<span class="mono">' + esc(it.drawing_ref) + "</span>");

      h += '<button type="button" class="card" data-disc="' + attr(it.discipline_code) +
        '" data-id="' + attr(it.id) + '">' +
        '<span class="card-top"><span class="card-disc">' + esc(it.discipline) + "</span>" +
        '<span class="card-code">' + esc(it.code_tag || "") + "</span></span>" +
        '<span class="card-title">' + esc(it.item) + "</span>" +
        (maker(it) ? '<span class="card-mfr">' + maker(it) + "</span>" : "") +
        (bits.length ? '<span class="card-line">' + bits.join(' <span class="sep">·</span> ') + "</span>" : "") +
        (it.notes ? '<span class="card-note">' + esc(it.notes) + "</span>" : "") +
        '<span class="card-foot">' + docMark(r.d, it) +
        '<span class="card-line">' + esc(r.d.docState === "none" ? noDocReason(it) : "Datasheet linked") + "</span>" +
        (isDefaultStatus(it.approved) ? "" : pill(it.approved, APPROVED)) +
        (isDefaultStatus(it.procured) ? "" : pill(it.procured, PROCURED)) +
        "</span></button>";
    });
    return h + "</div>";
  }

  function accView(rows) {
    var groups = {};
    rows.forEach(function (r) {
      (groups[r.it.discipline_code] = groups[r.it.discipline_code] || []).push(r);
    });
    var h = '<div class="acc">';
    DISCIPLINE_ORDER.forEach(function (d) {
      var g = groups[d.code];
      if (!g) return;
      var done = g.filter(function (r) { return r.d.docState !== "none"; }).length;
      h += '<details class="disc" data-disc="' + attr(d.code) + '"' + (g.length <= 12 ? " open" : "") +
        "><summary>" + ICON.caret +
        '<span class="acc-name">' + esc(d.name) + "</span>" +
        '<span class="acc-bar" role="img" aria-label="' + done + " of " + g.length + ' documented">' +
        '<i style="width:' + (done / g.length * 100) + '%"></i></span>' +
        '<span class="acc-n">' + done + "/" + g.length + " documented</span>" +
        '</summary><div class="acc-body">';
      g.forEach(function (r) {
        var it = r.it;
        var meta = [];
        if (it.manufacturer) meta.push(esc(it.manufacturer));
        if (it.model) meta.push('<span class="mono">' + esc(it.model) + "</span>");
        if (siteLocation(it)) meta.push(esc(siteLocation(it)));
        var q = qty(it);
        if (q) meta.push('<span class="num">' + q + "</span>");
        h += '<button type="button" class="acc-item" data-id="' + attr(it.id) + '">' +
          '<span class="acc-item-top"><span class="t">' + esc(it.item) + "</span>" +
          '<span class="card-code">' + esc(it.code_tag || "") + "</span></span>" +
          (meta.length ? '<span class="acc-meta">' + meta.join(' <span class="sep">·</span> ') + "</span>" : "") +
          '<span class="card-foot">' + docMark(r.d, it) +
          '<span class="card-line">' + esc(r.d.docState === "none" ? noDocReason(it) : "Datasheet linked") +
          "</span></span></button>";
      });
      h += "</div></details>";
    });
    return h + "</div>";
  }

  function renderResults() {
    var rows = currentRows();
    var missing = rows.filter(function (r) { return r.d.docState === "none"; }).length;

    document.getElementById("resultbar").innerHTML =
      "<span><b>" + rows.length + "</b> of " + state.items.length + " items</span>" +
      (missing ? "<span><b>" + missing + "</b> with no documentation</span>" : "") +
      (ui.q ? "<span>matching “" + esc(ui.q) + "”</span>" : "");

    var host = document.getElementById("results");
    if (!rows.length) {
      host.innerHTML = '<div class="empty"><p>No items match these filters.</p>' +
        '<button type="button" class="btn" id="clear2">Clear all filters</button></div>';
      return;
    }
    host.innerHTML = ui.view === "table" ? tableView(rows)
      : ui.view === "cards" ? cardsView(rows) : accView(rows);
    measureHead();
  }

  /* The discipline band stacks under the column head, so it needs the head's
     real height - which depends on whether the web font actually arrived. */
  function measureHead() {
    var th = document.querySelector("thead th");
    document.documentElement.style.setProperty(
      "--thead-h", th ? Math.round(th.getBoundingClientRect().height) + "px" : "0px");
  }

  /* ======================================================================
     7 - DETAIL SHEET. One item at a time. A reader sees the facts; an editor
     sees the same fields behind an explicit Save.
     ====================================================================== */

  var sheetId = null;
  var editing = false;

  function openSheet(id) {
    var i = byId(id);
    if (i < 0) return;
    sheetId = id;
    editing = false;
    renderSheet();
    var dlg = document.getElementById("sheet");
    if (!dlg.open) dlg.showModal();
  }

  function renderSheet() {
    var i = byId(sheetId);
    if (i < 0) return;
    var it = state.items[i], d = derived[i];
    var dlg = document.getElementById("sheet");
    dlg.setAttribute("data-disc", it.discipline_code);

    var head = '<div class="sheet-head"><div class="top"><div>' +
      '<div class="sheet-disc">' + esc(it.discipline) +
      (it.sub_category ? " · " + esc(it.sub_category) : "") + "</div>" +
      '<h2 class="sheet-title" id="sheet-title">' + esc(it.item) + "</h2>" +
      (it.code_tag ? '<div class="sheet-code">' + esc(it.code_tag) + "</div>" : "") +
      "</div>" +
      '<button type="button" class="sheet-close" id="sheet-close" aria-label="Close">' +
      ICON.close + "</button></div></div>";

    var body = editing ? editorBody(it) : detailBody(it, d);

    var foot;
    if (editing) {
      foot = '<span class="note">' +
        (window.Store.writeState() === "reader" ? "This deployment is read-only for your account." : "") +
        "</span>" +
        '<button type="button" class="btn" id="ed-cancel">Cancel</button>' +
        '<button type="button" class="btn btn-primary" id="ed-save">Save item</button>';
    } else {
      foot = '<span class="note"></span>' +
        (window.Store.canOfferEditing()
          ? '<button type="button" class="btn" id="ed-open">Edit item</button>' : "") +
        '<button type="button" class="btn" id="sheet-done">Close</button>';
    }

    dlg.innerHTML = head + '<div class="sheet-body">' + body + "</div>" +
      '<div class="sheet-foot">' + foot + "</div>";
  }

  function detailBody(it, d) {
    var h = docLinks(it);

    var facts = [];
    function f(label, value) { if (value) facts.push([label, value]); }
    f("Manufacturer", esc(it.manufacturer));
    f("Model / SKU", it.model ? '<span class="mono">' + esc(it.model) + "</span>" : "");
    f("Quantity", qty(it) ? '<span class="num">' + qty(it) + "</span>" : "");
    f("Location / zone", esc(it.location));
    f("Drawing", it.drawing_ref ? '<span class="mono">' + esc(it.drawing_ref) + "</span>" : "");
    f("Spec sheet", esc(SPEC_STATUS[it.spec_status] || it.spec_status));
    f("Approved", isDefaultStatus(it.approved) ? "" : pill(it.approved, APPROVED));
    f("Procured", isDefaultStatus(it.procured) ? "" : pill(it.procured, PROCURED));
    f("Notes", esc(it.notes));
    f("Source", esc(it.source_sheet + " row " + it.source_row));

    h += '<dl class="facts">';
    facts.forEach(function (p) {
      h += '<div class="fact"><dt>' + p[0] + "</dt><dd>" + p[1] + "</dd></div>";
    });
    return h + "</dl>";
  }

  function editorBody(it) {
    var f = "";
    f += '<div class="ed-grid two">' +
      textField("code_tag", "Code / tag", it.code_tag, true) +
      textField("sub_category", "Sub-category", it.sub_category) + "</div>";
    f += textField("item", "Item / description", it.item);
    f += '<div class="ed-grid two">' +
      textField("location", "Location / zone", it.location) +
      textField("manufacturer", "Manufacturer / brand", it.manufacturer) + "</div>";
    f += '<div class="ed-grid two">' +
      textField("model", "Model / SKU", it.model, true) +
      textField("drawing_ref", "Drawing reference", it.drawing_ref, true) + "</div>";
    f += '<div class="ed-grid two">' +
      textField("qty", "Qty", it.qty === null || it.qty === undefined ? (it.qty_raw || "") : it.qty) +
      textField("unit", "Unit", it.unit) + "</div>";
    f += textField("spec_url", "Datasheet URL", it.spec_url, true);
    f += textField("folder_url", "Drive folder URL", it.folder_url, true);
    f += '<div class="ed-grid two">' +
      selectField("approved", "Approved", APPROVED, it.approved) +
      selectField("procured", "Procured", PROCURED, it.procured) + "</div>";
    f += selectField("spec_status", "Spec sheet status", SPEC_STATUS, it.spec_status);
    f += '<label class="field"><span>Notes</span><textarea data-f="notes">' + esc(it.notes) + "</textarea></label>";
    return f;
  }

  function textField(key, label, value, mono) {
    return '<label class="field"><span>' + label + "</span>" +
      '<input type="text" data-f="' + key + '" value="' + attr(value == null ? "" : value) + '"' +
      (mono ? ' class="mono-in"' : "") + "></label>";
  }
  function selectField(key, label, map, current) {
    var h = '<label class="field"><span>' + label + '</span><select data-f="' + key + '">';
    Object.keys(map).forEach(function (k) {
      h += '<option value="' + k + '"' + (k === current ? " selected" : "") + ">" + esc(map[k]) + "</option>";
    });
    return h + "</select></label>";
  }

  function saveSheet() {
    if (!sheetId) return;
    var fields = {};
    var inputs = document.querySelectorAll("#sheet [data-f]");
    Array.prototype.forEach.call(inputs, function (el) {
      fields[el.getAttribute("data-f")] = el.value.trim();
    });

    var q = fields.qty;
    if (q === "") { fields.qty = null; fields.qty_raw = null; }
    else if (isFinite(Number(q))) { fields.qty = Number(q); fields.qty_raw = null; }
    else { fields.qty_raw = q; fields.qty = null; }

    ["spec_url", "folder_url"].forEach(function (k) {
      var v = fields[k];
      if (v && !/^https?:\/\//i.test(v)) fields[k] = "https://" + v.replace(/^\/+/, "");
    });

    window.Store.patch(sheetId, fields);
    editing = false;
    renderSheet();
    render();

    window.Store.flush().then(function (r) {
      if (r === "saved") toast("Saved");
      else if (r === "read_only") showReadOnly();
      else if (r === "no_backend") toast("No database is connected, so the change is on screen only.");
      else if (r === "error") toast("Couldn’t save just now. Your change is still on screen — try again.");
    }, function () {});
  }

  function showReadOnly() {
    document.getElementById("banner").innerHTML =
      '<div class="banner read-only"><div><b>This is a read-only view.</b> ' +
      "Your change wasn’t saved. The register is maintained by the project team — " +
      "the item still shows your edit on screen until you reload.</div></div>";
    render();
  }

  /* ======================================================================
     8 - WIRING + BOOT
     ====================================================================== */

  function renderActions() {
    var host = document.getElementById("actions");
    if (!host) return;
    var n = window.Store.dirtyCount();
    var h = "";

    if (window.Store.configured()) {
      if (!window.Store.user()) {
        h += '<button type="button" class="btn" id="signin">Sign in to edit</button>';
      } else if (n) {
        h += '<button type="button" class="btn btn-primary" id="save">Save ' + n +
          " change" + (n > 1 ? "s" : "") + "</button>";
      } else {
        h += '<button type="button" class="btn btn-quiet" id="signout" title="' +
          attr(window.Store.user().email || "") + '">Sign out</button>';
      }
    }
    host.innerHTML = h;

    var note = document.getElementById("src-note");
    if (note) {
      note.textContent = window.Store.source() === "supabase"
        ? "Live from Supabase" : "From the committed seed";
    }
  }

  function toast(msg) {
    var el = document.getElementById("toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast";
      el.className = "toast";
      el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.display = "";
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.style.display = "none"; }, 3800);
  }

  function download(kind) {
    var name = "gp1-mur-register-rev" + ((state.meta && state.meta.rev) || 1);
    var data = kind === "json" ? JSON.stringify(state, null, 2) : toCsv(state.items);
    var blob = new Blob([data], {
      type: kind === "json" ? "application/json" : "text/csv;charset=utf-8"
    });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name + "." + kind;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function toCsv(items) {
    var cols = ["seq", "discipline", "sub_category", "code_tag", "item", "location",
      "manufacturer", "model", "qty", "unit", "drawing_ref", "spec_url", "folder_url",
      "spec_status", "approved", "procured", "notes"];
    var lines = [cols.join(",")];
    items.forEach(function (it) {
      lines.push(cols.map(function (c) {
        var v = it[c];
        if (v === null || v === undefined) v = "";
        v = String(v);
        return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
      }).join(","));
    });
    return "﻿" + lines.join("\r\n");
  }

  function render() {
    renderResults();
    renderActions();
  }

  function renderChrome() {
    document.getElementById("rail").innerHTML = rail();
    var panel = document.getElementById("filterpanel");
    panel.innerHTML = ui.showFilters ? filterPanel() : "";
    var t = document.getElementById("filters-toggle");
    t.setAttribute("aria-pressed", ui.showFilters ? "true" : "false");
    t.innerHTML = "Filters" +
      (activeFilterCount() ? ' <span class="count">' + activeFilterCount() + "</span>" : "");
    Array.prototype.forEach.call(document.querySelectorAll(".seg [data-view]"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-view") === ui.view ? "true" : "false");
    });
  }

  function changed() {
    writeHash();
    renderChrome();
    render();
  }

  function clearFilters() {
    ui.disciplines = []; ui.doc = "all"; ui.sub = ""; ui.location = "";
    ui.manufacturer = ""; ui.approved = ""; ui.procured = "";
    changed();
  }

  function setTheme(v) {
    if (v === "auto") {
      document.documentElement.removeAttribute("data-theme");
      remember("gp1.theme", "auto");
    } else {
      document.documentElement.setAttribute("data-theme", v);
      remember("gp1.theme", v);
    }
    Array.prototype.forEach.call(document.querySelectorAll("[data-theme-set]"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-theme-set") === v ? "true" : "false");
    });
  }

  /* The sticky table head sits under the toolbar, whose height changes when the
     filter panel opens. Measure it rather than hard-coding an offset - a stale
     constant is what pins the column headers behind the panel. */
  function watchToolbar() {
    var tb = document.getElementById("toolbar");
    if (!tb) return;
    function measure() {
      document.documentElement.style.setProperty("--toolbar-h", tb.offsetHeight + "px");
    }
    measure();
    if (window.ResizeObserver) new ResizeObserver(measure).observe(tb);
    else window.addEventListener("resize", measure);
  }

  var qTimer = null, rTimer = null;

  function wire() {
    document.addEventListener("click", function (e) {
      if (!e.target || !e.target.closest) return;
      var el;

      if ((el = e.target.closest("[data-theme-set]"))) {
        setTheme(el.getAttribute("data-theme-set"));

      } else if ((el = e.target.closest("[data-view]"))) {
        ui.view = el.getAttribute("data-view");
        remember("gp1.view", ui.view);   // an explicit choice beats the breakpoint
        changed();

      } else if (e.target.closest("[data-disc-all]")) {
        ui.disciplines = [];
        changed();

      } else if ((el = e.target.closest("[data-disc]")) && el.tagName === "BUTTON") {
        var c = el.getAttribute("data-disc");
        var at = ui.disciplines.indexOf(c);
        if (at >= 0) ui.disciplines.splice(at, 1); else ui.disciplines.push(c);
        changed();

      } else if ((el = e.target.closest("[data-doc]"))) {
        ui.doc = el.getAttribute("data-doc");
        if (el.closest(".stat-key")) {
          ui.showFilters = true;
          document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
        }
        changed();

      } else if ((el = e.target.closest("[data-id]"))) {
        openSheet(el.getAttribute("data-id"));

      } else if ((el = e.target.closest("[data-dl]"))) {
        download(el.getAttribute("data-dl"));

      } else if (e.target.closest("#filters-toggle")) {
        ui.showFilters = !ui.showFilters;
        renderChrome();

      } else if (e.target.closest("#clear") || e.target.closest("#clear2")) {
        clearFilters();

      } else if (e.target.closest("#sheet-close") || e.target.closest("#sheet-done")) {
        document.getElementById("sheet").close();

      } else if (e.target.closest("#ed-open")) {
        editing = true; renderSheet();

      } else if (e.target.closest("#ed-cancel")) {
        editing = false; renderSheet();

      } else if (e.target.closest("#ed-save")) {
        saveSheet();

      } else if (e.target.closest("#save")) {
        window.Store.flush().then(function (r) {
          if (r === "saved") toast("Saved");
          else if (r === "read_only") showReadOnly();
        }, function () {});

      } else if (e.target.closest("#signin")) {
        var email = prompt("Email address for a sign-in link:");
        if (!email) return;
        window.Store.signIn(email).then(function (res) {
          toast(res && res.error
            ? "Couldn’t send the link: " + res.error.message
            : "Check your email for a sign-in link.");
        });

      } else if (e.target.closest("#signout")) {
        window.Store.signOut().then(function () { toast("Signed out."); render(); });
      }
    });

    /* A table row is a button in spirit; give it the keyboard to match. */
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      var row = e.target.closest && e.target.closest("tr.row");
      if (!row) return;
      e.preventDefault();
      openSheet(row.getAttribute("data-id"));
    });

    document.addEventListener("change", function (e) {
      var el = e.target.closest && e.target.closest("[data-sel]");
      if (!el) return;
      var k = el.getAttribute("data-sel"), v = el.value;
      if (k === "sub") ui.sub = v;
      else if (k === "loc") ui.location = v;
      else if (k === "mfr") ui.manufacturer = v;
      else if (k === "ap") ui.approved = v;
      else if (k === "pr") ui.procured = v;
      else if (k === "sort") ui.sort = v;
      changed();
    });

    document.addEventListener("input", function (e) {
      if (e.target.id !== "q") return;
      clearTimeout(qTimer);
      qTimer = setTimeout(function () {
        ui.q = e.target.value;
        writeHash();
        renderChrome();
        render();
      }, 130);
    });

    document.addEventListener("close", function (e) {
      if (e.target && e.target.id === "sheet") { sheetId = null; editing = false; }
    }, true);

    window.addEventListener("hashchange", function () {
      if (writingHash) return;
      if (readHash()) { renderChrome(); render(); }
    });

    /* Columns appear and disappear with the viewport, so a resize can change
       the table. Re-render only when the active set actually differs. */
    window.addEventListener("resize", function () {
      if (ui.view !== "table") return;
      clearTimeout(rTimer);
      rTimer = setTimeout(function () {
        var keys = activeColumns(currentRows()).map(function (c) { return c.key; }).join(",");
        if (keys !== lastColumnKeys) renderResults();
      }, 160);
    });

    window.Store.onChange(function () { renderActions(); });
  }

  function boot(data) {
    state = data;
    deriveAll(state.items);

    window.Store.bind({
      items: function () { return state.items; },
      byId: byId,
      rederive: function () { deriveAll(state.items); }
    });
    window.Store.restoreRole();

    ui.view = defaultView();
    var saved = recall("gp1.view");
    if (saved === "table" || saved === "cards" || saved === "acc") ui.view = saved;
    readHash();

    document.getElementById("root").innerHTML = shell();
    document.getElementById("toolbar").innerHTML = toolbar();
    renderChrome();
    wire();
    watchToolbar();
    setTheme(recall("gp1.theme") || "auto");
    render();
    writeHash();

    /* The register is complete and useful before either of these lands, and
       stays useful if they never do. */
    window.Store.restoreSession().then(renderActions);
    window.Store.syncFromRemote().then(function (rows) {
      if (!rows || !rows.length) return;
      state.items = rows;
      deriveAll(state.items);
      renderChrome();
      render();
    }, function () {});
  }

  window.Store.load().then(boot, function (err) {
    document.getElementById("root").innerHTML =
      '<div class="layout"><div class="content"><div class="banner"><div>' +
      "<b>The register couldn’t load.</b> " +
      esc(String(err && err.message || err)) +
      " — the schedule is still available as <a href=\"./data/seed.json\">seed.json</a>." +
      "</div></div></div></div>";
    if (window.console) console.error(err);
  });
})();
