"""Wrap picture-audit.html in a fake artifact store and drive the link rows."""
import io, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
page = io.open("picture-audit.html", encoding="utf-8").read()

STUB = r"""<script>
/* A stand-in for the artifact store: records every call, behaves like the
   real one (get -> {exists, data}), and can be told to fail for one slug. */
window.__log = [];
window.__store = {};
window.__failFor = null;
window.__lagFor = null;
window.__copied = null;
Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
  writeText: function (t) { window.__copied = t; return Promise.resolve(); }
}});
function ref(path) {
  return {
    set: function (d) {
      window.__log.push(["set", path, d.url]);
      if (window.__failFor && path.indexOf(window.__failFor) > -1)
        return Promise.reject({code: "unavailable", message: "nope"});
      window.__store[path] = d;
      return Promise.resolve();
    },
    delete: function () {
      window.__log.push(["delete", path, null]);
      if (window.__failFor && path.indexOf(window.__failFor) > -1)
        return Promise.reject({code: "unavailable", message: "nope"});
      delete window.__store[path];
      return Promise.resolve();
    },
    get: function () {
      window.__log.push(["get", path, null]);
      /* A store that answers the first read before the write has landed. */
      if (window.__lagFor && path.indexOf(window.__lagFor) > -1) {
        window.__lagFor = null;
        return Promise.resolve({exists: false, data: function () {}});
      }
      var d = window.__store[path];
      /* data() is a method on the real DocumentSnapshot. Faking it as a
         plain property is what let a broken read-back pass 24 tests. */
      return Promise.resolve({exists: !!d, data: function () { return d; }});
    }
  };
}
var FAKE_DB = {
  doc: ref,
  collection: function (name) {
    return { limit: function () { return { get: function () {
      var docs = [];
      Object.keys(window.__store).forEach(function (p) {
        if (p.indexOf(name + "/") === 0)
          docs.push({id: p.split("/").pop(),
                     data: (function (v) { return function () { return v; }; })(window.__store[p])});
      });
      return Promise.resolve({docs: docs});
    }};}};
  }
};
window.claude = { use: function (n) {
  if (n === "db") return Promise.resolve(FAKE_DB);
  if (n === "assets") return Promise.resolve({upload: function () {}, list: function () {}});
  return Promise.resolve(null);
}};
</script>
"""

