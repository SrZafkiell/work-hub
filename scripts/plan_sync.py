#!/usr/bin/env python3
"""Sync the plan files to GitHub: labels, milestones, epics, tasks, steps and the board.

docs/plan/*.md in this repository is the source of truth for every repository of the
project. Each plan file is one module. Its header gives the track, the phase and what the
module depends on:

    Track: A. Phase: 1. Size: L. Depends on: P0. Unlocks: P2.

The work has three levels. The module is the epic. A task is a deliverable of the module,
a line of the "## Tasks" section that names its steps:

    - <ID> [type] Title -- Done when: ... -- Steps: <step ID>, <step ID>

A step is one piece of work, a line of the "## Steps" section

    - <ID> [type priority size] Title -- Done when: ...

under a heading that names the repository it belongs to:

    ### work-hub-backend

The size is S, M or L and stands for the planned hours in SIZES. A "## Schedule" table
gives every step its week, from Monday to Sunday:

    | Week of | Steps |
    |---|---|
    | 2026-12-07 | P1-01, P1-02 |

A task takes its priority, its dates and its hours from its steps.

The script keeps one epic per module and one issue per task in the home repository, and
one issue per step in the repository of its heading. Each is matched by its plan ID in a
hidden marker in the body, so the script can be re-run at any time and resumes after a
failure. A step whose line moved under another heading is transferred. Titles, bodies,
issue types, parents (epic, then task, then step), milestones with their due dates and the
type, area, priority and phase labels are managed here, and an issue nobody holds is
assigned to the owner. Discussion belongs in issue comments, and labels added by hand are
kept. With --project the board gets every epic, task and step and their Priority, Phase,
Track, Estimate, Start and Target fields; --views and --guide keep the saved views and the
board's guide (see plan_board.py and docs/BOARD.md).

docs/PLAN.md lists the tasks and the hours of every week between marker comments. --write
refreshes those tables and --check fails when they are behind the plan files.

It is a dry run unless --apply is given. Writes are paced and retried with back-off to
stay under GitHub's secondary rate limits for content creation.

Usage:
    python scripts/plan_sync.py --check            # parse and validate only
    python scripts/plan_sync.py --write            # refresh the tables of docs/PLAN.md
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
EPIC_TYPE = "Epic"
TASK_TYPE = "Task"
STEP_TYPE = "Step"
ISSUE_TYPES_URL = "https://github.com/settings/issue-types"
# Planned hours of a step, by size. An estimate, corrected from what the weeks really take.
SIZES = {"S": 0.5, "M": 1, "L": 3}
ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN_DIR = ROOT / "docs" / "plan"
PLAN_DOC = ROOT / "docs" / "PLAN.md"
GUIDE = ROOT / "docs" / "BOARD.md"
GUIDE_END = "<!-- maintenance -->"
PLAN_URL = f"https://github.com/{OWNER}/{HOME}/blob/main/docs/plan/"

MODULE = r"P[0-9]|M[0-9]{2}|R[0-9]"
TASK_LINE = re.compile(
    rf"^- (?P<id>(?P<ms>{MODULE})-[A-Z]) \[(?P<type>[a-z]+)\] (?P<title>.+?) "
    r"-- Done when: (?P<done>.+?) -- Steps: (?P<steps>.+)$"
)
STEP_LINE = re.compile(
    rf"^- (?P<id>(?P<ms>{MODULE})-[0-9]{{2}}) \[(?P<type>[a-z]+) (?P<prio>p[0-9]) (?P<size>[A-Z]+)\] "
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
# The hidden marker that ties an issue to its line in the plan, per level.
MARKERS = {
    "epic": re.compile(r"<!-- plan-epic: (?P<id>[A-Z][0-9]{1,2}) -->"),
    "task": re.compile(r"<!-- plan-task: (?P<id>[A-Z][0-9]{1,2}-[A-Z]) -->"),
    "step": re.compile(r"<!-- plan-id: (?P<id>[A-Z][0-9]{1,2}-[0-9]{2}) -->"),
}
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
TYPES_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) { issueTypes(first: 50) { nodes { name isEnabled } } }
}
"""


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
                raise ValueError(f"{path.name}:{n}: {plan_id} is not a step of this file")
            if plan_id in weeks:
                raise ValueError(f"{path.name}:{n}: {plan_id} is scheduled twice")
            weeks[plan_id] = week
    missing = [plan_id for plan_id in ids if plan_id not in weeks]
    if missing:
        raise ValueError(f"{path.name}: no week in the Schedule for {', '.join(missing)}")
    return weeks


