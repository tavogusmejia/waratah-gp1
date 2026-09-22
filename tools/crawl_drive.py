"""Walk a public Drive folder and list every file in it.

A public folder page embeds its listing as `window['_DRIVE_ivd']`, a
hex-escaped JSON array. Each entry is [id, [parent], name, mimeType, ...].
Folders carry the vnd.google-apps.folder type, so the walk is: read a page,
record the files, recurse into the folders.
"""
import codecs, json, re, subprocess, sys, time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
FOLDER = "application/vnd.google-apps.folder"
BLOB = re.compile(r"_DRIVE_ivd'\]\s*=\s*'([^']+)'")


def page(fid):
    url = "https://drive.google.com/drive/folders/" + fid
    out = subprocess.run(["curl", "-sL", "-A", UA, url],
                         capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def listing(fid):
    """(files, folders) for one folder, or None when the page carries no blob."""
    m = BLOB.search(page(fid))
    if not m:
        return None
    raw = codecs.decode(m.group(1), "unicode_escape")
    entries = json.loads(raw)[0] or []
    files, folders = [], []
    for e in entries:
        eid, name, mime = e[0], e[2], e[3]
        (folders if mime == FOLDER else files).append((eid, name, mime))
    return files, folders


def walk(root):
    seen, files, blind = set(), [], []
    queue = [(root, "")]
    while queue:
        fid, path = queue.pop(0)
        if fid in seen:
            continue
        seen.add(fid)
        got = listing(fid)
        if got is None:
            blind.append(path or fid)
            print("  NO LISTING: " + (path or fid), file=sys.stderr)
            continue
        kids, subs = got
        for eid, name, mime in kids:
            files.append({"id": eid, "name": name, "mime": mime,
                          "path": (path + "/" + name).lstrip("/")})
        for eid, name, _ in subs:
            queue.append((eid, (path + "/" + name).lstrip("/")))
        print("  %-52s %2d files, %d folders"
              % ((path or "(root)")[:52], len(kids), len(subs)), file=sys.stderr)
        time.sleep(0.3)
    return files, blind


if __name__ == "__main__":
    root = sys.argv[1]
    files, blind = walk(root)
    json.dump({"files": files, "unreadable": blind},
              open("_drive.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    print("\n%d files, %d folders could not be read" % (len(files), len(blind)),
          file=sys.stderr)
