"""CHANGELOG.md, from the commit subjects.

They are already written as headlines - "Invoices move off the role ladder onto
a flag of their own", "Nothing lists a CE mark" - which is no use to anybody
who cannot read the repository. This turns them into a file that can be.

The first paragraph of each body comes with the subject, because that is where
the reason lives and a list of headlines without reasons is a worse document
than no document.

    python tools/changelog.py
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEP = "\x1e"
FIELD = "\x1f"

# Lines that are machinery rather than history.
NOISE = re.compile(r"^(Co-Authored-By|Claude-Session|Signed-off-by|\s*$)", re.I)


def commits():
    out = subprocess.run(
        ["git", "log", "--no-merges", "--date=short",
         "--pretty=format:%H" + FIELD + "%ad" + FIELD + "%s" + FIELD + "%b" + SEP],
        cwd=ROOT, capture_output=True, timeout=60).stdout.decode("utf-8", "replace")
    for chunk in out.split(SEP):
        chunk = chunk.strip()
        if not chunk:
            continue
        sha, date, subject, body = (chunk.split(FIELD) + ["", "", "", ""])[:4]
        lines = [l for l in body.splitlines() if not NOISE.match(l)]
        # the first paragraph, which is the reason
        para = []
        for l in lines:
            if not l.strip() and para:
                break
            if l.strip():
                para.append(l.strip())
        yield {"sha": sha[:7], "date": date, "subject": subject,
               "why": " ".join(para)}


def main():
    rows = list(commits())
    by_day = {}
    order = []
    for c in rows:
        if c["date"] not in by_day:
            by_day[c["date"]] = []
            order.append(c["date"])
        by_day[c["date"]].append(c)

    out = ["# What has changed",
           "",
           "Generated from the commit subjects by `python tools/run.py changelog`.",
           "They are written as headlines on purpose; this is them, with the reason",
           "that came with each one, for anybody who cannot read the repository.",
           ""]
    for day in order:
        out.append("## " + day)
        out.append("")
        for c in by_day[day]:
            out.append("- **%s**  <sub>`%s`</sub>" % (c["subject"], c["sha"]))
            if c["why"]:
                why = c["why"]
                if len(why) > 400:
                    why = why[:400].rsplit(" ", 1)[0] + "…"
                out.append("  <br>%s" % why)
        out.append("")

    p = os.path.join(ROOT, "CHANGELOG.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
    print("wrote %s - %d commits across %d days" % (p, len(rows), len(order)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
