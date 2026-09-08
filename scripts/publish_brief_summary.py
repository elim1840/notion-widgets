#!/usr/bin/env python3
"""
Extract the morning brief's abstract into docs/data/brief.json so the Today
sidebar can show it.

Runs on the Mac (where the vault lives), not in the GitHub Action -- the vault
is not in the repo. Publishes only the abstract lines, never the full brief:
the brief can contain private research and calendar detail, and docs/ is a
PUBLIC GitHub Pages site.

Usage:  python3 scripts/publish_brief_summary.py
"""
import json
import os
import re
import html
import datetime
import glob

VAULT = os.path.expanduser("~/Yohans-2nd-Brain")
HTML_DIR = os.path.join(VAULT, "z_System/Briefs/Archive/html")
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "data", "brief.json")

# Notion page that always holds today's brief PDF.
BRIEF_PAGE = "https://app.notion.com/p/Daily-Brief-3d5ea74eb7798179899ee61e32e8dc1f"


def text_lines(path):
    raw = open(path, errors="replace").read()
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S)
    raw = re.sub(r"<[^>]+>", "\n", raw)
    raw = html.unescape(raw)
    return [l.strip() for l in raw.split("\n") if l.strip()]


def main():
    today = datetime.date.today().isoformat()
    path = os.path.join(HTML_DIR, f"{today} Brief.html")

    if not os.path.exists(path):
        # Fall back to the most recent brief, but say so plainly rather than
        # letting a stale brief masquerade as today's.
        cands = sorted(glob.glob(os.path.join(HTML_DIR, "*.html")))
        if not cands:
            payload = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                       "date": None, "stale": True, "lines": [],
                       "note": "no brief found", "url": BRIEF_PAGE}
            json.dump(payload, open(OUT, "w"), indent=1)
            print("no brief found")
            return
        path = cands[-1]

    fname = os.path.basename(path)
    brief_date = fname.split(" ")[0]
    stale = brief_date != today

    lines = text_lines(path)

    # The abstract sits between the "Abstract" heading and the "I." section mark.
    out = []
    try:
        i = lines.index("Abstract")
        for l in lines[i + 1:]:
            if re.fullmatch(r"[IVX]+\.", l):
                break
            out.append(l)
    except ValueError:
        out = []

    # Stitch fragments the HTML-to-text pass split mid-sentence.
    merged = []
    for l in out:
        if merged and not re.search(r"[.;:!?]$", merged[-1]) and len(merged[-1]) < 110:
            merged[-1] = (merged[-1] + " " + l).strip()
        else:
            merged.append(l)

    merged = [m for m in merged if len(m) > 12][:6]

    payload = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "date": brief_date,
        "stale": stale,
        "lines": merged,
        "url": BRIEF_PAGE,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(payload, open(OUT, "w"), indent=1)
    print(f"wrote brief.json — {brief_date}"
          f"{' (STALE)' if stale else ''}, {len(merged)} lines")
    for m in merged:
        print("   ", m[:88])


if __name__ == "__main__":
    main()