DRIVER = r"""<pre id="TESTOUT" style="white-space:pre-wrap"></pre>
<script>
(async function () {
  var out = [], pass = 0, fail = 0;
  function ok(name, cond, extra) {
    (cond ? pass++ : fail++);
    out.push((cond ? "PASS  " : "FAIL  ") + name + (extra ? "   [" + extra + "]" : ""));
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function rows() { return document.querySelectorAll(".lrow"); }
  function type(row, v) {
    var i = row.querySelector(".lurl");
    i.value = v;
    i.dispatchEvent(new Event("input", {bubbles: true}));
  }
  function commit(row) {
    row.querySelector(".lurl").dispatchEvent(new Event("change", {bubbles: true}));
  }
  function state() { return document.getElementById("lstate"); }

  for (var t = 0; t < 100 && state().textContent.indexOf("Connect") === 0; t++)
    await wait(50);
  ok("the page boots and reports state",
     state().textContent.indexOf("Connect") !== 0, state().textContent);

  var all = rows();
  ok("only the unconfirmed rows are listed", all.length === 53, all.length + " rows");
  ok("every row carries a slug",
     [].every.call(all, function (r) { return /^[a-z0-9]/.test(r.getAttribute("data-slug")); }));

  /* 1. typing then going quiet saves */
  var r0 = all[0], s0 = r0.getAttribute("data-slug");
  type(r0, "https://www.pentair.com/en/product-category/pool-spa/filters.html");
  ok("typing marks the row unsaved", r0.classList.contains("dirty"));
  await wait(1400);
  ok("a second of quiet writes it",
     !!window.__store["maker/" + s0] &&
     window.__store["maker/" + s0].url.indexOf("pentair.com/en") > -1);
  ok("the row turns green", r0.classList.contains("kept"), r0.className);
  ok("green came after a read-back",
     window.__log.some(function (e) { return e[0] === "get" && e[1] === "maker/" + s0; }));

  /* 2. blur commits at once */
  var r1 = all[1], s1 = r1.getAttribute("data-slug");
  type(r1, "https://www.pentair.com/intelliflo3");
  commit(r1);
  await wait(250);
  ok("leaving the field saves without waiting for the debounce",
     !!window.__store["maker/" + s1]);

  /* 3. rubbish is refused and never written */
  var r2 = all[2], s2 = r2.getAttribute("data-slug");
  var before = window.__log.length;
  type(r2, "pentair dot com");
  await wait(1400);
  ok("a value that is not a URL is flagged", r2.classList.contains("bad"));
  ok("and is never written",
     !window.__log.slice(before).some(function (e) {
       return e[1] === "maker/" + s2 && e[0] === "set"; }));
  ok("the status line warns about it",
     state().className.indexOf("warn") > -1, state().textContent);

  type(r2, "https://www.pentair.com/fixed");
  await wait(1400);
  ok("correcting it saves and clears the flag",
     !!window.__store["maker/" + s2] && !r2.classList.contains("bad"));

  /* 4. clearing deletes */
  type(r0, "");
  await wait(1400);
  ok("clearing a link deletes it", !window.__store["maker/" + s0]);
  ok("and the row is no longer green", !r0.classList.contains("kept"));

  /* 5. a store that refuses goes loudly red */
  var r3 = all[3], s3 = r3.getAttribute("data-slug");
  window.__failFor = s3;
  type(r3, "https://example.com/will-not-save");
  await wait(1400);
  ok("a refused write turns the row red", r3.classList.contains("lost"), r3.className);
  ok("it is NOT shown as saved", !r3.classList.contains("kept"));
  ok("the status line says it would not save",
     state().textContent.indexOf("would not save") > -1, state().textContent);
  window.__failFor = null;

  commit(r3);
  await wait(500);
  ok("a retry after the store recovers saves it",
     !!window.__store["maker/" + s3] && r3.classList.contains("kept"));

  /* 5c. a store that lags on the read-back must not flash red */
  var r5 = all[5], s5 = r5.getAttribute("data-slug");
  window.__lagFor = s5;
  type(r5, "https://example.com/slow-store");
  await wait(2000);
  ok("a lagging read-back is retried, not called a failure",
     r5.classList.contains("kept") && !r5.classList.contains("lost"),
     r5.className);

  /* 6. hiding the tab flushes */
  var r4 = all[4], s4 = r4.getAttribute("data-slug");
  type(r4, "https://example.com/pending-when-hidden");
  Object.defineProperty(document, "visibilityState", {value: "hidden", configurable: true});
  document.dispatchEvent(new Event("visibilitychange"));
  await wait(500);
  ok("hiding the tab writes what was still queued", !!window.__store["maker/" + s4]);

  /* 6b. confirming a prefill that is already right */
  var r6 = all[6], s6 = r6.getAttribute("data-slug");
  var had = r6.querySelector(".lurl").value.trim();
  r6.querySelector(".lok").click();
  await wait(700);
  ok("This one is right saves the row untouched",
     !!window.__store["maker/" + s6] &&
     window.__store["maker/" + s6].url === had, had.slice(0, 40));
  ok("and the row goes green", r6.classList.contains("kept"), r6.className);
  ok("the button says so", r6.querySelector(".lok").textContent === "Confirmed",
     r6.querySelector(".lok").textContent);

  /* 7. the clipboard escape hatch */
  document.getElementById("lcopy").click();
  await wait(400);
  var csv = window.__copied || "";
  ok("Copy every link produces CSV", csv.indexOf("code,slug,url") === 0,
     csv.split("\n")[0]);
  ok("the CSV carries what is on screen",
     csv.indexOf("https://www.pentair.com/fixed") > -1,
     (csv.split("\n").length - 1) + " rows");

  /* 8. prefilled links survived */
  var filled = [].filter.call(rows(), function (r) {
    return r.querySelector(".lurl").value.trim(); });
  ok("every open row carries a guess to work from", filled.length >= 35,
     filled.length + " filled");

  /* 9. the sweep button */
  document.getElementById("lsave").click();
  await wait(3000);
  ok("Save every link writes every filled row",
     Object.keys(window.__store).length >= filled.length,
     Object.keys(window.__store).length + " docs for " + filled.length + " rows");

  out.push("");
  out.push(pass + " passed, " + fail + " failed");
  document.getElementById("TESTOUT").textContent = out.join("\n");
  document.title = "DONE " + pass + "/" + (pass + fail);
})();
</script>
"""

doc = STUB + page + DRIVER
io.open("_linktest.html", "w", encoding="utf-8", newline="\n").write(doc)
print("harness written,", len(doc), "bytes")
