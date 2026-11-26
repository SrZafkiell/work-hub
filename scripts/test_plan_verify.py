"""Tests for plan_verify: what counts as a difference between the board and the plan.

Run from the repository root:
    python -m unittest discover -s scripts -p "test_*.py"
"""
import unittest

import plan_sync
import plan_verify
from test_plan_sync import GOOD, parse

GUIDE = "# How to read this board\n"


def value_node(name: str, value: object) -> dict:
    """A field value as the API returns it: an option name, a date or a number."""
    key = {"Estimate": "number", "Start": "date", "Target": "date"}.get(name, "name")
    return {"field": {"name": name}, key: value}


def board_for(milestones: list[dict], tasks: list[dict], steps: list[dict]) -> list[dict]:
    """The cards of a board that equals the plan."""
    modules = {m["id"]: m for m in milestones}
    items = {"epic": modules, "task": {t["id"]: t for t in tasks},
             "step": {s["id"]: s for s in steps}}
    children = {"epic": lambda m: sum(1 for t in tasks if t["milestone"] == m["id"]),
                "task": lambda t: len(t["steps"]), "step": lambda s: 0}
    cards: list[dict] = []
    places: dict[tuple[str, str], tuple[str, int]] = {}
    for kind, specs in plan_sync.specs(milestones, tasks, steps).items():
        for spec in specs:
            item = items[kind][spec["id"]]
            number = len(cards) + 1
            places[(kind, spec["id"])] = (spec["repo"], number)
            parent = None
            if kind in plan_verify.PARENTS:
                parent_kind, key = plan_verify.PARENTS[kind]
                repo, parent_number = places[(parent_kind, item[key])]
                parent = {"number": parent_number, "repository": {"name": repo}}
            module = modules[spec["milestone"]]
            values = plan_sync.board_values(item, kind)
            cards.append({"id": f"I{number}", "content": {
                "number": number,
                "url": f"https://github.com/o/{spec['repo']}/issues/{number}",
                "title": spec["title"], "state": "OPEN", "body": spec["body"],
                "repository": {"name": spec["repo"]}, "issueType": {"name": spec["type"]},
                "assignees": {"nodes": [{"login": "owner"}]},
                "labels": {"nodes": [{"name": name} for name in spec["labels"]]},
                "milestone": {"title": module["title"], "dueOn": f"{module['target']}T12:00:00Z"},
                "parent": parent,
                "subIssuesSummary": {"total": children[kind](item), "completed": 0},
            }, "fieldValues": {"nodes": [value_node(name, value) for name, value in values.items()]
                               + [value_node("Status", "Todo")]}})
    return cards


