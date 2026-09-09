#!/usr/bin/env python3
"""Pull Google Calendar -> docs/data/gcal.json for the gcal widget.

WHY THIS EXISTS
---------------
Every other widget in this repo reads from Notion only. But most of the
real day lives in Google Calendar (lab meetings, committee meetings,
dinners, BBQs) and never reached the dashboard at all. This script is the
bridge.

CREDENTIAL RULE (same as scripts/build_data.py)
-----------------------------------------------
The OAuth refresh_token / client_secret / access_token live OUTSIDE this
repo, in ~/.hermes/, and are read at BUILD time only. Nothing secret is
ever written into docs/ -- that directory is published to GitHub Pages.
The widget fetches a plain, credential-free JSON file.

Local run:  python3 scripts/fetch_gcal.py
Override:   GOOGLE_TOKEN_FILE=... GOOGLE_CLIENT_SECRET_FILE=... DAYS=7
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
TOKEN_FILE = os.environ.get(
    "GOOGLE_TOKEN_FILE", os.path.join(HOME, ".hermes", "google_token.json"))
SECRET_FILE = os.environ.get(
    "GOOGLE_CLIENT_SECRET_FILE",
    os.path.join(HOME, ".hermes", "google_client_secret.json"))

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data")
DAYS = int(os.environ.get("DAYS", "7"))
ET = timezone(timedelta(hours=-4))          # EDT; -5 in winter

# Calendars worth showing, in display order. Anything not listed here is
# still fetched into "other" so a newly-added calendar is never silently
# dropped -- but these are the ones Yohan actually runs his life on.
USEFUL = [
    "yohanlim1113@gmail.com",       # personal, highest signal
    "yohanlim@mit.edu",             # MIT account -- picnics, discussions, runs
    "MIT Outlook",                  # Outlook import -- church, RASCAL meetings
    "APT 234",                      # roommates
    "Conf.Rm 33-407a ESL",          # lab room -- real research meetings
    "Deadlines",
    "Hermes Schedule",
    "AstroSource Team Calendar",
]

# GSC Events posts ~16 generic campus events a day. Real, but it drowns
# everything else, so it is fetched and kept SEPARATE rather than deleted:
# the widget shows it behind a toggle, off by default.
NOISY = ["GSC Events"]


# ---------------------------------------------------------------- auth
def access_token():
    """Refresh the OAuth access token. Never returns anything to disk."""
    tok = json.load(open(TOKEN_FILE))
    cid = tok.get("client_id")
    csec = tok.get("client_secret")
    if not (cid and csec):
        sec = json.load(open(SECRET_FILE))
        blob = sec.get("installed") or sec.get("web") or {}
        cid = cid or blob.get("client_id")
        csec = csec or blob.get("client_secret")
    refresh = tok.get("refresh_token")
    if not (cid and csec and refresh):
        sys.exit("missing client_id / client_secret / refresh_token")

    body = urllib.parse.urlencode({
        "client_id": cid,
        "client_secret": csec,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def api(url, token):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


# ---------------------------------------------------------------- fetch
def calendars(token):
    out, page = [], None
    while True:
        u = "https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=250"
        if page:
            u += "&pageToken=" + urllib.parse.quote(page)
        r = api(u, token)
        out += r.get("items", [])
        page = r.get("nextPageToken")
        if not page:
            return out


def events(token, cal_id, tmin, tmax):
    out, page = [], None
    base = ("https://www.googleapis.com/calendar/v3/calendars/"
            + urllib.parse.quote(cal_id, safe="")
            + "/events?singleEvents=true&orderBy=startTime&maxResults=250"
            + "&timeMin=" + urllib.parse.quote(tmin)
            + "&timeMax=" + urllib.parse.quote(tmax))
    while True:
        u = base + ("&pageToken=" + urllib.parse.quote(page) if page else "")
        r = api(u, token)
        out += r.get("items", [])
        page = r.get("nextPageToken")
        if not page:
            return out


def norm(ev, cal_name, noisy):
    """Google event -> flat record the widget can render with no logic."""
    s, e = ev.get("start", {}), ev.get("end", {})
    allday = "date" in s
    start = s.get("dateTime") or s.get("date") or ""
    end = e.get("dateTime") or e.get("date") or ""
    return {
        "title": (ev.get("summary") or "(no title)").strip(),
        "start": start,
        "end": end,
        "allday": allday,
        "day": start[:10],
        "location": (ev.get("location") or "").strip(),
        "calendar": cal_name,
        "noise": noisy,
        "status": ev.get("status", ""),
        "link": ev.get("htmlLink", ""),
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(ET)
    start_day = now.date()
    end_day = start_day + timedelta(days=DAYS)
    tmin = datetime.combine(start_day, datetime.min.time(), ET).isoformat()
    tmax = datetime.combine(end_day, datetime.min.time(), ET).isoformat()

    token = access_token()
    all_cals = calendars(token)
    by_name = {}
    for c in all_cals:
        by_name.setdefault(c.get("summaryOverride") or c.get("summary") or c["id"], c)

    wanted = []
    for name in USEFUL + NOISY:
        c = by_name.get(name)
        if c:
            wanted.append((name, c["id"], name in NOISY))
        else:
            wanted.append((name, None, name in NOISY))

    records, cal_report, errors = [], [], []
    for name, cid, noisy in wanted:
        if cid is None:
            cal_report.append({"name": name, "count": 0, "ok": False,
                               "noise": noisy, "error": "calendar not found"})
            errors.append(f"{name}: not found in calendarList")
            continue
        try:
            evs = events(token, cid, tmin, tmax)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as ex:
            code = getattr(ex, "code", "")
            cal_report.append({"name": name, "count": 0, "ok": False,
                               "noise": noisy, "error": f"fetch failed {code}".strip()})
            errors.append(f"{name}: fetch failed {code}".strip())
            continue
        keep = [norm(e, name, noisy) for e in evs
                if e.get("status") != "cancelled" and (e.get("start") or {})]
        keep = [k for k in keep if k["start"]]
        records += keep
        cal_report.append({"name": name, "count": len(keep), "ok": True,
                           "noise": noisy, "error": ""})

    def sortkey(r):
        return (r["day"], 0 if r["allday"] else 1, r["start"])

    records.sort(key=sortkey)

    days = []
    for i in range(DAYS):
        d = (start_day + timedelta(days=i)).isoformat()
        days.append({
            "date": d,
            "is_today": d == start_day.isoformat(),
            "events": [r for r in records if r["day"] == d and not r["noise"]],
            "campus": [r for r in records if r["day"] == d and r["noise"]],
        })

    payload = {
        "generated": now.isoformat(timespec="seconds"),
        "today": start_day.isoformat(),
        "range": {"from": start_day.isoformat(), "to": end_day.isoformat()},
        "calendars": cal_report,
        "errors": errors,
        "days": days,
        "total": sum(1 for r in records if not r["noise"]),
        "total_campus": sum(1 for r in records if r["noise"]),
    }

    with open(os.path.join(OUT, "gcal.json"), "w") as f:
        json.dump(payload, f, indent=1)

    print(f"wrote gcal.json — {payload['total']} events "
          f"(+{payload['total_campus']} campus/GSC) "
          f"{start_day} .. {end_day}")
    for c in cal_report:
        flag = "" if c["ok"] else "  !! " + c["error"]
        tag = " [noise]" if c["noise"] else ""
        print(f"  {c['count']:>4}  {c['name']}{tag}{flag}")
    if errors:
        print("ERRORS:", "; ".join(errors))


if __name__ == "__main__":
    main()