def _sunday(monday: str) -> str:
    return (datetime.date.fromisoformat(monday) + datetime.timedelta(days=6)).isoformat()


def _line(path: pathlib.Path, n: int, line: str, pattern: re.Pattern, module: dict,
          seen: set[str]) -> re.Match:
    """Match a task or a step line and check what both kinds share."""
    m = pattern.match(line)
    kind = "task" if pattern is TASK_LINE else "step"
    if not m:
        raise ValueError(f"{path.name}:{n}: malformed {kind} line")
    if m["ms"] != module["id"]:
        raise ValueError(f"{path.name}:{n}: {m['id']} belongs to another milestone")
    if m["type"] not in TYPES:
        raise ValueError(f"{path.name}:{n}: unknown type [{m['type']}]")
    if m["id"] in seen:
        raise ValueError(f"{path.name}:{n}: duplicate ID {m['id']}")
    seen.add(m["id"])
    return m


def _group(path: pathlib.Path, tasks: list[dict], steps: list[dict]) -> None:
    """Give every step its task, and every task what it takes from its steps."""
    by_id = {step["id"]: step for step in steps}
    for task in tasks:
        for step_id in task["steps"]:
            step = by_id.get(step_id)
            if step is None:
                raise ValueError(f"{path.name}: {task['id']} names {step_id}, "
                                 "which is not a step of this file")
            if "task" in step:
                raise ValueError(f"{path.name}: {step_id} is in {step['task']} and in {task['id']}")
            step["task"] = task["id"]
        own = [by_id[step_id] for step_id in task["steps"]]
        task["prio"] = min(step["prio"] for step in own)
        task["start"] = min(step["start"] for step in own)
        task["target"] = max(step["target"] for step in own)
        task["hours"] = sum(step["hours"] for step in own)
    loose = [step["id"] for step in steps if "task" not in step]
    if loose:
        raise ValueError(f"{path.name}: no task for {', '.join(loose)}")


