#!/usr/bin/env python3
"""Fall 2026 syllabus data — static, transcribed from the real syllabus PDFs.

WHY THIS FILE EXISTS
--------------------
Elliot's MIT graded deadlines live only in syllabus PDFs. They are not in
Notion, so every Notion-fed widget was blind to three exams, five problem
sets, two papers and the design reviews. A deadline widget that cannot see
an exam is not merely incomplete, it is falsely reassuring.

This module is DATA ONLY. It touches no network, no vault, no credential,
so it works identically on a laptop and inside the hourly GitHub Action.

Transcribed 2026-09-08 from:
  * 14_03_Fall_2026_Syllabus.pdf
  * Syllabus_20260906b.pdf            (IDS.412, "Version 2026-09-26")
  * 16.S896 syllabus                  ("Version 9, 2026-09-04")

RULE OBEYED THROUGHOUT: nothing is invented. Where the syllabus does not
state a date (14.003 Exam 3) the date is null and a note says so. Where a
weight cannot be attributed to a single event, weight is null and a note
explains, so a widget summing `weight` never double-counts.

Run standalone to write the JSON without a Notion token:
    python3 scripts/syllabus_fall2026.py
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

# kind vocabulary — small and controlled. Widgets may switch on these.
KINDS = {
    "pset", "exam", "paper", "presentation", "review",
    "milestone", "admin", "lecture", "recitation",
}

TERM = {
    "term": "Fall 2026",
    "classes_end": "2026-12-10",
    "finals_start": "2026-12-14",
    "finals_end": "2026-12-18",
    "add_date": "2026-10-09",
    "drop_date": "2026-11-18",
    # Registrar rule: no assignment may fall due after this date for a
    # subject that also has a final exam.
    "no_assignments_after": "2026-12-04",
    "thesis_title_due": "2026-12-12",
    "thesis_title_note": "Advanced degree thesis title due; $85 late fee after.",
}

# --------------------------------------------------------------------------
# Courses. has_syllabus=false is deliberate and load-bearing: a course that
# is silently omitted looks like a course with no work.
# --------------------------------------------------------------------------
COURSES = [
    {
        "code": "14.003",
        "title": "Microeconomic Theory and Public Policy",
        "units": 12,
        "meets": "Mon+Wed lectures, Fri recitation",
        "room": "",
        "instructor": "",
        "has_syllabus": True,
        "source": "14_03_Fall_2026_Syllabus.pdf",
        "grading": [],
        "note": "Syllabus does not publish a percentage breakdown; weights left null.",
    },
    {
        "code": "IDS.412",
        "alt_code": "17.310",
        "title": "Science, Technology and Public Policy",
        "units": 12,
        "meets": "Mon+Wed 1300-1430",
        "room": "66-168",
        "instructor": "Prof. Noelle Selin",
        "has_syllabus": True,
        "source": "Syllabus_20260906b.pdf (Version 2026-09-26)",
        "grading": [
            {"component": "Paper 1 (15% written + 5% conference)", "weight": 20},
            {"component": "Midterm", "weight": 20},
            {"component": "Final project presentation", "weight": 25},
            {"component": "Paper 2 (15% written + 5% conference)", "weight": 25},
            {"component": "Participation", "weight": 10},
        ],
        "note": "",
    },
    {
        "code": "16.S896",
        "title": "Planetary Surface Technology Development",
        "units": 12,
        "meets": "Fri 1500-1700",
        "room": "9-354",
        "instructor": "Dr. George Lordos",
        "has_syllabus": True,
        "source": "16.S896 syllabus (Version 9, 2026-09-04)",
        "grading": [
            {"component": "A1-A5 assignments (5% each)", "weight": 25},
            {"component": "Concept review (internal panel)", "weight": 15},
            {"component": "Draft proposal (5-7 pages)", "weight": 20},
            {"component": "Final presentation (external NASA/industry judges)", "weight": 20},
        ],
        "note": "Listed components total 80%; the remaining 20% is not itemised in the syllabus.",
    },
    {
        "code": "16.842",
        "title": None,
        "units": None,
        "meets": "",
        "room": "",
        "instructor": "",
        "has_syllabus": False,
        "source": None,
        "grading": [],
        "note": ("No syllabus available — not in Canvas at all. Title not transcribed. "
                 "Notion holds 19 items "
                 "for this subject including an oral exam and a final presentation, "
                 "but none of them are dated here. Treat as UNKNOWN, not as empty."),
    },
    {
        "code": "16.987",
        "title": None,
        "units": None,
        "meets": "",
        "room": "",
        "instructor": "",
        "has_syllabus": False,
        "source": None,
        "grading": [],
        "note": "No syllabus available; title not transcribed. Graded work, if any, is unknown.",
    },
    {
        "code": "16.990",
        "title": None,
        "units": None,
        "meets": "",
        "room": "",
        "instructor": "",
        "has_syllabus": False,
        "source": None,
        "grading": [],
        "note": "No syllabus available; title not transcribed. Graded work, if any, is unknown.",
    },
    {
        "code": "24.134",
        "title": "Experiential Ethics",
        "units": None,
        "meets": "",
        "room": "",
        "instructor": "",
        "has_syllabus": False,
        "source": None,
        "grading": [],
        "note": "Archived/finished. No syllabus data; no outstanding graded work.",
    },
]

# --------------------------------------------------------------------------
# No-class days. code=null means it applies to every course.
# --------------------------------------------------------------------------
NO_CLASS = [
    {"date": "2026-10-12", "reason": "Indigenous Peoples' Day", "code": None},
    {"date": "2026-11-11", "reason": "Veterans Day", "code": None},
    {"date": "2026-11-23", "reason": "Thanksgiving", "code": None},
    {"date": "2026-11-25", "reason": "Thanksgiving", "code": None},
    {"date": "2026-11-09", "reason": "Project conference week — no class", "code": "IDS.412"},
    {"date": "2026-11-27", "reason": "No recitation", "code": "14.003"},
    {"date": "2026-11-27", "reason": "No class", "code": "16.S896"},
]


def _ev(code, name, d, kind, *, time=None, weight=None, graded=False, note="", location=""):
    assert kind in KINDS, f"bad kind {kind!r}"
    return {
        "code": code,
        "name": name,
        "date": d,          # ISO string, or None when the syllabus gives no date
        "time": time,       # "2359", "1700-1830", or None
        "kind": kind,
        "weight": weight,   # percent of final grade, or None if not attributable
        "graded": graded,
        "note": note,
        "location": location,
    }


def _events():
    e = []

    # ---------------- 14.003 ----------------
    e += [
        _ev("14.003", "PS1 due", "2026-09-24", "pset", time="2359", graded=True),
        _ev("14.003", "PS2 due", "2026-10-07", "pset", time="2359", graded=True),
        _ev("14.003", "Exam 1", "2026-10-13", "exam", graded=True,
            note="Tuesday running on a Monday schedule."),
        _ev("14.003", "PS3 due", "2026-10-29", "pset", time="2359", graded=True),
        _ev("14.003", "PS4 due", "2026-11-12", "pset", time="2359", graded=True),
        _ev("14.003", "Exam 2", "2026-11-16", "exam", graded=True),
        _ev("14.003", "PS5 due", "2026-12-03", "pset", time="2359", graded=True),
        _ev("14.003", "Exam 3", None, "exam", graded=True,
            note=("DATE NOT PUBLISHED. The syllabus references Exam 3 "
                  "(\"tested on Exam #3 not Exam #2\") but never dates it. "
                  "No date has been invented — confirm with the instructor.")),
    ]
    for d in ["2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09",
              "2026-10-16", "2026-10-23", "2026-10-30", "2026-11-06", "2026-11-13",
              "2026-12-04"]:
        e.append(_ev("14.003", "Recitation", d, "recitation"))

    # ---------------- IDS.412 / 17.310 ----------------
    e += [
        _ev("IDS.412", "Paper 1 due", "2026-10-26", "paper", weight=20, graded=True,
            note="20% = 15% written + 5% conference."),
        _ev("IDS.412", "Midterm (in class)", "2026-11-04", "exam", weight=20, graded=True,
            note="Closed book; one 8.5x11 sheet, both sides.", location="66-168"),
        _ev("IDS.412", "Final presentations I", "2026-11-30", "presentation", graded=True,
            note="Weight null on purpose: the 25% final-presentation grade is shared "
                 "with the 2026-12-02 session; see course grading breakdown.",
            location="66-168"),
        _ev("IDS.412", "Final presentations II", "2026-12-02", "presentation", graded=True,
            note="Weight null on purpose: shares the 25% with 2026-11-30.",
            location="66-168"),
        _ev("IDS.412", "Paper 2 due", "2026-12-09", "paper", weight=25, graded=True,
            note="25% = 15% written + 5% conference."),
        _ev("IDS.412", "Paper 1 conferences (week of)", "2026-10-19", "milestone",
            note="Conferences run through the week beginning 2026-10-19."),
        _ev("IDS.412", "Paper 2 conferences (week of)", "2026-11-09", "milestone",
            note="Conferences run through the week beginning 2026-11-09; no lecture that week."),
    ]
    for d in ["2026-09-09", "2026-09-14", "2026-09-16", "2026-09-21", "2026-09-23",
              "2026-09-28", "2026-09-30", "2026-10-05", "2026-10-07", "2026-10-13",
              "2026-10-14", "2026-10-19", "2026-10-21", "2026-10-26", "2026-10-28",
              "2026-11-02", "2026-11-04", "2026-11-16", "2026-11-18", "2026-11-30",
              "2026-12-02", "2026-12-07", "2026-12-09"]:
        e.append(_ev("IDS.412", "Lecture", d, "lecture", time="1300-1430",
                     location="66-168",
                     note="Tuesday on a Monday schedule." if d == "2026-10-13" else ""))

    # ---------------- 16.S896 ----------------
    e += [
        _ev("16.S896", "NASA Challenges info session", "2026-09-14", "milestone",
            time="1700-1830", location="35-225",
            note="Monday special session, outside the normal Friday slot."),
        _ev("16.S896", "Skills survey due", "2026-09-18", "milestone",
            note="Gates team assignment."),
        _ev("16.S896", "Team assignments finalized", "2026-09-22", "milestone"),
        _ev("16.S896", "A1 due", "2026-10-09", "pset", weight=5, graded=True),
        _ev("16.S896", "WORMS hardware selections final, orders placed",
            "2026-10-09", "milestone"),
        _ev("16.S896", "RASC-AL Notice of Intent due", "2026-10-13", "milestone",
            note="Optional and non-binding."),
        _ev("16.S896", "Questions for NASA due", "2026-10-18", "milestone"),
        _ev("16.S896", "A2 due", "2026-10-23", "pset", weight=5, graded=True),
        _ev("16.S896", "Q&A with NASA subject matter experts", "2026-10-27", "milestone"),
        _ev("16.S896", "A3 due", "2026-11-06", "pset", weight=5, graded=True),
        _ev("16.S896", "Concept review", "2026-11-06", "review", weight=15, graded=True,
            note="Internal panel."),
        _ev("16.S896", "A4 due", "2026-11-13", "pset", weight=5, graded=True),
        _ev("16.S896", "Draft proposal", "2026-11-20", "review", weight=20, graded=True,
            note="5-7 pages."),
        _ev("16.S896", "A5 due", "2026-12-04", "pset", weight=5, graded=True),
        _ev("16.S896", "Final presentation", "2026-12-04", "presentation",
            weight=20, graded=True, note="External NASA/industry judges."),
    ]
    for d in ["2026-09-11", "2026-09-18", "2026-09-25", "2026-10-02", "2026-10-09",
              "2026-10-16", "2026-10-23", "2026-10-30", "2026-11-06", "2026-11-13",
              "2026-11-20", "2026-12-04"]:
        e.append(_ev("16.S896", "Class", d, "lecture", time="1500-1700", location="9-354"))

    # ---------------- Registrar (course-independent) ----------------
    e += [
        _ev(None, "Add Date", "2026-10-09", "admin", note="MIT Registrar."),
        _ev(None, "DROP DATE", "2026-11-18", "admin", note="MIT Registrar."),
        _ev(None, "Advanced degree thesis title due", "2026-12-12", "admin",
            note="MIT Registrar; $85 late fee after this date."),
        _ev(None, "Classes end", "2026-12-10", "admin"),
        _ev(None, "Final exam period begins", "2026-12-14", "admin"),
        _ev(None, "Final exam period ends", "2026-12-18", "admin"),
    ]
    return e


# --------------------------------------------------------------------------
# Validation. Runs every build. exit code 0 is not evidence of success, so
# this measures and raises rather than assuming.
# --------------------------------------------------------------------------
def validate(payload):
    problems = []
    codes = {c["code"] for c in payload["courses"]}
    codes |= {c.get("alt_code") for c in payload["courses"] if c.get("alt_code")}

    # global no-class dates apply to every course; course-scoped ones only to it
    global_nc = {n["date"]: n["reason"] for n in payload["no_class"] if n["code"] is None}
    scoped_nc = {}
    for n in payload["no_class"]:
        if n["code"]:
            scoped_nc.setdefault(n["code"], {})[n["date"]] = n["reason"]

    for ev in payload["events"]:
        if ev["code"] is not None and ev["code"] not in codes:
            problems.append(f"event {ev['name']!r} references unknown course {ev['code']!r}")
        if ev["kind"] not in KINDS:
            problems.append(f"event {ev['name']!r} has kind {ev['kind']!r} outside vocabulary")
        d = ev["date"]
        if d is None:
            if not ev["note"]:
                problems.append(f"undated event {ev['name']!r} carries no explanatory note")
            continue
        try:
            parsed = date.fromisoformat(d)
        except ValueError:
            problems.append(f"event {ev['name']!r} has unparseable date {d!r}")
            continue
        if parsed.isoformat() != d:
            problems.append(f"event {ev['name']!r} date {d!r} not canonical ISO")
        # An event that requires the class to physically meet must not land on
        # a no-class day. Due-dates (pset/paper/milestone/admin) legitimately
        # can — e.g. the IDS.412 Paper 2 conferences week has no lecture.
        if ev["kind"] not in ("lecture", "recitation", "exam", "presentation", "review"):
            continue
        if d in global_nc:
            problems.append(
                f"event {ev['name']!r} ({ev['code']}) falls on no-class day {d} "
                f"({global_nc[d]})")
        if ev["code"] and d in scoped_nc.get(ev["code"], {}):
            problems.append(
                f"event {ev['name']!r} falls on {ev['code']} no-class day {d} "
                f"({scoped_nc[ev['code']][d]})")

    for n in payload["no_class"]:
        try:
            date.fromisoformat(n["date"])
        except ValueError:
            problems.append(f"no_class entry has unparseable date {n['date']!r}")

    for k, v in payload["term"].items():
        if k.endswith(("_end", "_start", "_date", "_after", "_due")) and isinstance(v, str):
            try:
                date.fromisoformat(v)
            except ValueError:
                problems.append(f"term.{k} is not an ISO date: {v!r}")

    # registrar rule: graded work for a subject with a final exam must not
    # fall after no_assignments_after. Report, do not silently drop.
    cutoff = payload["term"]["no_assignments_after"]
    late = [e for e in payload["events"]
            if e["graded"] and e["date"] and e["date"] > cutoff
            and e["kind"] in ("pset", "paper", "review")]
    return problems, late


def summarize(payload):
    ev = payload["events"]
    dated = [e for e in ev if e["date"]]
    graded = [e for e in ev if e["graded"]]
    by_kind = {}
    for e in ev:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    return {
        "courses": len(payload["courses"]),
        "courses_with_syllabus": sum(1 for c in payload["courses"] if c["has_syllabus"]),
        "courses_without_syllabus": sum(1 for c in payload["courses"] if not c["has_syllabus"]),
        "events": len(ev),
        "graded_events": len(graded),
        "ungraded_events": len(ev) - len(graded),
        "dated_events": len(dated),
        "undated_events": len(ev) - len(dated),
        "exams": by_kind.get("exam", 0),
        "by_kind": dict(sorted(by_kind.items())),
        "no_class": len(payload["no_class"]),
    }


def build(now=None):
    """Return the syllabus payload dict. Pure; no I/O."""
    if now is None:
        now = datetime.now(timezone(timedelta(hours=-4)))
    events = _events()
    # stable order: dated ascending, undated last, then course then name
    events.sort(key=lambda e: (e["date"] is None, e["date"] or "", e["code"] or "", e["name"]))
    payload = {
        "generated": now.isoformat(timespec="seconds"),
        "source": "Fall 2026 syllabus PDFs, transcribed 2026-09-08",
        "term": TERM,
        "kinds": sorted(KINDS),
        "courses": COURSES,
        "events": events,
        "no_class": NO_CLASS,
    }
    payload["counts"] = summarize(payload)
    return payload


def write(out_dir, now=None, verbose=True):
    payload = build(now)
    problems, late = validate(payload)
    if problems:
        raise SystemExit("syllabus.json validation FAILED:\n  " + "\n  ".join(problems))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "syllabus.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
    c = payload["counts"]
    if verbose:
        print(f"wrote syllabus.json — {c['courses']} courses "
              f"({c['courses_with_syllabus']} with syllabus, "
              f"{c['courses_without_syllabus']} without), "
              f"{c['events']} events, {c['graded_events']} graded, "
              f"{c['exams']} exams, {c['dated_events']} dated / "
              f"{c['undated_events']} undated, {c['no_class']} no-class entries")
        for e in payload["events"]:
            if e["date"] is None:
                print(f"  undated: {e['code']} {e['name']} — {e['note'][:60]}...")
        for e in late:
            print(f"  NOTE: graded {e['code']} {e['name']} due {e['date']} is after "
                  f"the {payload['term']['no_assignments_after']} registrar cutoff "
                  f"(course has no final exam listed)")
    return payload


if __name__ == "__main__":
    write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data"))
