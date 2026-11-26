#!/usr/bin/env python3
"""Spread the steps of the plan over the weeks, at a number of planned hours per week.

The Schedule table of each plan file gives every step its week. This script fills those
tables. It takes the steps in the order the plan has them now (week by week, inside a
week by module, task and position in the task) and puts them into consecutive weeks,
each filled up to the capacity. A step that does not fit in what is left of a week starts
the next one. The pass is repeated until nothing moves, so a second run with the same
numbers changes nothing.

    python scripts/plan_schedule.py                       # report at CAPACITY
    python scripts/plan_schedule.py --write               # rewrite the Schedule tables
    python scripts/plan_schedule.py --capacity 20 --since 2026-12-07 --write

With --since, the steps of earlier weeks keep their dates and the rest is spread again
from that Monday: this is how the plan is re-dated when a week went differently. After
--write, refresh the tables of docs/PLAN.md with plan_sync.py --write.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

import plan_sync

# Planned hours of work per week. The tests fail when a week of the plan holds more.
CAPACITY = 15
SCHEDULE = re.compile(
    r"(\| Week of \| Steps \|\n\|---\|---\|\n)(?:\| [0-9]{4}-[0-9]{2}-[0-9]{2} \| .+ \|\n)+"
)


def in_order(tasks: list[dict], steps: list[dict], weeks: dict[str, str]) -> list[dict]:
    """The steps by week, then module, then task, then position in the task."""
    modules = list(plan_sync.AREAS)
    place = {step_id: (n, k) for n, task in enumerate(tasks)
             for k, step_id in enumerate(task["steps"])}
    return sorted(steps, key=lambda step: (weeks[step["id"]], modules.index(step["milestone"]),
                                           place[step["id"]]))


def spread(sequence: list[dict], capacity: float, first: str) -> dict[str, str]:
    """Plan ID -> the Monday of its week, filling each week up to the capacity."""
    week = datetime.date.fromisoformat(first)
    used = 0.0
    weeks: dict[str, str] = {}
    for step in sequence:
        if used and used + step["hours"] > capacity + 1e-9:
            week += datetime.timedelta(days=7)
            used = 0.0
        weeks[step["id"]] = week.isoformat()
        used += step["hours"]
    return weeks


def settle(tasks: list[dict], steps: list[dict], capacity: float, since: str) -> dict[str, str]:
    """The week of every step once the steps from `since` on are packed and nothing moves."""
    weeks = {step["id"]: step["start"] for step in steps}
    for _ in range(100):
        moving = [step for step in in_order(tasks, steps, weeks) if weeks[step["id"]] >= since]
        fresh = {**weeks, **spread(moving, capacity, since)}
        if fresh == weeks:
            return weeks
        weeks = fresh
    raise RuntimeError("the schedule does not settle")


def load(steps: list[dict], weeks: dict[str, str]) -> dict[str, float]:
    """Monday -> the planned hours of that week."""
    hours: dict[str, float] = {}
    for step in steps:
        hours[weeks[step["id"]]] = hours.get(weeks[step["id"]], 0) + step["hours"]
    return dict(sorted(hours.items()))


def rewrite(text: str, rows: dict[str, list[str]]) -> str:
    """A plan file with the rows of its Schedule table replaced."""
    if len(SCHEDULE.findall(text)) != 1:
        raise ValueError("expected one Schedule table")
    body = "".join(f"| {week} | {', '.join(sorted(rows[week]))} |\n" for week in sorted(rows))
    return SCHEDULE.sub(lambda table: table.group(1) + body, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--capacity", type=float, default=CAPACITY,
                        help=f"planned hours per week (default {CAPACITY})")
    parser.add_argument("--since", help="Monday from which the steps are spread again "
                                        "(default: the first week of the plan)")
    parser.add_argument("--write", action="store_true", help="rewrite the Schedule tables")
    args = parser.parse_args(argv)

    _milestones, tasks, steps = plan_sync.parse_plan(plan_sync.PLAN_DIR)
    since = args.since or min(step["start"] for step in steps)
    if datetime.date.fromisoformat(since).weekday() != 0:
        parser.error(f"{since} is not a Monday")
    weeks = settle(tasks, steps, args.capacity, since)
    moved = sum(1 for step in steps if weeks[step["id"]] != step["start"])
    for week, hours in load(steps, weeks).items():
        count = sum(1 for step in steps if weeks[step["id"]] == week)
        print(f"{week}: {count} steps, {plan_sync.hours_text(hours)} hours")
    for phase in sorted({step["phase"] for step in steps}):
        last = max(weeks[step["id"]] for step in steps if step["phase"] == phase)
        print(f"phase {phase} ends {plan_sync._sunday(last)}")
    print(f"{moved} of {len(steps)} steps change week")
    if not args.write:
        return 0
    by_file: dict[str, dict[str, list[str]]] = {}
    for step in steps:
        by_file.setdefault(step["file"], {}).setdefault(weeks[step["id"]], []).append(step["id"])
    for name, rows in by_file.items():
        path: pathlib.Path = plan_sync.PLAN_DIR / name
        raw = path.read_bytes().decode("utf-8")
        text = rewrite(raw.replace("\r\n", "\n"), rows)
        path.write_bytes((text.replace("\n", "\r\n") if "\r\n" in raw else text).encode("utf-8"))
    print("schedule written; now run python scripts/plan_sync.py --write")
    return 0


if __name__ == "__main__":
    sys.exit(main())