def project_for(guide: str = GUIDE) -> dict:
    return {"id": "P", "readme": guide, "views": {"Roadmap": {"number": 1, "name": "Roadmap"}},
            "fields": {field["name"]: {} for field in plan_sync.board_fields()}}


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.plan = parse(GOOD)
        self.cards = board_for(*self.plan)

    def card(self, marker: str) -> dict:
        return next(card for card in self.cards if f"{marker} -->" in card["content"]["body"])

    def problems(self, project: dict | None = None) -> list[str]:
        _, _, problems = plan_verify.verify(project or project_for(), self.cards, *self.plan, GUIDE)
        return problems

    def set_value(self, marker: str, name: str, value: object) -> None:
        nodes = self.card(marker)["fieldValues"]["nodes"]
        nodes[:] = [node for node in nodes if node["field"]["name"] != name]
        nodes.append(value_node(name, value))

    def test_a_board_that_equals_the_plan_has_no_problems(self):
        self.assertEqual(self.problems(), [])

    def test_progress_is_not_a_difference(self):
        issue = self.card("plan-id: P0-01")["content"]
        issue["state"] = "CLOSED"
        issue["assignees"]["nodes"] = [{"login": "someone"}, {"login": "else"}]
        issue["labels"]["nodes"].append({"name": "blocked"})
        self.set_value("plan-id: P0-01", "Status", "Done")
        self.assertEqual(self.problems(), [])

    def test_a_step_that_is_not_on_the_board_is_reported(self):
        self.cards.remove(self.card("plan-id: P0-03"))
        problems = self.problems()
        self.assertIn("step P0-03: not on the board", problems)
        self.assertIn("the hours per week on the board are not those of the plan", problems)

    def test_a_card_that_left_the_plan_is_reported(self):
        self.card("plan-id: P0-03")["content"]["body"] = "<!-- plan-id: P0-09 -->\n"
        problems = self.problems()
        self.assertIn("step P0-09: on the board but no longer in the plan", problems)
        self.assertIn("step P0-03: not on the board", problems)

    def test_a_plan_id_on_two_cards_is_reported(self):
        self.cards.append(self.card("plan-id: P0-02"))
        self.assertIn("step P0-02: on two cards", self.problems())

    def test_a_card_outside_the_plan_is_listed_and_not_counted(self):
        self.cards.append({"id": "I99", "content": {
            "number": 99, "url": "https://github.com/o/work-hub-backend/issues/99", "body": "A bug.",
            "state": "OPEN", "repository": {"name": "work-hub-backend"}}, "fieldValues": {"nodes": []}})
        self.cards.append({"id": "I98", "content": {"url": "https://github.com/o/work-hub-backend/pull/98"},
                           "fieldValues": {"nodes": []}})
        lines, outside, problems = plan_verify.verify(project_for(), self.cards, *self.plan, GUIDE)
        self.assertEqual(problems, [])
        self.assertEqual(outside, ["https://github.com/o/work-hub-backend/issues/99",
                                   "https://github.com/o/work-hub-backend/pull/98"])
        self.assertIn("outside the plan 2", lines[0])

    def test_each_managed_field_of_an_issue_is_compared(self):
        issue = self.card("plan-id: P0-02")["content"]
        issue["title"] = "P0-02 Something else"
        issue["body"] = "Edited by hand.\n\n<!-- plan-id: P0-02 -->\n"
        issue["issueType"] = {"name": "Task"}
        issue["labels"]["nodes"] = [{"name": "type:security"}, {"name": "area:foundation"},
                                    {"name": "prio:p3"}, {"name": "phase:1"}]
        issue["assignees"]["nodes"] = []
        issue["milestone"]["dueOn"] = "2027-01-01T12:00:00Z"
        issue["parent"] = None
        text = "\n".join(self.problems())
        name = "step P0-02 (work-hub#5)"
        for what in ("title", "body", "type", "labels", "milestone due date", "parent"):
            self.assertIn(f"{name} {what}: ", text)
        self.assertIn(f"{name}: nobody is assigned", text)

    def test_board_values_are_compared(self):
        self.set_value("plan-id: P0-03", "Estimate", 6)
        self.set_value("plan-task: P0-A", "Estimate", 1)
        self.set_value("plan-epic: P0", "Start", "2026-11-23")
        text = "\n".join(self.problems())
        self.assertIn("step P0-03 (work-hub-backend#6) board values", text)
        self.assertIn("task P0-A (work-hub#2) board values", text)
        self.assertIn("epic P0 (work-hub#1) board values", text)

    def test_the_number_of_sub_issues_is_compared(self):
        self.card("plan-task: P0-A")["content"]["subIssuesSummary"]["total"] = 1
        self.assertEqual(self.problems(),
                         ["task P0-A (work-hub#2) sub-issues: 1 instead of 2"])

    def test_a_missing_field_and_another_guide_are_reported(self):
        project = project_for(guide="# Another text\n")
        del project["fields"]["Estimate"]
        self.assertEqual(self.problems(project), [
            "field Estimate: not on the board",
            "the guide on the board is not that of docs/BOARD.md"])

    def test_board_load_adds_the_estimates_of_each_week(self):
        found, _, _ = plan_verify.index_cards(self.cards)
        hours = plan_sync.SIZES
        self.assertEqual(plan_verify.board_load(found), {
            "2026-11-30": hours["S"] + hours["M"], "2026-12-07": hours["L"]})


if __name__ == "__main__":
    unittest.main()
