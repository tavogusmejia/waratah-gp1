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
        '<img src="/_blob/' + rec.asset + '" alt="">' +
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

  async function take(slug, file) {
    if (!assets || !db || !file) return;
    var type = typeOf(file);
    if (!type) { fail(slug, "Only PNG, JPEG, GIF, WebP or SVG can be staged."); return; }
    if (file.size > MAX) { fail(slug, REASON.too_large); return; }

    var z = zone(slug);
    if (z) z.classList.add("busy");
    var previous = staged[slug];
    try {
      var up = await assets.upload(file, {type: type});
      var rec = {asset: up.id, filename: slug + "." + EXT[type],
                 contentType: type, bytes: up.sizeBytes,
                 stagedAt: new Date().toISOString()};
      staged[slug] = rec;
      await db.doc("staged/" + slug).set(rec);
      paint(slug);
      tally();
      /* Only once the replacement is safely stored. */
      if (previous && previous.asset !== up.id) {
        try { await assets.delete(previous.asset); } catch (e) {}
      }
    } catch (err) {
      fail(slug, REASON[err && err.code] || "That upload did not go through.");
    }
  }

  async function unstage(slug) {
    var rec = staged[slug];
    if (!rec || !db) return;
    delete staged[slug];
    paint(slug);
    tally();
    try { await db.doc("staged/" + slug).delete(); } catch (e) {}
    if (assets) { try { await assets.delete(rec.asset); } catch (e) {} }
  }

  /* ---- events ---- */
  document.addEventListener("dragover", function (ev) {
    var z = ev.target.closest && ev.target.closest(".drop");
    if (!z || !assets) return;
    ev.preventDefault();
    z.classList.add("over");
  });
  document.addEventListener("dragleave", function (ev) {
    var z = ev.target.closest && ev.target.closest(".drop");
    if (z) z.classList.remove("over");
  });
  document.addEventListener("drop", function (ev) {
    var z = ev.target.closest && ev.target.closest(".drop");
    if (!z || !assets) return;
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
  function isUrl(v) { return /^https?:\/\/\S+$/i.test(v); }
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
      if (lost) bits.push(lost + " would not save — copy them out");
    }
    stateEl.textContent = bits.join(" · ");
    stateEl.className = "lstate" + ((!db || bad || lost) ? " warn" : "");
  }

  function markLink(row) {
    var v = val(row);
    row.classList.toggle("bad", !!v && !isUrl(v));
    row.classList.add("dirty");
    row.classList.remove("kept", "lost");
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
      row.classList.remove("dirty", "bad", "lost");
      row.classList.toggle("kept", !!v);
      return true;
    } catch (err) {
      row.classList.remove("kept");
      row.classList.add("lost");
      return false;
    } finally {
      report();
    }
  }

  function queue(row) {
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

  /* ---- wake up ---- */
  (async function () {
    var use = window.claude && window.claude.use;
    if (use) {
      try { assets = await window.claude.use("assets"); } catch (e) {}
      try { db = await window.claude.use("db"); } catch (e) {}
    }
    if (!assets || !db) {
      document.getElementById("offline").textContent =
        "Open this page in the Claude viewer to drag pictures straight in. " +
        "The filenames work either way.";
      var zs = document.querySelectorAll(".drop, .fine");
      for (var i = 0; i < zs.length; i++) zs[i].style.display = "none";
      if (linksEl) linksEl.style.display = "none";
      report();
      return;
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
          row.classList.remove("dirty", "bad", "lost");
        }
      });
    } catch (e) {}
    booted = true;
    report();
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
