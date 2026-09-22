"""Open every matched Drive link and check the page names the file we expect.

A 200 is not enough - Drive answers 200 with a "request access" wall too. The
<title> of a file view is the filename, so comparing it to the name the crawl
recorded proves both that the link works and that it points at the right file.
"""
import html, json, io, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
sys.path.insert(0, r"C:\Users\gus\Dropbox\06 Apps\Waratah-gp1\tools")
from extract_datasheets import slug

matched = json.load(open("_matched.json", encoding="utf-8"))


def check(item):
    stem, m = item
    url = "https://drive.google.com/file/d/" + m["id"] + "/view"
    r = subprocess.run(["curl", "-s", "-L", "-A", UA, url], capture_output=True)
    body = r.stdout.decode("utf-8", "replace")
    t = re.search(r"<title>(.*?)</title>", body, re.S)
    title = html.unescape(t.group(1) if t else "")
    title = title.replace(" - Google Drive", "").strip()
    wall = bool(re.search(r"You need access|Request access|requestAccess", body))
    want = m["path"].rsplit("/", 1)[-1]
    return stem, title, want, wall, slug(title) == slug(want)


out = io.open(1, "w", encoding="utf-8", closefd=False)
with ThreadPoolExecutor(max_workers=8) as pool:
    res = list(pool.map(check, sorted(matched.items())))

bad = [r for r in res if not r[4] or r[3]]
out.write("checked %d links\n" % len(res))
out.write("title matches the crawled filename : %d\n" % sum(1 for r in res if r[4]))
out.write("permission walls                   : %d\n" % sum(1 for r in res if r[3]))
if bad:
    out.write("\n--- links that did not check out ---\n")
    for stem, title, want, wall, okmatch in bad:
        out.write("  %s\n    want : %s\n    got  : %s%s\n"
                  % (stem, want, title, "  [WALL]" if wall else ""))
else:
    out.write("\nEvery link opens the file the register expects.\n")
