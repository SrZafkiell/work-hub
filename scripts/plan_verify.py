#!/usr/bin/env python3
"""Read the board back from GitHub and compare every card with the plan files.

plan_sync.py writes the plan to GitHub. This script reads it back: every card of the
board with its repository, issue type, assignees, labels, milestone, title, body, parent,
sub-issues and field values, compared with what the plan files say. It changes nothing.

    python scripts/plan_verify.py <project number>

It prints a summary, then every difference, and ends with "problems: 0" and exit code 0
when the board equals the plan. Progress is not a difference: a card may be closed, may
have any Status, may be held by someone else and may carry labels added by hand. A card
without a plan marker (a bug filed by hand, a pull request) is listed, not counted.
"""
from __future__ import annotations

import collections
import sys

import plan_board
import plan_schedule
import plan_sync

CARDS = """
query($project: ID!, $after: String) {
  node(id: $project) { ... on ProjectV2 { items(first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      content { ... on Issue {
        number url title state body
        repository { name }
        issueType { name }
        assignees(first: 5) { nodes { login } }
        labels(first: 30) { nodes { name } }
        milestone { title dueOn }
        parent { number repository { name } }
        subIssuesSummary { total completed }
      } ... on PullRequest { url } }
      fieldValues(first: 30) { nodes {
        ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
        ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
        ... on ProjectV2ItemFieldNumberValue { number field { ... on ProjectV2FieldCommon { name } } }
      } }
    }
  } } }
}
"""
# Which level a card hangs from, and how to name its parent in the plan.
PARENTS = {"task": ("epic", "milestone"), "step": ("task", "task")}


def fetch_cards(board: plan_board.Board, project_id: str) -> list[dict]:
    """Every card of the board, as the API returns it."""
    cards: list[dict] = []
    after = None
    while True:
        page = board.graphql(CARDS, {"project": project_id, "after": after})["node"]["items"]
        cards.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return cards
        after = page["pageInfo"]["endCursor"]


def index_cards(cards: list[dict]) -> tuple[dict[str, dict[str, dict]], list[str], list[str]]:
    """Level -> plan ID -> issue with its board values; the problems; the cards outside the plan."""
    found: dict[str, dict[str, dict]] = {kind: {} for kind in plan_sync.MARKERS}
    problems: list[str] = []
    outside: list[str] = []
    for card in cards:
        issue = dict(card.get("content") or {})
        if "body" not in issue:
            outside.append(issue.get("url") or "a draft item")
            continue
        issue["values"] = {value["field"]["name"]: plan_board.stored_value(value)
                           for value in card["fieldValues"]["nodes"] if value}
        for kind, marker in plan_sync.MARKERS.items():
            mark = marker.search(issue["body"] or "")
            if not mark:
                continue
            if mark["id"] in found[kind]:
                problems.append(f"{kind} {mark['id']}: on two cards")
            found[kind][mark["id"]] = issue
            break
        else:
            outside.append(issue["url"])
    return found, problems, outside


def _place(issue: dict) -> tuple[str, int]:
    return issue["repository"]["name"], issue["number"]


def compare(milestones: list[dict], tasks: list[dict], steps: list[dict],
            found: dict[str, dict[str, dict]]) -> list[str]:
    """Every difference between the cards and the plan, one line each."""
    problems: list[str] = []
    modules = {module["id"]: module for module in milestones}
    items = {"epic": modules, "task": {task["id"]: task for task in tasks},
             "step": {step["id"]: step for step in steps}}
    children = {
        "epic": {m["id"]: sum(1 for task in tasks if task["milestone"] == m["id"])
                 for m in milestones},
        "task": {task["id"]: len(task["steps"]) for task in tasks},
        "step": {step["id"]: 0 for step in steps},
    }
    fields = [field["name"] for field in plan_sync.board_fields()]
    for kind, specs in plan_sync.specs(milestones, tasks, steps).items():
        for orphan in sorted(set(found[kind]) - {spec["id"] for spec in specs}):
            problems.append(f"{kind} {orphan}: on the board but no longer in the plan")
        for spec in specs:
            issue = found[kind].get(spec["id"])
            if issue is None:
                problems.append(f"{kind} {spec['id']}: not on the board")
                continue
            item = items[kind][spec["id"]]
            module = modules[spec["milestone"]]
            name = f"{kind} {spec['id']} ({issue['repository']['name']}#{issue['number']})"

            def check(what: str, got: object, want: object, name: str = name) -> None:
                if got != want:
                    problems.append(f"{name} {what}: {got!r} instead of {want!r}")

            check("repository", issue["repository"]["name"], spec["repo"])
            check("type", (issue.get("issueType") or {}).get("name"), spec["type"])
            check("title", issue["title"], spec["title"])
            if (issue["body"] or "").replace("\r\n", "\n") != spec["body"]:
                problems.append(f"{name} body: not the text of the plan")
            managed = sorted(label["name"] for label in issue["labels"]["nodes"]
                             if label["name"].startswith(plan_sync.MANAGED_PREFIXES))
            check("labels", managed, sorted(spec["labels"]))
            if not issue["assignees"]["nodes"]:
                problems.append(f"{name}: nobody is assigned")
            milestone = issue.get("milestone") or {}
            check("milestone", milestone.get("title"), module["title"])
            check("milestone due date", (milestone.get("dueOn") or "")[:10], module["target"])
            values = {field: issue["values"][field] for field in fields if field in issue["values"]}
            check("board values", values, plan_sync.board_values(item, kind))
            parent = issue.get("parent")
            got_parent = (parent["repository"]["name"], parent["number"]) if parent else None
            if kind in PARENTS:
                parent_kind, key = PARENTS[kind]
                want_parent = found[parent_kind].get(item[key])
                if want_parent is not None:
                    check("parent", got_parent, _place(want_parent))
            else:
                check("parent", got_parent, None)
            check("sub-issues", issue["subIssuesSummary"]["total"], children[kind][spec["id"]])
    return problems


