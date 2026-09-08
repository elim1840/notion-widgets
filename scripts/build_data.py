#!/usr/bin/env python3
"""Pull Notion data -> static JSON for the widgets.

Runs in GitHub Actions on a schedule. The Notion token comes from the
NOTION_API_KEY repo secret and NEVER reaches the browser: this script
writes plain JSON files that the widget pages read with no credentials.

Local run:  NOTION_API_KEY=... python3 scripts/build_data.py
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ.get("NOTION_API_KEY", "").strip()
if not TOKEN:
    sys.exit("NOTION_API_KEY not set")

VERSION = "2025-09-03"
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "data")

TASKS_DS = "cd1ad116-e9e2-4719-954d-e75189cf3ce3"   # Tasks & Meetings
CLASS_DS = "beb6c6ee-20b1-4c1d-a8c3-93b13fae040c"   # Class Database
ET = timezone(timedelta(hours=-4))                   # EDT; -5 in winter


def api(path, method="GET", body=None):
    req = urllib.request.Request(
        "https://api.notion.com/v1/" + path,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode() if body else None,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def query_all(ds, body=None):
    rows, cursor = [], None
    while True:
        b = dict(body or {})
        b["page_size"] = 100
        if cursor:
            b["start_cursor"] = cursor
        r = api(f"data_sources/{ds}/query", "POST", b)
        rows += r["results"]
        if not r.get("has_more"):
            return rows
        cursor = r["next_cursor"]


def txt(prop):
    if not prop:
        return ""
    t = prop.get("type")
    if t == "title":
        return "".join(x["plain_text"] for x in prop["title"])
    if t == "rich_text":
        return "".join(x["plain_text"] for x in prop["rich_text"])
    if t == "select":
        return (prop["select"] or {}).get("name", "")
    if t == "checkbox":
        return prop["checkbox"]
    if t == "date":
        return (prop["date"] or {}).get("start", "")
    return ""


def main():
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(ET)
    today = now.date()

    rows = query_all(TASKS_DS)

    tasks = []
    for r in rows:
        p = r["properties"]
        start = txt(p.get("Meeting Date"))
        d = p.get("Meeting Date", {}).get("date") or {}
        tasks.append({
            "name": txt(p.get("Name")),
            "date": start,
            "end": d.get("end") or "",
            "done": bool(txt(p.get("Done"))),
            "status": txt(p.get("Status")),
            "type": txt(p.get("Type")),
            "meeting_type": txt(p.get("Meeting Type")),
            "priority": txt(p.get("Priority")),
            "energy": txt(p.get("Energy")),
            "location": txt(p.get("Location")),
            "attendees": txt(p.get("Attendees")),
            "agenda": txt(p.get("Agenda")),
            "link": (p.get("Meeting Link") or {}).get("url") or "",
            "notes": txt(p.get("Notes")),
            "url": r.get("url", ""),
        })

    def on(d):
        return [t for t in tasks if t["date"][:10] == d.isoformat()]

    def upcoming(days):
        end = today + timedelta(days=days)
        out = [t for t in tasks
               if t["date"][:10] and today.isoformat() <= t["date"][:10] <= end.isoformat()
               and not t["done"]]
        return sorted(out, key=lambda t: t["date"])

    # 14-day completion history for the streak/chart widget
    hist = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        day = on(d)
        hist.append({
            "date": d.isoformat(),
            "total": len(day),
            "done": sum(1 for t in day if t["done"]),
        })

    payload = {
        "generated": now.isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "counts": {
            "total": len(tasks),
            "open": sum(1 for t in tasks if not t["done"]),
            "done": sum(1 for t in tasks if t["done"]),
            "today_total": len(on(today)),
            "today_done": sum(1 for t in on(today) if t["done"]),
            "overdue": sum(1 for t in tasks
                           if t["date"][:10] and t["date"][:10] < today.isoformat()
                           and not t["done"]),
        },
        "today_items": sorted(on(today), key=lambda t: t["date"]),
        "upcoming": upcoming(7)[:12],
        "history": hist,
    }

    with open(os.path.join(OUT, "tasks.json"), "w") as f:
        json.dump(payload, f, indent=1)

    print(f"wrote tasks.json — {payload['counts']['total']} tasks, "
          f"{payload['counts']['open']} open, "
          f"{payload['counts']['overdue']} overdue")

    # ---------------- week agenda ----------------
    # Monday-anchored week containing today, merging Tasks & Meetings with
    # the Class Database so classes and commitments share one column.
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    def in_week(iso):
        return bool(iso) and monday.isoformat() <= iso[:10] <= sunday.isoformat()

    events = []
    for t in tasks:
        if in_week(t["date"]) and t["type"] != "Task":
            events.append({
                "name": t["name"], "date": t["date"], "end": t.get("end") or "",
                "done": t["done"],
                "kind": t["meeting_type"] or "Meeting", "src": "task",
                "location": t.get("location") or "", "type": t.get("type") or "",
                "meeting_type": t.get("meeting_type") or "",
                "url": t["url"],
            })
        elif in_week(t["date"]) and t["type"] == "Task":
            events.append({
                "name": t["name"], "date": t["date"], "end": t.get("end") or "",
                "done": t["done"],
                "kind": t["meeting_type"] or "Task", "src": "task",
                "location": t.get("location") or "", "type": t.get("type") or "",
                "meeting_type": t.get("meeting_type") or "",
                "url": t["url"],
            })

    for r in query_all(CLASS_DS):
        p = r["properties"]
        d = txt(p.get("Date"))
        dobj = (p.get("Date") or {}).get("date") or {}
        cats = [o["name"] for o in (p.get("Class Category") or {}).get("multi_select", [])]
        if in_week(d):
            events.append({
                "name": txt(p.get("Class Item")),
                "date": d,
                "end": dobj.get("end") or "",
                "done": txt(p.get("Task Status")) == "Done",
                "kind": txt(p.get("Class Code")) or "Class",
                "src": "class",
                "location": txt(p.get("Room")),
                "type": ", ".join(cats),
                "meeting_type": "Class",
                "url": r.get("url", ""),
            })

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        items = sorted(
            (e for e in events if e["date"][:10] == d.isoformat()),
            key=lambda e: (len(e["date"]) <= 10, e["date"]),
        )
        days.append({
            "date": d.isoformat(),
            "is_today": d == today,
            "items": items,
        })

    week = {
        "generated": now.isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "monday": monday.isoformat(),
        "days": days,
        "total": len(events),
    }
    with open(os.path.join(OUT, "week.json"), "w") as f:
        json.dump(week, f, indent=1)

    print(f"wrote week.json — {len(events)} events "
          f"{monday.isoformat()}..{sunday.isoformat()}")


if __name__ == "__main__":
    main()