def parse_plan(plan_dir: pathlib.Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Read every plan file; fail loudly on anything the sync could get wrong.

    Returns the modules, the tasks and the steps.
    """
    milestones: list[dict] = []
    tasks: list[dict] = []
    steps: list[dict] = []
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
        shared = {"milestone": ms, "phase": module["phase"], "track": module["track"],
                  "file": path.name}
        own_tasks: list[dict] = []
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
            if section == "Steps" and line.startswith("### "):
                m = REPO_HEADING.match(line)
                if not m or m["repo"] not in REPOS:
                    raise ValueError(f"{path.name}:{n}: unknown repository in '{line}'")
                repo = m["repo"]
                continue
            if not line.startswith("- ") or " -- Done when: " not in line:
                continue
            if section == "Tasks":
                m = _line(path, n, line, TASK_LINE, module, seen)
                own_tasks.append({
                    "id": m["id"], "repo": HOME, "type": m["type"], "title": m["title"],
                    "done": m["done"], "steps": [part.strip() for part in m["steps"].split(",")],
                    **shared,
                })
                continue
            if repo is None:
                raise ValueError(f"{path.name}:{n}: this step is not under a repository heading "
                                 "of the Steps section")
            m = _line(path, n, line, STEP_LINE, module, seen)
            if m["prio"] not in PRIORITIES:
                raise ValueError(f"{path.name}:{n}: unknown priority [{m['prio']}]")
            if m["size"] not in SIZES:
                raise ValueError(f"{path.name}:{n}: unknown size [{m['size']}]")
            own.append({
                "id": m["id"], "repo": repo, "type": m["type"], "prio": m["prio"],
                "size": m["size"], "hours": SIZES[m["size"]], "title": m["title"],
                "done": m["done"], **shared,
            })
        if not own:
            raise ValueError(f"{path.name}: no steps")
        weeks = _weeks(path, rows, [step["id"] for step in own])
        for step in own:
            step["start"] = weeks[step["id"]]
            step["target"] = _sunday(weeks[step["id"]])
        _group(path, own_tasks, own)
        module["start"] = min(step["start"] for step in own)
        module["target"] = max(step["target"] for step in own)
        module["hours"] = sum(step["hours"] for step in own)
        milestones.append(module)
        tasks.extend(own_tasks)
        steps.extend(own)
    return milestones, tasks, steps


def _plan_link(item: dict) -> str:
    return f"Plan: [docs/plan/{item['file']}]({PLAN_URL}{item['file']})\n\n"


def step_body(step: dict) -> str:
    return (
        f"**Done when:** {step['done']}\n\n"
        f"**Size:** {step['size']}\n\n"
        f"{_plan_link(step)}"
        f"<!-- plan-id: {step['id']} -->\n"
    )


def task_body(task: dict) -> str:
    return (
        f"**Done when:** {task['done']}\n\n"
        "The steps of this task, in every repository, are its sub-issues. The task is closed "
        "by hand, when every step is closed and the line above holds.\n\n"
        f"{_plan_link(task)}"
        f"<!-- plan-task: {task['id']} -->\n"
    )


def item_labels(item: dict) -> list[str]:
    """The managed labels of a task or of a step."""
    return [
        f"type:{item['type']}",
        f"area:{AREAS[item['milestone']]}",
        f"prio:{item['prio']}",
        f"phase:{item['phase']}",
    ]


def epic_title(module: dict) -> str:
    return f"{module['id']} {module['name']}"


def epic_body(module: dict) -> str:
    return (
        f"**Goal:** {module['goal']}\n\n"
        f"**Depends on:** {', '.join(module['deps']) or 'nothing'}\n\n"
        "The tasks of this module are the sub-issues of this epic, and every task has its "
        "steps as sub-issues, in the repository that does the work.\n\n"
        f"{_plan_link(module)}"
        f"<!-- plan-epic: {module['id']} -->\n"
    )


def epic_labels(module: dict) -> list[str]:
    return [f"area:{AREAS[module['id']]}", f"phase:{module['phase']}"]


def specs(milestones: list[dict], tasks: list[dict], steps: list[dict]) -> dict[str, list[dict]]:
    """What the issue of every epic, task and step must look like, per level."""
    return {
        "epic": [{"id": m["id"], "milestone": m["id"], "repo": HOME, "title": epic_title(m),
                  "body": epic_body(m), "labels": epic_labels(m), "type": EPIC_TYPE}
                 for m in milestones],
        "task": [{"id": t["id"], "milestone": t["milestone"], "repo": t["repo"],
                  "title": f"{t['id']} {t['title']}", "body": task_body(t),
                  "labels": item_labels(t), "type": TASK_TYPE} for t in tasks],
        "step": [{"id": s["id"], "milestone": s["milestone"], "repo": s["repo"],
                  "title": f"{s['id']} {s['title']}", "body": step_body(s),
                  "labels": item_labels(s), "type": STEP_TYPE} for s in steps],
    }


def families(tasks: list[dict], steps: list[dict]) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """(level, plan ID) of every parent -> its children, in the order of the plan."""
    tree: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for task in tasks:
        tree.setdefault(("epic", task["milestone"]), []).append(("task", task["id"]))
    for task in tasks:
        tree[("task", task["id"])] = [("step", step_id) for step_id in task["steps"]]
    return tree


def merged_labels(current: list[str], wanted: list[str]) -> list[str]:
    """Wanted managed labels plus any label someone added by hand."""
    manual = [name for name in current if not name.startswith(MANAGED_PREFIXES)]
    return manual + [name for name in wanted if name not in manual]


def repos_in_use(steps: list[dict]) -> list[str]:
    """Repositories that have at least one step, in the order of REPOS."""
    used = {step["repo"] for step in steps} | {HOME}
    return [repo for repo in REPOS if repo in used]


def milestones_of(repo: str, milestones: list[dict], steps: list[dict]) -> list[dict]:
    """The milestones a repository needs: all at home, where the epics and tasks live."""
    if repo == HOME:
        return list(milestones)
    used = {step["milestone"] for step in steps if step["repo"] == repo}
    return [m for m in milestones if m["id"] in used]


def wanted_labels(repo: str, milestones: list[dict], steps: list[dict]) -> dict[str, tuple[str, str]]:
    """Every label the repository must have: name -> (color, description)."""
    want = {f"type:{name}": spec for name, spec in TYPES.items()}
    for m in milestones_of(repo, milestones, steps):
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
        {"name": "Estimate", "type": "NUMBER", "options": []},
        {"name": "Start", "type": "DATE", "options": []},
        {"name": "Target", "type": "DATE", "options": []},
    ]


def board_values(item: dict, kind: str) -> dict[str, str | int]:
    """Field values of the card of a module (its epic), a task or a step.

    Only a step carries hours, so a sum over any set of cards counts each hour once.
    """
    values: dict[str, str | int] = {
        "Phase": f"Phase {item['phase']}",
        "Track": f"{item['track']} {TRACKS[item['track']][0]}",
        "Start": item["start"],
        "Target": item["target"],
    }
    if kind != "epic":
        values["Priority"] = item["prio"].upper()
    if kind == "step":
        values["Estimate"] = item["hours"]
    return values


def board_guide(text: str) -> str:
    """The part of docs/BOARD.md that is published as the README of the board."""
    return text.split(GUIDE_END, 1)[0].strip() + "\n"


def hours_text(hours: float) -> str:
    """Hours as they are printed: 3 for 3.0, 1.5 for 1.5."""
    return f"{hours:g}"


def task_table(milestones: list[dict], tasks: list[dict], steps: list[dict]) -> str:
    """Every module and its tasks, with their steps, hours and dates."""
    rows = ["| Task | Steps | Hours | Start | Target |", "|---|---|---|---|---|"]
    for module in sorted(milestones, key=lambda m: (m["track"], m["id"])):
        count = sum(1 for step in steps if step["milestone"] == module["id"])
        rows.append(f"| **{module['id']} {module['name']}** | {count} "
                    f"| {hours_text(module['hours'])} | {module['start']} | {module['target']} |")
        for task in tasks:
            if task["milestone"] == module["id"]:
                rows.append(f"| {task['id']} {task['title']} | {len(task['steps'])} "
                            f"| {hours_text(task['hours'])} | {task['start']} | {task['target']} |")
    return "\n".join(rows)


def load_table(steps: list[dict]) -> str:
    """The steps and the hours planned for every week, split by module."""
    weeks: dict[str, dict[str, list[float]]] = {}
    for step in steps:
        weeks.setdefault(step["start"], {}).setdefault(step["milestone"], []).append(step["hours"])
    order = list(AREAS)
    rows = ["| Week of | Steps | Hours | By module |", "|---|---|---|---|"]
    for monday in sorted(weeks):
        modules = weeks[monday]
        split = ", ".join(f"{ms} {hours_text(sum(modules[ms]))}"
                          for ms in sorted(modules, key=order.index))
        rows.append(f"| {monday} | {sum(len(hours) for hours in modules.values())} "
                    f"| {hours_text(sum(sum(hours) for hours in modules.values()))} | {split} |")
    rows.append(f"| **Total** | {len(steps)} "
                f"| {hours_text(sum(step['hours'] for step in steps))} | |")
    return "\n".join(rows)


def fill(text: str, blocks: dict[str, str]) -> str:
    """Replace what stands between the start and end comments of each named block."""
    for name, body in blocks.items():
        block = re.compile(rf"<!-- {name}:start -->\n.*?<!-- {name}:end -->", re.S)
        if not block.search(text):
            raise ValueError(f"no '{name}' block in the document")
        text = block.sub(lambda _m, name=name, body=body:
                         f"<!-- {name}:start -->\n{body}\n<!-- {name}:end -->", text, count=1)
    return text


def plan_doc(text: str, milestones: list[dict], tasks: list[dict], steps: list[dict]) -> str:
    """docs/PLAN.md with its generated tables brought up to date."""
    return fill(text, {"tasks": task_table(milestones, tasks, steps), "load": load_table(steps)})


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


def missing_types() -> list[str]:
    """The issue types the levels need that the account does not have."""
    out = gh(["api", "graphql", "--input", "-"],
             {"query": TYPES_QUERY, "variables": {"owner": OWNER, "name": HOME}}, repeatable=True)
    nodes = json.loads(out)["data"]["repository"]["issueTypes"]["nodes"]
    have = {node["name"] for node in nodes if node["isEnabled"]}
    return [name for name in (EPIC_TYPE, TASK_TYPE, STEP_TYPE) if name not in have]


def sync_labels(milestones: list[dict], steps: list[dict], apply: bool, pace: float) -> None:
    for repo in repos_in_use(steps):
        have = {label["name"] for label in api_list(f"repos/{OWNER}/{repo}/labels?per_page=100")}
        for name, (color, description) in wanted_labels(repo, milestones, steps).items():
            if name in have:
                continue
            print(f"label + {repo} {name}", flush=True)
            if apply:
                gh(["api", "--method", "POST", f"repos/{OWNER}/{repo}/labels", "--input", "-"],
                   {"name": name, "color": color, "description": description}, pace)


def sync_milestones(milestones: list[dict], steps: list[dict], apply: bool,
                    pace: float) -> dict[tuple[str, str], int]:
    """Create each milestone in every repository that needs it, due on its last day.

    Milestones are matched by their ID prefix, so a renamed one is updated in place.
    """
    numbers: dict[tuple[str, str], int] = {}
    for repo in repos_in_use(steps):
        base = f"repos/{OWNER}/{repo}/milestones"
        have = {}
        for cur in api_list(f"{base}?state=all&per_page=100"):
            have[cur["title"].split(" - ", 1)[0]] = cur
        for m in milestones_of(repo, milestones, steps):
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


def find_existing() -> dict[str, dict[str, tuple[str, dict]]]:
    """Level -> plan ID -> (repository, issue), for every issue that carries a marker."""
    found: dict[str, dict[str, tuple[str, dict]]] = {kind: {} for kind in MARKERS}
    for repo in REPOS:
        for item in api_list(f"repos/{OWNER}/{repo}/issues?state=all&per_page=100"):
            if "pull_request" in item:
                continue
            body = item.get("body") or ""
            for kind, marker in MARKERS.items():
                mark = marker.search(body)
                if not mark:
                    continue
                if mark["id"] in found[kind]:
                    print(f"warning: {kind} {mark['id']} is on more than one issue", flush=True)
                found[kind].setdefault(mark["id"], (repo, item))
                break
    return found


def transfer(number: int, source: str, target: str, pace: float) -> dict:
    """Move an issue to another repository and return it as it is there."""
    out = gh(["issue", "transfer", str(number), f"{OWNER}/{target}",
              "--repo", f"{OWNER}/{source}"], pace=pace)
    moved = ISSUE_URL.search(out)
    if not moved or moved["repo"] != target:
        raise RuntimeError(f"transfer of {source}#{number} gave no issue URL: {out.strip()}")
    return json.loads(gh(["api", f"repos/{OWNER}/{target}/issues/{moved['number']}"]))


def sync_issues(kind: str, wanted_issues: list[dict], numbers: dict[tuple[str, str], int],
                existing: dict[str, tuple[str, dict]], only: set[str] | None, apply: bool,
                pace: float) -> dict[str, dict]:
    """One issue per epic, task or step, in its repository; returns plan ID -> issue."""
    plan_ids = {spec["id"] for spec in wanted_issues}
    for orphan in sorted(set(existing) - plan_ids):
        repo, item = existing[orphan]
        print(f"warning: {repo}#{item['number']} ({orphan}) is no longer in the plan", flush=True)

    records: dict[str, dict] = {}
    created = moved = updated = unchanged = 0
    for spec in wanted_issues:
        if only and spec["milestone"] not in only:
            continue
        repo = spec["repo"]
        base = f"repos/{OWNER}/{repo}/issues"
        cur_repo, cur = existing.get(spec["id"], (repo, None))
        if cur is not None and cur_repo != repo:
            moved += 1
            print(f"{kind} > {cur_repo}#{cur['number']} to {repo}: {spec['title']}", flush=True)
            if not apply:
                continue
            cur = transfer(cur["number"], cur_repo, repo, pace)
        want = wanted(cur, spec["title"], spec["body"], spec["labels"], spec["type"],
                      numbers.get((repo, spec["milestone"])))
        if cur is None:
            created += 1
            print(f"{kind} + {repo} {want['title']}", flush=True)
            if apply:
                out = gh(["api", "--method", "POST", base, "--input", "-"], want, pace)
                records[spec["id"]] = json.loads(out)
            continue
        records[spec["id"]] = cur
        if _differs(cur, want):
            updated += 1
            print(f"{kind} ~ {repo}#{cur['number']} {want['title']}", flush=True)
            if apply:
                gh(["api", "--method", "PATCH", f"{base}/{cur['number']}", "--input", "-"],
                   want, pace, repeatable=True)
        else:
            unchanged += 1
    print(f"{kind}s: {created} to create, {moved} to move, {updated} to update, "
          f"{unchanged} unchanged", flush=True)
    return records


def sync_parents(tasks: list[dict], steps: list[dict], records: dict[str, dict[str, dict]],
                 only: set[str] | None, apply: bool, pace: float) -> None:
    """Make every task a sub-issue of its epic and every step a sub-issue of its task."""
    linked = 0
    for (kind, parent_id), children in families(tasks, steps).items():
        if only and parent_id.split("-")[0] not in only:
            continue
        parent = records[kind].get(parent_id)
        have: set[int] = set()
        path = ""
        if parent is not None:
            where = ISSUE_URL.search(parent["html_url"])
            path = f"repos/{OWNER}/{where['repo']}/issues/{where['number']}/sub_issues"
            have = {sub["id"] for sub in api_list(f"{path}?per_page=100")}
        for child_kind, child_id in children:
            child = records[child_kind].get(child_id)
            if child is not None and child["id"] in have:
                continue
            linked += 1
            print(f"parent + {parent_id} gets {child_id}", flush=True)
            if apply and parent is not None and child is not None:
                gh(["api", "--method", "POST", path, "--input", "-"],
                   {"sub_issue_id": child["id"], "replace_parent": True}, pace)
    print(f"parents: {linked} to link", flush=True)


def board_cards(milestones: list[dict], tasks: list[dict], steps: list[dict],
                records: dict[str, dict[str, dict]]) -> dict[str, dict[str, str | int]]:
    """Issue URL -> the field values its card must carry."""
    cards: dict[str, dict[str, str | int]] = {}
    for kind, items in (("epic", milestones), ("task", tasks), ("step", steps)):
        for item in items:
            record = records[kind].get(item["id"])
            if record is not None:
                cards[record["html_url"]] = board_values(item, kind)
    return cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    parser.add_argument("--only", help="comma-separated milestone IDs, for example P0,M01")
    parser.add_argument("--project", type=int, help="number of the user project to fill")
    parser.add_argument("--views", action="store_true", help="also keep the saved views of the board")
    parser.add_argument("--guide", action="store_true", help="also publish docs/BOARD.md on the board")
    parser.add_argument("--pace", type=float, default=3.0, help="seconds to wait after each write")
    parser.add_argument("--check", action="store_true",
                        help="only validate the plan and the tables of docs/PLAN.md")
    parser.add_argument("--write", action="store_true",
                        help="only refresh the tables of docs/PLAN.md")
    args = parser.parse_args(argv)

    milestones, tasks, steps = parse_plan(PLAN_DIR)
    per_repo = ", ".join(
        f"{repo} {sum(1 for step in steps if step['repo'] == repo)}"
        for repo in repos_in_use(steps)
    )
    print(f"plan: {len(milestones)} milestones, {len(tasks)} tasks, {len(steps)} steps "
          f"({per_repo}), {hours_text(sum(step['hours'] for step in steps))} hours", flush=True)
    if args.check or args.write:
        raw = PLAN_DOC.read_bytes().decode("utf-8")
        text = raw.replace("\r\n", "\n")
        fresh = plan_doc(text, milestones, tasks, steps)
        if fresh == text:
            return 0
        if args.write:
            PLAN_DOC.write_bytes((fresh.replace("\n", "\r\n") if "\r\n" in raw else fresh)
                                 .encode("utf-8"))
            print("docs/PLAN.md: tables refreshed")
            return 0
        print("docs/PLAN.md is behind the plan files: run python scripts/plan_sync.py --write",
              file=sys.stderr)
        return 1
    only = set(args.only.split(",")) if args.only else None
    if only and only - set(AREAS):
        parser.error(f"unknown milestone IDs: {', '.join(sorted(only - set(AREAS)))}")
    if (args.views or args.guide) and not args.project:
        parser.error("--views and --guide need --project")
    absent = missing_types()
    if absent:
        note = f"issue type missing on the account: {', '.join(absent)} (add at {ISSUE_TYPES_URL})"
        if args.apply:
            print(note, file=sys.stderr)
            return 1
        print(f"warning: {note}", flush=True)

    sync_labels(milestones, steps, args.apply, args.pace)
    numbers = sync_milestones(milestones, steps, args.apply, args.pace)
    existing = find_existing()
    records = {
        kind: sync_issues(kind, wanted_issues, numbers, existing[kind], only, args.apply, args.pace)
        for kind, wanted_issues in specs(milestones, tasks, steps).items()
    }
    sync_parents(tasks, steps, records, only, args.apply, args.pace)
    if args.project:
        import plan_board

        board = plan_board.Board(gh, OWNER, args.project, args.apply, args.pace)
        cards = board_cards(milestones, tasks, steps, records)
        board.sync_items(list(cards))
        board.sync_fields(board_fields())
        board.sync_values(cards)
        if args.views:
            board.sync_views()
        if args.guide:
            board.sync_guide(board_guide(GUIDE.read_text(encoding="utf-8")))
    if not args.apply:
        print("dry run: nothing changed; pass --apply to make these changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
