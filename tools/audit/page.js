/* ---------------------------------------------------------------- copy */
document.addEventListener("click", function (ev) {
  var b = ev.target.closest("[data-copy]");
  if (!b) return;
  var text = b.getAttribute("data-copy");
  var slot = b.querySelector(".act") || b.querySelector(".said");
  var was = slot ? slot.textContent : b.textContent;
  function done() {
    if (slot) { slot.textContent = "Copied"; b.classList.add("done"); }
    else b.textContent = "Copied";
    setTimeout(function () {
      if (slot) { slot.textContent = was; b.classList.remove("done"); }
      else b.textContent = was;
    }, 1400);
  }
  function fallback() {
    var t = document.createElement("textarea");
    t.value = text; t.setAttribute("readonly", "");
    t.style.position = "fixed"; t.style.opacity = "0";
    document.body.appendChild(t); t.select();
    try { document.execCommand("copy"); done(); } catch (err) {}
    document.body.removeChild(t);
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done, fallback);
  } else { fallback(); }
});

/* ------------------------------------------------- staging the pictures

   A dropped picture is uploaded to this artifact's own asset store and
   remembered in `db` against the item it belongs to, keyed by that item's
   slug. That pairing is what lets Claude collect the batch afterwards and
   put each file into tools/images/ under the right name - and what keeps
   your pictures on the page after a reload.

   All of it no-ops when the capabilities are absent (a read-only view, or
   this page opened outside the viewer). The audit is the point and still
   reads without any of it.                                              */

