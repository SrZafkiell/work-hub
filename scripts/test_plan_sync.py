"""Tests for plan_sync: the parser, the issue body and label merging.

Run from the repository root:
    python -m unittest discover -s scripts -p "test_*.py"
"""
import pathlib
import tempfile
import unittest

import plan_sync

GOOD = """# P0 - Foundation

Track: all.

## Goal

A repository that is safe
to build in public.

## Issues

- P0-01 [chore] Repository files -- Done when: merged.
- P0-02 [security] Settings -- Done when: the settings are on.
"""


class PlanDir:
    """A temporary docs/plan directory holding the given files."""

    def __init__(self, files: dict[str, str]):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self._tmp.name)
        for name, text in files.items():
            (self.path / name).write_text(text, encoding="utf-8")

    def __enter__(self) -> pathlib.Path:
        return self.path

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()


class ParsePlanTest(unittest.TestCase):
    def test_parses_milestone_and_issues(self):
        with PlanDir({"P0-foundation.md": GOOD}) as path:
            milestones, issues = plan_sync.parse_plan(path)
        self.assertEqual(milestones[0]["title"], "P0 - Foundation")
        self.assertEqual(milestones[0]["goal"], "A repository that is safe to build in public.")
        self.assertEqual([i["id"] for i in issues], ["P0-01", "P0-02"])
        self.assertEqual(issues[1]["type"], "security")
        self.assertEqual(issues[1]["done"], "the settings are on.")

    def test_rejects_issue_from_another_milestone(self):
        text = GOOD + "- M01-01 [chore] Elsewhere -- Done when: never.\n"
        with PlanDir({"P0-foundation.md": text}) as path:
            with self.assertRaisesRegex(ValueError, "another milestone"):
                plan_sync.parse_plan(path)

    def test_rejects_unknown_type(self):
        text = GOOD + "- P0-03 [epic] Too big -- Done when: never.\n"
        with PlanDir({"P0-foundation.md": text}) as path:
            with self.assertRaisesRegex(ValueError, "unknown type"):
                plan_sync.parse_plan(path)

    def test_rejects_duplicate_id(self):
        text = GOOD + "- P0-02 [chore] Again -- Done when: never.\n"
        with PlanDir({"P0-foundation.md": text}) as path:
            with self.assertRaisesRegex(ValueError, "duplicate ID"):
                plan_sync.parse_plan(path)

    def test_rejects_issue_line_without_id(self):
        text = GOOD + "- [chore] No ID -- Done when: never.\n"
        with PlanDir({"P0-foundation.md": text}) as path:
            with self.assertRaisesRegex(ValueError, "malformed"):
                plan_sync.parse_plan(path)

    def test_rejects_heading_that_does_not_match_file(self):
        with PlanDir({"P1-runtime.md": GOOD}) as path:
            with self.assertRaisesRegex(ValueError, "does not match"):
                plan_sync.parse_plan(path)

    def test_real_plan_files_parse(self):
        milestones, issues = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        self.assertEqual({m["id"] for m in milestones}, set(plan_sync.AREAS))
        with_issues = {i["milestone"] for i in issues}
        self.assertEqual(with_issues, set(plan_sync.AREAS))


class BodyAndLabelsTest(unittest.TestCase):
    def test_body_carries_marker_and_plan_link(self):
        issue = {"id": "M08-06", "done": "it holds.", "file": "M08-meetings.md"}
        body = plan_sync.issue_body(issue)
        self.assertEqual(plan_sync.MARKER.search(body)["id"], "M08-06")
        self.assertIn("blob/main/docs/plan/M08-meetings.md", body)
        self.assertTrue(body.startswith("**Done when:** it holds."))

    def test_manual_labels_survive_and_managed_ones_are_replaced(self):
        merged = plan_sync.merged_labels(
            ["good first issue", "type:chore", "area:old"],
            ["type:security", "area:meetings"],
        )
        self.assertEqual(merged, ["good first issue", "type:security", "area:meetings"])


if __name__ == "__main__":
    unittest.main()
