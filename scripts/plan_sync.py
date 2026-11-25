#!/usr/bin/env python3
"""Sync the plan files to GitHub: labels, milestones, epics, issues and the project board.

docs/plan/*.md in this repository is the source of truth for every repository of the
project. Each plan file is one module. Its header gives the track, the phase and what the
module depends on:

    Track: A. Phase: 1. Size: L. Depends on: P0. Unlocks: P2.

Each issue line has the form

    - <ID> [type priority] Title -- Done when: ...

and sits under a heading that names the repository it belongs to:

    ### work-hub-backend

A "## Schedule" table gives every issue its week, from Monday to Sunday:

    | Week of | Issues |
    |---|---|
    | 2026-12-07 | P1-01, P1-02 |

The script keeps one epic per module in the home repository and one issue per line in the
repository of its heading, matched by the plan ID in a hidden marker in the body, so it
can be re-run at any time and resumes after a failure. An issue whose line moved under
another heading is transferred. Titles, bodies, issue types, the parent epic, milestones
with their due dates and the type, area, priority and phase labels are managed here, and
an issue nobody holds is assigned to the owner. Discussion belongs in issue comments, and
labels added by hand are kept. With --project the board gets every epic and issue and
their Priority, Phase, Track, Start and Target fields; --views and --guide keep the saved
views and the board's guide (see plan_board.py and docs/BOARD.md).

It is a dry run unless --apply is given. Writes are paced and retried with back-off to
stay under GitHub's secondary rate limits for content creation.

Usage:
    python scripts/plan_sync.py --check            # parse and validate only
    python scripts/plan_sync.py --project 2        # dry run
    python scripts/plan_sync.py --apply --only P0
    python scripts/plan_sync.py --apply --project 2 --views --guide
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys
import time

OWNER = "SrZafkiell"
HOME = "work-hub"
REPOS = ("work-hub", "work-hub-backend", "work-hub-frontend", "work-hub-desktop")
ASSIGNEE = OWNER
TASK_TYPE = "Task"
EPIC_TYPE = "Epic"
ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN_DIR = ROOT / "docs" / "plan"
GUIDE = ROOT / "docs" / "BOARD.md"
GUIDE_END = "<!-- maintenance -->"
PLAN_URL = f"https://github.com/{OWNER}/{HOME}/blob/main/docs/plan/"

MODULE = r"P[0-9]|M[0-9]{2}|R[0-9]"
ISSUE_LINE = re.compile(
    rf"^- (?P<id>(?P<ms>{MODULE})-[0-9]{{2}}) \[(?P<type>[a-z]+) (?P<prio>p[0-9])\] "
    r"(?P<title>.+?) -- Done when: (?P<done>.+)$"
)
HEADING = re.compile(rf"^# (?P<ms>{MODULE}) - (?P<name>.+)$")
HEADER = re.compile(
    r"^Track: (?P<track>[A-Z])\. Phase: (?P<phase>[0-9])\. Size: (?P<size>S|M|L|XL)\. "
    r"Depends on: (?P<deps>.+?)\. Unlocks: (?P<unlocks>.+)\.$"
)
MODULE_ID = re.compile(rf"\b(?:{MODULE})\b(?!-)")
REPO_HEADING = re.compile(r"^### (?P<repo>\S+)$")
WEEK_ROW = re.compile(r"^\| (?P<week>[0-9]{4}-[0-9]{2}-[0-9]{2}) \| (?P<ids>.+?) \|$")
MARKER = re.compile(r"<!-- plan-id: (?P<id>[A-Z][0-9]{1,2}-[0-9]{2}) -->")
EPIC_MARKER = re.compile(r"<!-- plan-epic: (?P<id>[A-Z][0-9]{1,2}) -->")
ISSUE_URL = re.compile(r"https://github\.com/[^/\s]+/(?P<repo>[^/\s]+)/issues/(?P<number>[0-9]+)")
RATE_LIMITED = re.compile(r"secondary rate limit|rate limit exceeded|abuse|HTTP 429", re.I)
GATEWAY = re.compile(r"HTTP 50[234]")

TYPES = {
    "feature": ("1f6feb", "New capability"),
    "bug": ("d73a4a", "Something is broken"),
    "chore": ("6e7781", "Setup and maintenance"),
    "ci": ("8250df", "CI/CD and automation"),
    "docs": ("0e8a16", "Documentation"),
    "security": ("b60205", "Security control or hardening"),
    "test": ("fbca04", "Tests and measurements"),
    "adr": ("5319e7", "Architecture decision record"),
    "spike": ("c5def5", "Time-boxed investigation"),
}
AREAS = {
    "P0": "foundation", "P1": "runtime", "P2": "delivery",
    "M01": "skeleton", "M02": "sign-in", "M03": "workspaces", "M04": "tasks",
    "M05": "notes-search", "M06": "calendars", "M07": "reminders", "M08": "meetings",
}
AREA_COLOR = "bfdadc"
# name: (label color, board color, meaning)
PRIORITIES = {
    "p1": ("d93f0b", "RED", "Blocks other work or a safety property"),
    "p2": ("f9d0c4", "YELLOW", "Part of the release"),
    "p3": ("fef2c0", "GRAY", "Can ship after the release"),
}
PHASES = {
    "1": ("BLUE", "Release v0.1.0"),
    "2": ("PURPLE", "Release v0.2.0"),
}
PHASE_COLOR = "d4c5f9"
TRACKS = {
    "A": ("Platform", "ORANGE", "Repository rules, server and delivery"),
    "B": ("Core", "GREEN", "Sign-in, workspaces, tasks and notes"),
    "C": ("Schedule", "PINK", "Calendars, reminders and meetings"),
}
# Labels set by hand, on an issue or a pull request, when they apply.
FLAGS = {
    "blocked": ("b60205", "Cannot move until something else is done"),
    "needs:decision": ("d876e3", "Waits for a decision by the owner"),
    "tech-debt": ("c5a35b", "Depth traded for time, to repay later"),
    "breaking-change": ("e11d21", "Pull request that breaks a published contract"),
}
MANAGED_PREFIXES = ("type:", "area:", "prio:", "phase:")
RETRIES = 6


def _paragraph(lines: list[str], start: int) -> str:
    """The paragraph that begins at lines[start], joined into one line."""
    para: list[str] = []
    for line in lines[start:]:
        if not line.strip() or line.startswith("#"):
            break
        para.append(line.strip())
    return " ".join(para)


def _goal(lines: list[str]) -> str:
    """First paragraph of the '## Goal' section, joined into one line."""
    try:
        start = lines.index("## Goal") + 1
    except ValueError:
        return ""
    while start < len(lines) and not lines[start].strip():
        start += 1
    return _paragraph(lines, start)


def _header(path: pathlib.Path, lines: list[str]) -> dict:
    """Track, phase, size and dependencies from the paragraph under the title."""
    start = next((n for n, line in enumerate(lines) if line.startswith("Track: ")), None)
    head = HEADER.match(_paragraph(lines, start)) if start is not None else None
    if not head:
        raise ValueError(
            f"{path.name}: the header must read 'Track: X. Phase: N. Size: S. "
            "Depends on: ... . Unlocks: ... .'"
        )
    if head["track"] not in TRACKS:
        raise ValueError(f"{path.name}: unknown track {head['track']}")
    if head["phase"] not in PHASES:
        raise ValueError(f"{path.name}: unknown phase {head['phase']}")
    deps = list(dict.fromkeys(MODULE_ID.findall(head["deps"])))
    unknown = [dep for dep in deps if dep not in AREAS]
    if unknown:
        raise ValueError(f"{path.name}: unknown module in 'Depends on': {', '.join(unknown)}")
    return {"track": head["track"], "phase": head["phase"], "size": head["size"], "deps": deps}


def _weeks(path: pathlib.Path, rows: list[tuple[int, str, str]], ids: list[str]) -> dict[str, str]:
    """Plan ID -> the Monday of its week, from the rows of the Schedule table."""
    weeks: dict[str, str] = {}
    last = ""
    for n, week, cell in rows:
        try:
            monday = datetime.date.fromisoformat(week).weekday() == 0
        except ValueError:
            monday = False
        if not monday:
            raise ValueError(f"{path.name}:{n}: {week} is not a Monday")
        if week <= last:
            raise ValueError(f"{path.name}:{n}: weeks must be in ascending order")
        last = week
        for plan_id in (part.strip() for part in cell.split(",")):
            if plan_id not in ids:
                raise ValueError(f"{path.name}:{n}: {plan_id} is not an issue of this file")
            if plan_id in weeks:
                raise ValueError(f"{path.name}:{n}: {plan_id} is scheduled twice")
            weeks[plan_id] = week
    missing = [plan_id for plan_id in ids if plan_id not in weeks]
    if missing:
        raise ValueError(f"{path.name}: no week in the Schedule for {', '.join(missing)}")
    return weeks


def _sunday(monday: str) -> str:
    return (datetime.date.fromisoformat(monday) + datetime.timedelta(days=6)).isoformat()


def parse_plan(plan_dir: pathlib.Path) -> tuple[list[dict], list[dict]]:
    """Read every plan file; fail loudly on anything the sync could get wrong."""
    milestones: list[dict] = []
    issues: list[dict] = []
    seen: set[str] = set()
    for path in sorted(plan_dir.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        head = HEADING.match(lines[0]) if lines else None
        if not head:
            raise ValueError(f"{path.name}: first line must be '# <ID> - <name>'")
        ms = head["ms"]
        if ms not in AREAS:
            raise ValueError(f"{path.name}: unknown milestone {ms}")
        if not path.name.startswith(ms + "-"):
            raise ValueError(f"{path.name}: heading {ms} does not match the file name")
        module = {
            "id": ms,
            "name": head["name"],
            "title": f"{ms} - {head['name']}",
            "file": path.name,
            "goal": _goal(lines),
            **_header(path, lines),
        }
        own: list[dict] = []
        rows: list[tuple[int, str, str]] = []
        section = ""
        repo = None
        for n, line in enumerate(lines, 1):
            if line.startswith("## "):
                section, repo = line[3:].strip(), None
                continue
            if section == "Schedule" and line.startswith("| ") and line[2:3].isdigit():
                row = WEEK_ROW.match(line)
                if not row:
                    raise ValueError(f"{path.name}:{n}: malformed schedule row")
                rows.append((n, row["week"], row["ids"]))
                continue
            if section == "Issues" and line.startswith("### "):
                m = REPO_HEADING.match(line)
                if not m or m["repo"] not in REPOS:
                    raise ValueError(f"{path.name}:{n}: unknown repository in '{line}'")
                repo = m["repo"]
                continue
            if not line.startswith("- ") or " -- Done when: " not in line:
                continue
            m = ISSUE_LINE.match(line)
            if not m:
                raise ValueError(f"{path.name}:{n}: malformed issue line")
            if repo is None:
                raise ValueError(f"{path.name}:{n}: {m['id']} is not under a repository heading")
            if m["ms"] != ms:
                raise ValueError(f"{path.name}:{n}: {m['id']} belongs to another milestone")
            if m["type"] not in TYPES:
                raise ValueError(f"{path.name}:{n}: unknown type [{m['type']}]")
            if m["prio"] not in PRIORITIES:
                raise ValueError(f"{path.name}:{n}: unknown priority [{m['prio']}]")
            if m["id"] in seen:
                raise ValueError(f"{path.name}:{n}: duplicate ID {m['id']}")
            seen.add(m["id"])
            own.append({
                "id": m["id"],
                "milestone": ms,
                "repo": repo,
                "type": m["type"],
                "prio": m["prio"],
                "phase": module["phase"],
                "track": module["track"],
                "title": m["title"],
                "done": m["done"],
                "file": path.name,
            })
        if not own:
            raise ValueError(f"{path.name}: no issues")
        weeks = _weeks(path, rows, [issue["id"] for issue in own])
        for issue in own:
            issue["start"] = weeks[issue["id"]]
            issue["target"] = _sunday(weeks[issue["id"]])
        module["start"] = min(issue["start"] for issue in own)
        module["target"] = max(issue["target"] for issue in own)
        milestones.append(module)
        issues.extend(own)
    return milestones, issues


def issue_body(issue: dict) -> str:
    return (
        f"**Done when:** {issue['done']}\n\n"
        f"Plan: [docs/plan/{issue['file']}]({PLAN_URL}{issue['file']})\n\n"
        f"<!-- plan-id: {issue['id']} -->\n"
    )


def issue_labels(issue: dict) -> list[str]:
    return [
        f"type:{issue['type']}",
        f"area:{AREAS[issue['milestone']]}",
        f"prio:{issue['prio']}",
        f"phase:{issue['phase']}",
    ]


def epic_title(module: dict) -> str:
    return f"{module['id']} {module['name']}"


def epic_body(module: dict) -> str:
    return (
        f"**Goal:** {module['goal']}\n\n"
        f"**Depends on:** {', '.join(module['deps']) or 'nothing'}\n\n"
        "The issues of this module, in every repository, are the sub-issues of this epic.\n\n"
        f"Plan: [docs/plan/{module['file']}]({PLAN_URL}{module['file']})\n\n"
        f"<!-- plan-epic: {module['id']} -->\n"
    )


def epic_labels(module: dict) -> list[str]:
    return [f"area:{AREAS[module['id']]}", f"phase:{module['phase']}"]


def merged_labels(current: list[str], wanted: list[str]) -> list[str]:
    """Wanted managed labels plus any label someone added by hand."""
    manual = [name for name in current if not name.startswith(MANAGED_PREFIXES)]
    return manual + [name for name in wanted if name not in manual]


def repos_in_use(issues: list[dict]) -> list[str]:
    """Repositories that have at least one issue, in the order of REPOS."""
    used = {issue["repo"] for issue in issues} | {HOME}
    return [repo for repo in REPOS if repo in used]


def milestones_of(repo: str, milestones: list[dict], issues: list[dict]) -> list[dict]:
    """The milestones a repository needs: all of them at home, where the epics live."""
    if repo == HOME:
        return list(milestones)
    used = {issue["milestone"] for issue in issues if issue["repo"] == repo}
    return [m for m in milestones if m["id"] in used]


def wanted_labels(repo: str, milestones: list[dict], issues: list[dict]) -> dict[str, tuple[str, str]]:
    """Every label the repository must have: name -> (color, description)."""
    want = {f"type:{name}": spec for name, spec in TYPES.items()}
    for m in milestones_of(repo, milestones, issues):
        want[f"area:{AREAS[m['id']]}"] = (AREA_COLOR, f"Milestone {m['title']}")
    for name, (color, _board, meaning) in PRIORITIES.items():
        want[f"prio:{name}"] = (color, meaning)
    for name, (_board, meaning) in PHASES.items():
        want[f"phase:{name}"] = (PHASE_COLOR, meaning)
    want.update(FLAGS)
    return want


def board_fields() -> list[dict]:
    """The custom fields of the board, with the options of the single-select ones."""
    return [
        {"name": "Priority", "type": "SINGLE_SELECT", "options": [
            (name.upper(), color, meaning) for name, (_label, color, meaning) in PRIORITIES.items()]},
        {"name": "Phase", "type": "SINGLE_SELECT", "options": [
            (f"Phase {name}", color, meaning) for name, (color, meaning) in PHASES.items()]},
        {"name": "Track", "type": "SINGLE_SELECT", "options": [
            (f"{key} {name}", color, meaning) for key, (name, color, meaning) in TRACKS.items()]},
        {"name": "Start", "type": "DATE", "options": []},
        {"name": "Target", "type": "DATE", "options": []},
    ]


def board_values(item: dict, epic: bool = False) -> dict[str, str]:
    """Field values of a module (its epic) or of an issue on the board."""
    values = {
        "Phase": f"Phase {item['phase']}",
        "Track": f"{item['track']} {TRACKS[item['track']][0]}",
        "Start": item["start"],
        "Target": item["target"],
    }
    if not epic:
        values["Priority"] = item["prio"].upper()
    return values


def board_guide(text: str) -> str:
    """The part of docs/BOARD.md that is published as the README of the board."""
    return text.split(GUIDE_END, 1)[0].strip() + "\n"


def gh(args: list[str], payload: dict | None = None, pace: float = 0.0,
       repeatable: bool = False) -> str:
    """Run gh; retry with back-off on rate limits; sleep `pace` after a write.

    A gateway error is retried only for a call that is safe to send twice.
    """
    for attempt in range(RETRIES):
        proc = subprocess.run(
            ["gh", *args],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode == 0:
            if pace:
                time.sleep(pace)
            return proc.stdout
        err = (proc.stderr + proc.stdout).strip()
        if RATE_LIMITED.search(err) and attempt < RETRIES - 1:
            wait = 60 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s", flush=True)
            time.sleep(wait)
            continue
        if repeatable and GATEWAY.search(err) and attempt < RETRIES - 1:
            wait = 10 * (attempt + 1)
            print(f"  gateway error, retrying in {wait}s", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"gh {' '.join(args)} failed: {err}")
    raise RuntimeError("unreachable")


def api_list(path: str) -> list[dict]:
    out = gh(["api", "--paginate", path, "--jq", ".[] | tojson"], repeatable=True)
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def sync_labels(milestones: list[dict], issues: list[dict], apply: bool, pace: float) -> None:
    for repo in repos_in_use(issues):
        have = {label["name"] for label in api_list(f"repos/{OWNER}/{repo}/labels?per_page=100")}
        for name, (color, description) in wanted_labels(repo, milestones, issues).items():
            if name in have:
                continue
            print(f"label + {repo} {name}", flush=True)
            if apply:
                gh(["api", "--method", "POST", f"repos/{OWNER}/{repo}/labels", "--input", "-"],
                   {"name": name, "color": color, "description": description}, pace)


def sync_milestones(milestones: list[dict], issues: list[dict], apply: bool,
                    pace: float) -> dict[tuple[str, str], int]:
    """Create each milestone in every repository that needs it, due on its last day.

    Milestones are matched by their ID prefix, so a renamed one is updated in place.
    """
    numbers: dict[tuple[str, str], int] = {}
    for repo in repos_in_use(issues):
        base = f"repos/{OWNER}/{repo}/milestones"
        have = {}
        for cur in api_list(f"{base}?state=all&per_page=100"):
            have[cur["title"].split(" - ", 1)[0]] = cur
        for m in milestones_of(repo, milestones, issues):
            want = {
                "title": m["title"],
                "description": f"{m['goal']}\n\nPlan: {PLAN_URL}{m['file']}",
                "due_on": f"{m['target']}T12:00:00Z",
            }
            cur = have.get(m["id"])
            if cur is None:
                print(f"milestone + {repo} {m['title']}", flush=True)
                if apply:
                    out = gh(["api", "--method", "POST", base, "--input", "-"], want, pace)
                    numbers[(repo, m["id"])] = json.loads(out)["number"]
                continue
            numbers[(repo, m["id"])] = cur["number"]
            if (cur["title"] != want["title"]
                    or (cur.get("description") or "") != want["description"]
                    or (cur.get("due_on") or "")[:10] != m["target"]):
                print(f"milestone ~ {repo} {m['title']}", flush=True)
                if apply:
                    gh(["api", "--method", "PATCH", f"{base}/{cur['number']}", "--input", "-"],
                       want, pace, repeatable=True)
    return numbers


def _differs(cur: dict, want: dict) -> bool:
    cur_labels = sorted(label["name"] for label in cur.get("labels", []))
    cur_milestone = cur["milestone"]["number"] if cur.get("milestone") else None
    return (
        cur["title"] != want["title"]
        or (cur.get("body") or "").replace("\r\n", "\n") != want["body"]
        or cur_labels != sorted(want["labels"])
        or ("milestone" in want and cur_milestone != want["milestone"])
        or (cur.get("type") or {}).get("name") != want["type"]
        or "assignees" in want
    )


def wanted(cur: dict | None, title: str, body: str, labels: list[str], issue_type: str,
           milestone: int | None) -> dict:
    """The fields the sync manages on an issue; the owner takes one nobody holds."""
    want = {
        "title": title,
        "body": body,
        "labels": merged_labels([label["name"] for label in cur.get("labels", [])] if cur else [],
                                labels),
        "type": issue_type,
    }
    if milestone is not None:
        want["milestone"] = milestone
    if cur is None or not cur.get("assignees"):
        want["assignees"] = [ASSIGNEE]
    return want


def find_existing() -> tuple[dict[str, tuple[str, dict]], dict[str, dict]]:
    """Issues that carry a plan ID, in any repository, and the epics at home."""
    existing: dict[str, tuple[str, dict]] = {}
    epics: dict[str, dict] = {}
    for repo in REPOS:
        for item in api_list(f"repos/{OWNER}/{repo}/issues?state=all&per_page=100"):
            if "pull_request" in item:
                continue
            body = item.get("body") or ""
            epic = EPIC_MARKER.search(body)
            if epic and repo == HOME:
                if epic["id"] in epics:
                    print(f"warning: more than one epic for {epic['id']}", flush=True)
                epics.setdefault(epic["id"], item)
                continue
            mark = MARKER.search(body)
            if not mark:
                continue
            if mark["id"] in existing:
                print(f"warning: plan ID {mark['id']} is on more than one issue", flush=True)
            existing.setdefault(mark["id"], (repo, item))
    return existing, epics


def transfer(number: int, source: str, target: str, pace: float) -> dict:
    """Move an issue to another repository and return it as it is there."""
    out = gh(["issue", "transfer", str(number), f"{OWNER}/{target}",
              "--repo", f"{OWNER}/{source}"], pace=pace)
    moved = ISSUE_URL.search(out)
    if not moved or moved["repo"] != target:
        raise RuntimeError(f"transfer of {source}#{number} gave no issue URL: {out.strip()}")
    return json.loads(gh(["api", f"repos/{OWNER}/{target}/issues/{moved['number']}"]))


def sync_epics(milestones: list[dict], numbers: dict[tuple[str, str], int], epics: dict[str, dict],
               only: set[str] | None, apply: bool, pace: float) -> dict[str, dict]:
    """One epic per module in the home repository; returns module ID -> epic."""
    base = f"repos/{OWNER}/{HOME}/issues"
    created = updated = unchanged = 0
    for module in milestones:
        if only and module["id"] not in only:
            continue
        cur = epics.get(module["id"])
        want = wanted(cur, epic_title(module), epic_body(module), epic_labels(module), EPIC_TYPE,
                      numbers.get((HOME, module["id"])))
        if cur is None:
            created += 1
            print(f"epic + {HOME} {want['title']}", flush=True)
            if apply:
                out = gh(["api", "--method", "POST", base, "--input", "-"], want, pace)
                epics[module["id"]] = json.loads(out)
        elif _differs(cur, want):
            updated += 1
            print(f"epic ~ {HOME}#{cur['number']} {want['title']}", flush=True)
            if apply:
                gh(["api", "--method", "PATCH", f"{base}/{cur['number']}", "--input", "-"],
                   want, pace, repeatable=True)
        else:
            unchanged += 1
    print(f"epics: {created} to create, {updated} to update, {unchanged} unchanged", flush=True)
    return epics


def sync_issues(issues: list[dict], numbers: dict[tuple[str, str], int],
                existing: dict[str, tuple[str, dict]], only: set[str] | None, apply: bool,
                pace: float) -> dict[str, dict]:
    """One issue per plan line, in its repository; returns plan ID -> issue."""
    plan_ids = {issue["id"] for issue in issues}
    for orphan in sorted(set(existing) - plan_ids):
        repo, item = existing[orphan]
        print(f"warning: {repo}#{item['number']} ({orphan}) is no longer in the plan", flush=True)

    records: dict[str, dict] = {}
    created = moved = updated = unchanged = 0
    for issue in issues:
        if only and issue["milestone"] not in only:
            continue
        repo = issue["repo"]
        base = f"repos/{OWNER}/{repo}/issues"
        cur_repo, cur = existing.get(issue["id"], (repo, None))
        if cur is not None and cur_repo != repo:
            moved += 1
            print(f"issue > {cur_repo}#{cur['number']} to {repo}: {issue['id']} {issue['title']}",
                  flush=True)
            if not apply:
                continue
            cur = transfer(cur["number"], cur_repo, repo, pace)
        want = wanted(cur, f"{issue['id']} {issue['title']}", issue_body(issue),
                      issue_labels(issue), TASK_TYPE, numbers.get((repo, issue["milestone"])))
        if cur is None:
            created += 1
            print(f"issue + {repo} {want['title']}", flush=True)
            if apply:
                out = gh(["api", "--method", "POST", base, "--input", "-"], want, pace)
                records[issue["id"]] = json.loads(out)
            continue
        records[issue["id"]] = cur
        if _differs(cur, want):
            updated += 1
            print(f"issue ~ {repo}#{cur['number']} {want['title']}", flush=True)
            if apply:
                gh(["api", "--method", "PATCH", f"{base}/{cur['number']}", "--input", "-"],
                   want, pace, repeatable=True)
        else:
            unchanged += 1
    print(f"issues: {created} to create, {moved} to move, {updated} to update, "
          f"{unchanged} unchanged", flush=True)
    return records


def sync_parents(issues: list[dict], records: dict[str, dict], epics: dict[str, dict],
                 only: set[str] | None, apply: bool, pace: float) -> None:
    """Make every issue a sub-issue of the epic of its module."""
    linked = 0
    for ms, epic in epics.items():
        if only and ms not in only:
            continue
        path = f"repos/{OWNER}/{HOME}/issues/{epic['number']}/sub_issues"
        have = {sub["id"] for sub in api_list(f"{path}?per_page=100")}
        for issue in issues:
            record = records.get(issue["id"])
            if issue["milestone"] != ms or record is None or record["id"] in have:
                continue
            linked += 1
            print(f"parent + {HOME}#{epic['number']} gets {issue['repo']}#{record['number']} "
                  f"{issue['id']}", flush=True)
            if apply:
                gh(["api", "--method", "POST", path, "--input", "-"],
                   {"sub_issue_id": record["id"], "replace_parent": True}, pace)
    print(f"parents: {linked} to link", flush=True)


def board_cards(milestones: list[dict], issues: list[dict], records: dict[str, dict],
                epics: dict[str, dict]) -> dict[str, dict[str, str]]:
    """Issue URL -> the field values its card must carry."""
    cards: dict[str, dict[str, str]] = {}
    for module in milestones:
        if module["id"] in epics:
            cards[epics[module["id"]]["html_url"]] = board_values(module, epic=True)
    for issue in issues:
        if issue["id"] in records:
            cards[records[issue["id"]]["html_url"]] = board_values(issue)
    return cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    parser.add_argument("--only", help="comma-separated milestone IDs, for example P0,M01")
    parser.add_argument("--project", type=int, help="number of the user project to fill")
    parser.add_argument("--views", action="store_true", help="also keep the saved views of the board")
    parser.add_argument("--guide", action="store_true", help="also publish docs/BOARD.md on the board")
    parser.add_argument("--pace", type=float, default=3.0, help="seconds to wait after each write")
    parser.add_argument("--check", action="store_true", help="only parse and validate the plan")
    args = parser.parse_args(argv)

    milestones, issues = parse_plan(PLAN_DIR)
    per_repo = ", ".join(
        f"{repo} {sum(1 for issue in issues if issue['repo'] == repo)}"
        for repo in repos_in_use(issues)
    )
    print(f"plan: {len(milestones)} milestones, {len(issues)} issues ({per_repo})", flush=True)
    if args.check:
        return 0
    only = set(args.only.split(",")) if args.only else None
    if only and only - set(AREAS):
        parser.error(f"unknown milestone IDs: {', '.join(sorted(only - set(AREAS)))}")
    if (args.views or args.guide) and not args.project:
        parser.error("--views and --guide need --project")

    sync_labels(milestones, issues, args.apply, args.pace)
    numbers = sync_milestones(milestones, issues, args.apply, args.pace)
    existing, epics = find_existing()
    epics = sync_epics(milestones, numbers, epics, only, args.apply, args.pace)
    records = sync_issues(issues, numbers, existing, only, args.apply, args.pace)
    sync_parents(issues, records, epics, only, args.apply, args.pace)
    if args.project:
        import plan_board

        board = plan_board.Board(gh, OWNER, args.project, args.apply, args.pace)
        board.sync_items(list(board_cards(milestones, issues, records, epics)))
        board.sync_fields(board_fields())
        board.sync_values(board_cards(milestones, issues, records, epics))
        if args.views:
            board.sync_views()
        if args.guide:
            board.sync_guide(board_guide(GUIDE.read_text(encoding="utf-8")))
    if not args.apply:
        print("dry run: nothing changed; pass --apply to make these changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