(function () {
  var EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
             "image/webp": "webp", "image/svg+xml": "svg"};
  var BY_EXT = {png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
                gif: "image/gif", webp: "image/webp", svg: "image/svg+xml"};
  var MAX = 20 * 1024 * 1024;
  var assets = null, db = null, staged = {}, fine = {};

  var REASON = {
    too_large: "That file is over the 20 MB limit.",
    unsupported_type: "Not a picture this can store - PNG, JPEG, GIF, WebP or SVG.",
    invalid_request: "That file could not be read as a picture.",
    quota_or_state: "The picture store is full. Remove a staged picture first.",
    rate_limited: "Too many uploads at once - wait a moment and try again.",
    not_granted: "This view cannot store pictures.",
    capability_disabled: "Storing pictures is not available in this view."
  };

  function zone(slug) {
    return document.querySelector('.drop[data-slug="' + slug + '"]');
  }

  function face(slug) {
    return '<input class="pick" type="file" accept="image/png,image/jpeg,' +
      'image/gif,image/webp,image/svg+xml" id="pick-' + slug + '">' +
      '<label class="pickface" for="pick-' + slug + '">Drop a picture here ' +
      '<span>or choose one</span></label>';
  }

  function paint(slug) {
    var z = zone(slug);
    if (!z) return;
    var rec = staged[slug];
    if (!rec) { z.className = "drop"; z.innerHTML = face(slug); return; }
    z.className = "drop done";
    z.innerHTML =
      '<div class="staged">' +
        '<img src="' + (rec.asset ? "/_blob/" + rec.asset : rec.data) + '" alt="">' +
        '<span class="as"><b>Will be saved as</b>' + rec.filename + '</span>' +
        '<button class="rm" type="button" title="Remove this picture" ' +
          'aria-label="Remove the picture staged for ' + slug + '">&times;</button>' +
      '</div>';
  }

  /* A flagged item the reader says is actually fine. Kept in `db` so the
     judgement sticks for everyone and survives a reload - the audit is one
     person's eye, and being able to overrule it is the point. */
  function paintFine(slug) {
    var li = document.querySelector('.item[data-slug="' + slug + '"]');
    if (!li) return;
    var on = !!fine[slug];
    li.classList.toggle("cleared", on);
    var btn = li.querySelector(".fine");
    if (btn) btn.textContent = on ? "Cleared - undo" : "This one is fine";
  }

  function counts() {
    var per = {};
    var lis = document.querySelectorAll(".item[data-verdict]");
    for (var i = 0; i < lis.length; i++) {
      var v = lis[i].getAttribute("data-verdict");
      per[v] = per[v] || {total: 0, cleared: 0};
      per[v].total++;
      if (fine[lis[i].getAttribute("data-slug")]) per[v].cleared++;
    }
    Object.keys(per).forEach(function (v) {
      var slot = document.querySelector('.block.' + v + ' .cleared-n');
      if (slot) {
        slot.textContent = per[v].cleared
          ? per[v].cleared + " cleared" : "";
      }
      var t = document.querySelector('[data-tally="' + v + '"]');
      if (t) t.textContent = per[v].total - per[v].cleared;
    });
  }

  async function setFine(slug, on) {
    if (on) fine[slug] = true; else delete fine[slug];
    paintFine(slug);
    counts();
    if (!db) return;
    try {
      if (on) await db.doc("fine/" + slug).set({at: new Date().toISOString()});
      else await db.doc("fine/" + slug).delete();
    } catch (e) {}
  }

  function tally() {
    var n = Object.keys(staged).length;
    document.getElementById("barn").textContent = n;
    document.getElementById("bart").textContent = n === 1
      ? "picture staged, ready to hand over."
      : "pictures staged, ready to hand over.";
    document.getElementById("bar").classList.toggle("on", n > 0);
    if (!n) document.getElementById("handoff").classList.remove("on");
  }

  function fail(slug, msg) {
    var z = zone(slug);
    if (!z) return;
    z.classList.remove("busy");
    var p = document.createElement("p");
    p.className = "err";
    p.textContent = msg;
    z.appendChild(p);
    setTimeout(function () {
      if (p.parentNode) p.parentNode.removeChild(p);
    }, 5000);
  }

  function typeOf(file) {
    if (EXT[file.type]) return file.type;
    var m = /\.([a-z0-9]+)$/i.exec(file.name || "");
    return m ? (BY_EXT[m[1].toLowerCase()] || null) : null;
  }

  /* A picture small enough to live in a database row.

     The asset store keeps the original, which is the better thing to have
     when it is available. When it is not, the choice is between no picture at
     all and a smaller one - and the register displays these at about 720px
     and 12 KB, so a 1200px JPEG is already more than it will ever show. That
     is a fair trade for a page that works. */
  function shrink(file) {
    return new Promise(function (ok, no) {
      var fr = new FileReader();
      fr.onerror = function () { no(new Error("could not read that file")); };
      fr.onload = function () {
        var img = new Image();
        img.onerror = function () { no(new Error("that file is not an image")); };
        img.onload = function () {
          var w = img.naturalWidth, h = img.naturalHeight, M = 1200;
          if (w > M || h > M) {
            var r = Math.min(M / w, M / h);
            w = Math.round(w * r); h = Math.round(h * r);
          }
          var c = document.createElement("canvas");
          c.width = w; c.height = h;
          /* White behind it: a PNG cutout flattened onto transparency turns
             black the moment it becomes a JPEG. */
          var x = c.getContext("2d");
          x.fillStyle = "#fff"; x.fillRect(0, 0, w, h);
          x.drawImage(img, 0, 0, w, h);
          ok(c.toDataURL("image/jpeg", 0.85));
        };
        img.src = fr.result;
      };
      fr.readAsDataURL(file);
    });
  }

  async function take(slug, file) {
    if (!db || !file) return;
    var type = typeOf(file);
    if (!type) { fail(slug, "Only PNG, JPEG, GIF, WebP or SVG can be staged."); return; }
    if (file.size > MAX) { fail(slug, REASON.too_large); return; }

    var z = zone(slug);
    if (z) z.classList.add("busy");
    var previous = staged[slug];
    try {
      var rec;
      if (assets) {
        var up = await assets.upload(file, {type: type});
        rec = {asset: up.id, filename: slug + "." + EXT[type],
               contentType: type, bytes: up.sizeBytes,
               stagedAt: new Date().toISOString()};
      } else {
        /* SVG cannot go through a canvas without being rasterised, and a
           rasterised SVG is not what anyone dropped. */
        if (type === "image/svg+xml") {
          fail(slug, "SVG needs the asset store, which this page does not "
                   + "have. Save it into tools/images/ under the name shown.");
          if (z) z.classList.remove("busy");
          return;
        }
        var data = await shrink(file);
        rec = {data: data, filename: slug + ".jpg",
               contentType: "image/jpeg",
               bytes: Math.round(data.length * 3 / 4),
               stagedAt: new Date().toISOString()};
      }
      staged[slug] = rec;
      await db.doc("staged/" + slug).set(rec);
      paint(slug);
      tally();
      /* Only once the replacement is safely stored. */
      if (assets && previous && previous.asset && previous.asset !== rec.asset) {
        try { await assets.delete(previous.asset); } catch (e) {}
      }
    } catch (err) {
      /* The code when the runtime gives one, the message when it does not,
         and never just "it did not work" - which is a sentence you cannot act
         on and cannot report. */
      var why = (err && (REASON[err.code] || err.message || err.code)) || "";
      fail(slug, why ? "Upload refused: " + why
                     : "That upload did not go through, with no reason given.");
      if (window.console) console.error("GP1 upload", slug, err);
    }
  }

  async function unstage(slug) {
    var rec = staged[slug];
    if (!rec || !db) return;
    delete staged[slug];
    paint(slug);
    tally();
    try { await db.doc("staged/" + slug).delete(); } catch (e) {}
    if (assets && rec.asset) { try { await assets.delete(rec.asset); } catch (e) {} }
  }

  /* ---- events ---- */
  document.addEventListener("dragover", function (ev) {
    var z = ev.target.closest && ev.target.closest(".drop");
    if (!z || !db) return;
    ev.preventDefault();
    z.classList.add("over");
  });
  document.addEventListener("dragleave", function (ev) {
    var z = ev.target.closest && ev.target.closest(".drop");
    if (z) z.classList.remove("over");
  });
  document.addEventListener("drop", function (ev) {
    var z = ev.target.closest && ev.target.closest(".drop");
    if (!z || !db) return;
    ev.preventDefault();
    z.classList.remove("over");
    var f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
    if (f) take(z.getAttribute("data-slug"), f);
  });
  /* Without these, a picture dropped slightly off target replaces the page
     with the image file. */
  window.addEventListener("dragover", function (e) { e.preventDefault(); });
  window.addEventListener("drop", function (e) { e.preventDefault(); });

  document.addEventListener("change", function (ev) {
    var i = ev.target.closest && ev.target.closest(".pick");
    if (!i) return;
    var z = i.closest(".drop");
    if (z && i.files && i.files[0]) take(z.getAttribute("data-slug"), i.files[0]);
    i.value = "";
  });
  document.addEventListener("click", function (ev) {
    var x = ev.target.closest && ev.target.closest(".rm");
    if (x) {
      var z = x.closest(".drop");
      if (z) unstage(z.getAttribute("data-slug"));
      return;
    }
    var f = ev.target.closest && ev.target.closest(".fine");
    if (f) {
      var slug = f.getAttribute("data-slug");
      setFine(slug, !fine[slug]);
    }
  });

  document.getElementById("hand").addEventListener("click", async function () {
    var keys = Object.keys(staged);
    if (!keys.length || !db) return;
    var names = keys.map(function (k) { return staged[k].filename; }).sort();
    try {
      await db.doc("batch/current").set({
        files: names, count: names.length, at: new Date().toISOString()
      });
    } catch (e) {}
    document.getElementById("handn").textContent = names.length;
    document.getElementById("handlist").textContent = names.join("\n");
    var box = document.getElementById("handoff");
    box.classList.add("on");
    box.scrollIntoView({block: "nearest", behavior: "smooth"});
  });

  document.getElementById("clear").addEventListener("click", async function () {
    var keys = Object.keys(staged);
    if (!keys.length) return;
    if (!window.confirm("Remove all " + keys.length + " staged pictures?")) return;
    for (var i = 0; i < keys.length; i++) await unstage(keys[i]);
  });

  /* ---- manufacturer pages -------------------------------------------

     Nothing here waits on a button. Typing marks the row unsaved, a second
     of quiet writes it, and the row turns green only once the value has
     been READ BACK out of the database - green means the store holds it,
     not that a call returned. Leaving the field, hiding the tab or closing
     the page flushes whatever is still queued first.

     The first build saved on a button press alone, and a session of pasted
     links went with the page when it reloaded. So: the line under the
     heading reports what the database actually holds, a row that will not
     save goes red and stays red, and "Copy every link" puts the lot on the
     clipboard as CSV - the work survives even if this page cannot reach
     the store at all. */
  var linksEl = document.getElementById("lsave");
  var copyEl  = document.getElementById("lcopy");
  var stateEl = document.getElementById("lstate");
  var timers  = {};
  var booted  = false;

  function lrows() { return document.querySelectorAll(".lrow"); }
  /* Two URLs run together is a paste that landed mid-field instead of
     replacing - it happened twice and corrupted both links, and each looked
     like a perfectly good URL until you read it. */
  function isUrl(v) {
    return /^https?:\/\/\S+$/i.test(v) && v.split("://").length === 2;
  }
  function val(row) { return row.querySelector(".lurl").value.trim(); }

  function report() {
    var all = lrows(), filled = 0;
    for (var i = 0; i < all.length; i++) if (val(all[i])) filled++;
    var t = document.getElementById("ltally");
    if (t) t.textContent = filled + " of " + all.length;
    if (!stateEl) return;

    var kept = document.querySelectorAll(".lrow.kept").length;
    var bad  = document.querySelectorAll(".lrow.bad").length;
    var lost = document.querySelectorAll(".lrow.lost").length;
    /* A row that is invalid or refused is not "still saving" - it is stuck,
       and counting it as in-flight reads as though it were on its way. */
    var wait = document.querySelectorAll(".lrow.dirty:not(.bad):not(.lost)").length;
    var bits = [];
    if (!db) {
      bits.push("No database in this view — use Copy every link so " +
                "nothing is lost");
    } else {
      bits.push(kept + (kept === 1 ? " link is saved" : " links are saved"));
      if (wait) bits.push(wait + " still saving");
      if (bad)  bits.push(bad + (bad === 1 ? " is not a URL" : " are not URLs"));
      var held = document.querySelectorAll(".lrow.held").length;
      if (held) {
        bits.push(held + (held === 1 ? " is kept in this browser" :
                          " are kept in this browser") +
                  " but not in the database" +
                  (lastError ? " (" + lastError + ")" : "") +
                  " — Copy every link to get them out");
      }
      if (lost) {
        bits.push(lost + " would not save" +
                  (lastError ? " (" + lastError + ")" : "") +
                  " — copy them out");
      }
    }
    stateEl.textContent = bits.join(" · ");
    stateEl.className = "lstate" +
      ((!db || bad || lost || document.querySelectorAll(".lrow.held").length)
       ? " warn" : "");
  }

  var lastError = "";

  /* Can this view write at all?

     Reading and writing are separate permissions: a database that answers
     reads can still refuse every write, and until now the page found that out
     one row at a time, after somebody had typed into them. One scratch
     document at startup settles it. */
  async function canWrite() {
    if (!db) return false;
    /* Probe the collection the links actually use. A scratch path of its own
       can be refused by a rule that has nothing to say about maker/, which
       would condemn a page that works perfectly well. */
    var ref = db.doc("maker/_selftest");
    try {
      await ref.set({at: new Date().toISOString()});
      var back = await ref.get();
      if (!back || !back.exists) throw new Error("the write did not read back");
      try { await ref.delete(); } catch (e) {}
      return true;
    } catch (err) {
      lastError = (err && (err.code ? err.code + ": " : "") +
                          (err.message || "")) || "refused";
      if (window.console) console.error("GP1 db write probe", err);
      return false;
    }
  }

  function markLink(row) {
    var v = val(row);
    row.classList.toggle("bad", !!v && !isUrl(v));
    row.classList.add("dirty");
    row.classList.remove("kept", "lost", "held");
  }

  /* Does the store hold exactly what this row says?

     `DocumentSnapshot.data` is a METHOD, not a property - reading
     `back.data.url` is always undefined, which turned every successful save
     red. Read it the same way the collection loader below does. */
  async function matches(ref, v) {
    var back = await ref.get();
    if (!back || !back.exists) return !v;
    var body = typeof back.data === "function" ? back.data() : back.data;
    return !!(v && body && body.url === v);
  }

  /* Writes one row and then reads it back. Returns true only if the store
     answered with what we sent. */
  async function saveLink(row) {
    if (!db) { report(); return false; }
    var v = val(row);
    if (v && !isUrl(v)) { report(); return false; }   /* stays dirty and red */
    var ref = db.doc("maker/" + row.getAttribute("data-slug"));
    try {
      if (v) await ref.set({url: v, at: new Date().toISOString()});
      else   await ref.delete();
      /* Read it back before going green. A store is allowed to answer the
         first read before the write has landed, so a mismatch gets one
         second look - otherwise a save that worked would flash red. */
      var ok = await matches(ref, v);
      if (!ok) {
        await new Promise(function (r) { setTimeout(r, 450); });
        ok = await matches(ref, v);
      }
      if (!ok) throw new Error("the database did not read back what was sent");
      row.classList.remove("dirty", "bad", "lost", "held");
      row.classList.toggle("kept", !!v);
      return true;
    } catch (err) {
      row.classList.remove("kept");
      /* Held here, not lost: the browser has it and Copy every link will
         include it. The row says which of the two happened. */
      row.classList.add(remembered(row.getAttribute("data-slug")) === v && v
                        ? "held" : "lost");
      /* The code first: the docs say to branch on it and never on message
         text, and "malformed or exceeds a limit" covers a bad path, an
         oversized body and a full collection alike - which are three quite
         different problems with three different answers. */
      var why = (err && (err.code ? err.code + ": " : "") +
                        (err.message || "")) || "no reason given";
      /* invalid_argument covers the path, the body and the value alike, and
         which of the three it is decides everything. The startup probe writes
         {at} and passes; a row writes {url, at} and fails, so the difference
         is worth establishing rather than guessing at. One escalating retry,
         only on this code, only once per row. */
      if (err && err.code === "invalid_argument" && !row._probed) {
        row._probed = true;
        try {
          await ref.set({at: new Date().toISOString()});
          why += " - but the same document accepted a write WITHOUT the url "
               + "field, so the value is what it refuses (length " + v.length
               + ", starts " + JSON.stringify(v.slice(0, 40)) + ")";
        } catch (e2) {
          why += " - and it also refused a write with no url field, so it is "
               + "the document or the path, not the value";
        }
      }
      row.setAttribute("title", "Would not save: " + why);
      lastError = why;
      if (window.console) console.error("GP1 link save", row.dataset.slug, err);
      return false;
    } finally {
      report();
    }
  }

  /* ---- the copy that cannot fail ----

     The database has refused every write in this view with invalid_argument,
     while the identical write from outside the page commits first time. I
     have not found why, and this page should not have been built so that
     finding out is a condition of anybody getting any work done.

     So localStorage is now the primary store. It is synchronous, it needs no
     capability, it cannot be refused, and it survives a reload and a closed
     tab. The database is still written - it is what makes a link visible on
     another machine - but a failure there no longer costs anybody a keystroke,
     and "Copy every link" reads the fields themselves, so it is complete
     either way.

     What it does not do is reach another device. That is what the CSV is
     for, and why the button next to it matters. */
  var LS = "gp1.maker.";

  function remember(slug, v) {
    try {
      if (v) localStorage.setItem(LS + slug, v);
      else localStorage.removeItem(LS + slug);
      return true;
    } catch (e) { return false; }
  }

  function remembered(slug) {
    try { return localStorage.getItem(LS + slug) || ""; }
    catch (e) { return ""; }
  }

  function queue(row) {
    /* Immediately, before the debounce and before any network: by the time
       the 900ms timer fires the browser already has it. */
    remember(row.getAttribute("data-slug"), val(row));
    var slug = row.getAttribute("data-slug");
    clearTimeout(timers[slug]);
    timers[slug] = setTimeout(function () {
      timers[slug] = 0;
      saveLink(row);
    }, 900);
  }

  /* Write everything still queued, now. */
  function flush() {
    var out = [];
    Object.keys(timers).forEach(function (k) {
      if (timers[k]) { clearTimeout(timers[k]); timers[k] = 0; }
    });
    var d = document.querySelectorAll(".lrow.dirty");
    for (var i = 0; i < d.length; i++) out.push(saveLink(d[i]));
    return Promise.all(out);
  }

  /* Selecting on focus means a paste replaces rather than inserts. */
  document.addEventListener("focusin", function (ev) {
    if (ev.target.classList && ev.target.classList.contains("lurl")) {
      ev.target.select();
    }
  });

  document.addEventListener("input", function (ev) {
    var i = ev.target.closest && ev.target.closest(".lurl");
    if (!i) return;
    var row = i.closest(".lrow");
    markLink(row);
    report();
    queue(row);
  });

  /* Blur, Enter, and a paste that never gets a keystroke after it. */
  document.addEventListener("change", function (ev) {
    var i = ev.target.closest && ev.target.closest(".lurl");
    if (!i) return;
    var row = i.closest(".lrow");
    clearTimeout(timers[row.getAttribute("data-slug")]);
    timers[row.getAttribute("data-slug")] = 0;
    saveLink(row);
  }, true);

  /* A prefilled guess that happens to be right still has to be confirmed,
     or it can never leave the list. This saves the row as it stands. */
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest(".lok");
    if (!b) return;
    var row = b.closest(".lrow");
    clearTimeout(timers[row.getAttribute("data-slug")]);
    timers[row.getAttribute("data-slug")] = 0;
    b.textContent = "Saving…";
    saveLink(row).then(function (ok) {
      b.textContent = ok ? "Confirmed" : "Would not save";
      if (!ok) setTimeout(function () { b.textContent = "This one is right"; }, 2600);
    });
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", function () { flush(); });
  window.addEventListener("beforeunload", function (ev) {
    if (!document.querySelector(".lrow.dirty, .lrow.lost")) return;
    flush();
    ev.preventDefault();
    ev.returnValue = "";
  });

  /* ---- the escape hatch ---- */
  function csv() {
    var out = ["code,slug,url"], all = lrows();
    function cell(s) {
      s = String(s == null ? "" : s);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    }
    for (var i = 0; i < all.length; i++) {
      var v = val(all[i]);
      if (!v) continue;
      out.push([cell(all[i].getAttribute("data-code")),
                cell(all[i].getAttribute("data-slug")),
                cell(v)].join(","));
    }
    return out.join("\n");
  }

  function say(el, msg, back) {
    el.textContent = msg;
    setTimeout(function () { el.textContent = back; }, 2600);
  }

  if (copyEl) {
    copyEl.addEventListener("click", async function () {
      var text = csv(), n = text.split("\n").length - 1;
      var done = false;
      try {
        await navigator.clipboard.writeText(text);
        done = true;
      } catch (err) {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "readonly");
        ta.style.cssText = "position:fixed;left:-9999px;top:0";
        document.body.appendChild(ta);
        ta.select();
        try { done = document.execCommand("copy"); } catch (e2) {}
        document.body.removeChild(ta);
      }
      say(copyEl, done ? "Copied " + n : "Could not copy", "Copy every link");
    });
  }

  if (linksEl) {
    linksEl.addEventListener("click", async function () {
      if (!db) { say(linksEl, "No database here", "Save every link"); return; }
      linksEl.textContent = "Saving…";
      var all = lrows(), saved = 0, bad = 0, lost = 0;
      for (var i = 0; i < all.length; i++) {
        var v = val(all[i]);
        if (v && !isUrl(v)) { bad++; continue; }
        if (!v) continue;
        if (await saveLink(all[i])) saved++; else lost++;
      }
      report();
      say(linksEl,
          "Saved " + saved + (bad ? ", " + bad + " not a URL" : "") +
          (lost ? ", " + lost + " failed" : ""),
          "Save every link");
    });
  }

  /* ---- the picture review -------------------------------------------

     Two marks per picture, and they are opposites: Fine says you have looked
     and it will do, Needs a better one marks it for replacement. Marking
     either clears the other, because a picture cannot be both.

     Nothing is written until Save. A mark is a judgement being formed and
     you should be able to go down the grid changing your mind before any of
     it counts. Hiding what you have passed is what makes 134 cards
     finishable: what is left on screen is what you have not looked at. */
  var psaveEl = document.getElementById("psave");
  var pnoneEl = document.getElementById("pnone");
  var phideEl = document.getElementById("phide");
  var pstateEl = document.getElementById("pstate");
  var pgridEl = document.querySelector(".pgrid");
  var pkept = {bad: {}, ok: {}};      /* what the store held when we looked */

  function prows() { return document.querySelectorAll(".prow"); }

  function preport() {
    var all = prows(), bad = 0, ok = 0, dirty = 0;
    for (var i = 0; i < all.length; i++) {
      var slug = all[i].getAttribute("data-slug");
      var b = all[i].classList.contains("marked");
      var o = all[i].classList.contains("okay");
      if (b) bad++;
      if (o) ok++;
      if (b !== !!pkept.bad[slug] || o !== !!pkept.ok[slug]) dirty++;
    }
    var t = document.getElementById("ptally");
    if (t) t.textContent = (bad + ok) + " of " + all.length;
    if (!pstateEl) return;
    if (!db) {
      pstateEl.textContent = "No database in this view — marks cannot be saved";
      pstateEl.className = "lstate warn";
      return;
    }
    var bits = [bad + " still to replace", ok + " passed since"];
    if (dirty) bits.push(dirty + (dirty === 1 ? " change" : " changes") +
                         " not saved yet");
    pstateEl.textContent = bits.join(" · ");
    pstateEl.className = "lstate" + (dirty ? " warn" : "");
  }

  /* Every card on this list is here because it needs a better picture, so
     the only move is to take one off - and the only way back is to put it
     on again. The button toggles between those two, never to a third state
     where the card is on the list but marked as nothing. */
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest(".ptick");
    if (!b) return;
    var row = b.closest(".prow");
    var fine = row.classList.contains("okay");
    row.classList.toggle("okay", !fine);
    row.classList.toggle("marked", fine);
    b.textContent = fine ? "Fine after all" : "Back on the list";
    preport();
  });

  if (phideEl) {
    phideEl.addEventListener("click", function () {
      if (!pgridEl) return;
      var hiding = pgridEl.classList.toggle("hideok");
      phideEl.textContent = hiding
        ? "Show the ones marked fine"
        : "Hide the ones marked fine";
    });
  }

  if (pnoneEl) {
    pnoneEl.addEventListener("click", function () {
      var all = prows();
      for (var i = 0; i < all.length; i++) {
        all[i].classList.remove("okay");
        all[i].classList.add("marked");        /* back to how the list arrived */
        var b = all[i].querySelector(".pok");
        if (b) b.textContent = "Fine after all";
      }
      preport();
    });
  }

  if (psaveEl) {
    psaveEl.addEventListener("click", async function () {
      if (!db) {
        psaveEl.textContent = "No database here";
        setTimeout(function () { psaveEl.textContent = "Save"; }, 2400);
        return;
      }
      psaveEl.textContent = "Saving…";
      var all = prows(), wrote = 0, cleared = 0, failed = 0;
      var of = {marked: ["fixpic", "bad"], okay: ["picok", "ok"]};
      for (var i = 0; i < all.length; i++) {
        var row = all[i], slug = row.getAttribute("data-slug");
        for (var cls in of) {
          var coll = of[cls][0], side = of[cls][1];
          var on = row.classList.contains(cls);
          if (on === !!pkept[side][slug]) continue;     /* unchanged */
          var ref = db.doc(coll + "/" + slug);
          try {
            if (on) {
              await ref.set({at: new Date().toISOString(),
                             title: row.querySelector(".pname").textContent});
              var back = await ref.get();
              if (!(back && back.exists)) throw new Error("not read back");
              pkept[side][slug] = true; wrote++;
            } else {
              await ref.delete();
              delete pkept[side][slug]; cleared++;
            }
          } catch (err) { failed++; }
        }
      }
      preport();
      psaveEl.textContent =
        (wrote ? "Saved " + wrote : "Nothing new") +
        (cleared ? ", cleared " + cleared : "") +
        (failed ? ", " + failed + " failed" : "");
      setTimeout(function () { psaveEl.textContent = "Save"; }, 3000);
    });
  }

  /* ---- wake up ---- */
  (async function () {
    var use = window.claude && window.claude.use;
    if (use) {
      try { assets = await window.claude.use("assets"); } catch (e) {}
      try { db = await window.claude.use("db"); } catch (e) {}
    }
    /* Degrade one capability at a time. This used to hide the drop zones AND
       the whole links section the moment EITHER came back null - so a page
       that could not take pictures also could not be used to check a single
       manufacturer link, which needs nothing but the database. One being
       unavailable is not the other being unavailable. */
    var off = document.getElementById("offline");
    if (!assets && !db) {
      var zs = document.querySelectorAll(".drop, .fine");
      for (var i = 0; i < zs.length; i++) zs[i].style.display = "none";
    }
    if (!db && linksEl) linksEl.style.display = "none";

    if (!assets && !db) {
      off.textContent = "Open this page in the Claude viewer to drag pictures "
        + "straight in and save links. The filenames work either way.";
    } else if (!assets) {
      off.textContent = "This page's asset store did not load, so pictures "
        + "are stored in the database instead and scaled to 1200px on the "
        + "way in - more than the register shows. Everything works; only an "
        + "SVG has to be saved into tools/images/ by hand.";
    } else if (!db) {
      off.textContent = "Links cannot be saved from here: the database did "
        + "not load. Pictures can still be staged.";
    }
    if (!assets && !db) {
      report();
      preport();
      return;
    }
    if (!db) { report(); preport(); return; }

    /* Reading works. Writing is a separate question, and the answer decides
       whether this page is a place to do work or a place to lose it. */
    var writable = await canWrite();
    if (!writable) {
      off.textContent = "A test write to the database was refused"
        + (lastError ? " (" + lastError + ")" : "") + ", so saving here may "
        + "not work. Type anyway - then use “Copy every link” and "
        + "paste the result into tools/maker-links.csv, which does not depend "
        + "on any of this. A row that does save still turns green.";
      off.className = "offline warn";
      /* WARN, NEVER BLOCK. Locking the fields was the wrong call and made
         things worse: it turned "saves may fail" into "you cannot work", on
         the word of a probe that can itself be wrong. Typing stays possible
         whatever the probe thinks - Copy every link gets it out either way,
         and a page that refuses input is no use even when it is right. */
      var ins = document.querySelectorAll(".lurl");
      for (var q = 0; q < ins.length; q++) {
        ins[q].title = "Type freely - use Copy every link to get it out, "
                     + "because saving may not work in this view.";
      }
    }
    try {
      var ok = await db.collection("fine").limit(200).get();
      ((ok && ok.docs) || ok || []).forEach(function (doc) {
        var id = doc.id || doc.path || "";
        fine[String(id).split("/").pop()] = true;
      });
    } catch (e) {}
    Object.keys(fine).forEach(paintFine);
    counts();
    /* Anything saved earlier wins over what was baked into the page, and
       comes back green: it is in the store by definition. */
    try {
      var saved = await db.collection("maker").limit(300).get();
      ((saved && saved.docs) || saved || []).forEach(function (doc) {
        var id = String(doc.id || doc.path || "").split("/").pop();
        var data = typeof doc.data === "function" ? doc.data() : doc.data;
        var row = document.querySelector('.lrow[data-slug="' + id + '"]');
        if (row && data && data.url) {
          row.querySelector(".lurl").value = data.url;
          row.classList.add("kept");
          row.classList.remove("dirty", "bad", "lost", "held");
        }
      });
    } catch (e) {}

    /* Then whatever this browser is holding, for every row the database did
       not fill. Last, so a link that IS in the database wins - that one is
       the shared truth and reaches other machines; this is the local copy of
       work the database refused. Either way nothing typed here is gone after
       a reload, which is the whole point of keeping it twice. */
    var all = lrows();
    for (var i = 0; i < all.length; i++) {
      var slug = all[i].getAttribute("data-slug");
      var mine = remembered(slug);
      if (!mine || all[i].classList.contains("kept")) continue;
      all[i].querySelector(".lurl").value = mine;
      all[i].classList.add("held");
    }

    booted = true;
    report();
    /* Ticks come back from the store, or a reload would quietly lose them -
       which is exactly how a session of links went missing. */
    /* Every card in this grid is here because it was marked as needing a
       better picture, so the page arrives with that baked in - the list IS
       the mark, and there is no second read to disagree with it.

       The one thing worth reading back is picok: a card passed as fine
       since the page was built should not come back red on a reload. */
    var pr0 = document.querySelectorAll(".prow");
    for (var i = 0; i < pr0.length; i++) {
      pkept.bad[pr0[i].getAttribute("data-slug")] = true;
    }
    try {
      /* NOT "fine" - that is the module-level object for the older audit
         cards, and `var` hoists this over it for the whole function, so the
         boot threw at the first use of it and never reached the links. */
      var passed = await db.collection("picok").limit(400).get();
      ((passed && passed.docs) || passed || []).forEach(function (doc) {
        var id = String(doc.id || doc.path || "").split("/").pop();
        var row = document.querySelector('.prow[data-slug="' + id + '"]');
        if (row) {
          row.classList.remove("marked");
          row.classList.add("okay");
          pkept.ok[id] = true;
          delete pkept.bad[id];
        }
      });
    } catch (e) {}
    preport();
    try {
      var snap = await db.collection("staged").limit(200).get();
      var docs = (snap && snap.docs) || snap || [];
      docs.forEach(function (doc) {
        var data = typeof doc.data === "function" ? doc.data() : doc.data;
        var id = doc.id || doc.path || "";
        if (data && data.asset) staged[String(id).split("/").pop()] = data;
      });
    } catch (e) {}
    Object.keys(staged).forEach(paint);
    tally();
  })();
})();