def board_load(found: dict[str, dict[str, dict]]) -> dict[str, float]:
    """Monday -> the hours of the step cards that start that week."""
    hours: dict[str, float] = {}
    for issue in found["step"].values():
        start = issue["values"].get("Start")
        if start:
            hours[start] = hours.get(start, 0) + (issue["values"].get("Estimate") or 0)
    return dict(sorted(hours.items()))


def _counts(values: list) -> str:
    counted = collections.Counter(str(value) for value in values)
    return ", ".join(f"{key} {count}" for key, count in sorted(counted.items())) or "none"


def summary(found: dict[str, dict[str, dict]], outside: list[str], project: dict) -> list[str]:
    """What is on the board, in a few lines."""
    steps = list(found["step"].values())
    everything = [issue for kind in found.values() for issue in kind.values()]
    load = board_load(found)
    views = sorted(project["views"].values(), key=lambda view: view["number"])
    return [
        f"cards: {len(everything) + len(outside)} (epics {len(found['epic'])}, "
        f"tasks {len(found['task'])}, steps {len(found['step'])}, "
        f"outside the plan {len(outside)})",
        f"state: {_counts([issue['state'] for issue in everything])}",
        f"status: {_counts([issue['values'].get('Status') for issue in everything])}",
        f"steps per repository: {_counts([issue['repository']['name'] for issue in steps])}",
        f"step priority: {_counts([issue['values'].get('Priority') for issue in steps])}",
        f"step phase: {_counts([issue['values'].get('Phase') for issue in steps])}",
        "hours per week: " + (", ".join(f"{week} {plan_sync.hours_text(hours)}"
                                        for week, hours in load.items()) or "none"),
        f"hours in all: {plan_sync.hours_text(sum(load.values()))}",
        f"views: {', '.join(view['name'] for view in views) or 'none'}",
        f"guide: {len(project['readme'])} characters",
    ]


def verify(project: dict, cards: list[dict], milestones: list[dict], tasks: list[dict],
           steps: list[dict], guide: str) -> tuple[list[str], list[str], list[str]]:
    """The summary lines, the cards outside the plan and the problems of a board."""
    found, problems, outside = index_cards(cards)
    for field in plan_sync.board_fields():
        if field["name"] not in project["fields"]:
            problems.append(f"field {field['name']}: not on the board")
    problems += compare(milestones, tasks, steps, found)
    plan_load = plan_schedule.load(steps, {step["id"]: step["start"] for step in steps})
    if board_load(found) != plan_load:
        problems.append("the hours per week on the board are not those of the plan")
    if project["readme"].replace("\r\n", "\n").strip() != guide.strip():
        problems.append("the guide on the board is not that of docs/BOARD.md")
    return summary(found, outside, project), outside, problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not args[0].isdigit():
        print("usage: python scripts/plan_verify.py <project number>", file=sys.stderr)
        return 2
    board = plan_board.Board(plan_sync.gh, plan_sync.OWNER, int(args[0]), apply=False, pace=0.0)
    project = board.project()
    milestones, tasks, steps = plan_sync.parse_plan(plan_sync.PLAN_DIR)
    guide = plan_sync.board_guide(plan_sync.GUIDE.read_text(encoding="utf-8"))
    lines, outside, problems = verify(project, fetch_cards(board, project["id"]),
                                      milestones, tasks, steps, guide)
    for line in lines:
        print(line)
    for url in outside:
        print(f"outside the plan: {url}")
    print(f"problems: {len(problems)}")
    for line in problems:
        print(f"  - {line}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
