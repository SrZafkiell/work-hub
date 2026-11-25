"""Tests for plan_sync and plan_board: the parser, what an issue carries, the board values.

Run from the repository root:
    python -m unittest discover -s scripts -p "test_*.py"
"""
import datetime
import pathlib
import tempfile
import unittest

import plan_board
import plan_sync

GOOD = """# P0 - Foundation

Track: A. Phase: 1. Size: M. Depends on: nothing. Unlocks: everything, and the first
build.

## Goal

A repository that is safe
to build in public.

## Issues

### work-hub

- P0-01 [chore p2] Repository files -- Done when: merged.
- P0-02 [security p1] Settings -- Done when: the settings are on.

### work-hub-backend

- P0-03 [chore p3] Demo data -- Done when: a seed command exists.

## Schedule

| Week of | Issues |
|---|---|
| 2026-11-30 | P0-01, P0-02 |
| 2026-12-07 | P0-03 |
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


def parse(text: str, name: str = "P0-foundation.md"):
    with PlanDir({name: text}) as path:
        return plan_sync.parse_plan(path)


class ParsePlanTest(unittest.TestCase):
    def assert_rejected(self, text: str, message: str, name: str = "P0-foundation.md"):
        with self.assertRaisesRegex(ValueError, message):
            parse(text, name)

    def test_parses_milestone_and_issues(self):
        milestones, issues = parse(GOOD)
        self.assertEqual(milestones[0]["title"], "P0 - Foundation")
        self.assertEqual(milestones[0]["goal"], "A repository that is safe to build in public.")
        self.assertEqual([i["id"] for i in issues], ["P0-01", "P0-02", "P0-03"])
        self.assertEqual(issues[1]["type"], "security")
        self.assertEqual(issues[1]["done"], "the settings are on.")

    def test_issue_takes_the_repository_of_its_heading(self):
        _, issues = parse(GOOD)
        self.assertEqual([i["repo"] for i in issues],
                         ["work-hub", "work-hub", "work-hub-backend"])

    def test_issue_carries_priority_phase_and_track(self):
        _, issues = parse(GOOD)
        self.assertEqual([i["prio"] for i in issues], ["p2", "p1", "p3"])
        self.assertEqual({(i["phase"], i["track"]) for i in issues}, {("1", "A")})

    def test_header_gives_track_phase_size_and_dependencies(self):
        text = GOOD.replace("Depends on: nothing.",
                            "Depends on: P1, and the worker of M06 (M06-04); the rest of M06.")
        milestones, _ = parse(text)
        module = milestones[0]
        self.assertEqual((module["track"], module["phase"], module["size"]), ("A", "1", "M"))
        self.assertEqual(module["deps"], ["P1", "M06"])

    def test_no_dependency_is_an_empty_list(self):
        milestones, _ = parse(GOOD)
        self.assertEqual(milestones[0]["deps"], [])

    def test_schedule_gives_each_issue_its_week(self):
        milestones, issues = parse(GOOD)
        self.assertEqual([(i["start"], i["target"]) for i in issues], [
            ("2026-11-30", "2026-12-06"), ("2026-11-30", "2026-12-06"),
            ("2026-12-07", "2026-12-13")])
        self.assertEqual((milestones[0]["start"], milestones[0]["target"]),
                         ("2026-11-30", "2026-12-13"))

    def test_rejects_header_without_phase(self):
        self.assert_rejected(GOOD.replace(" Phase: 1.", ""), "the header must read")

    def test_rejects_unknown_track(self):
        self.assert_rejected(GOOD.replace("Track: A.", "Track: Z."), "unknown track")

    def test_rejects_unknown_module_in_dependencies(self):
        self.assert_rejected(GOOD.replace("Depends on: nothing.", "Depends on: M77."),
                             "unknown module")

    def test_rejects_issue_without_priority(self):
        self.assert_rejected(GOOD.replace("[chore p2]", "[chore]"), "malformed")

    def test_rejects_unknown_priority(self):
        self.assert_rejected(GOOD.replace("[chore p2]", "[chore p9]"), "unknown priority")

    def test_rejects_week_that_is_not_a_monday(self):
        self.assert_rejected(GOOD.replace("| 2026-12-07 |", "| 2026-12-08 |"), "not a Monday")

    def test_rejects_weeks_out_of_order(self):
        text = GOOD.replace("| 2026-11-30 |", "| 2026-12-14 |")
        self.assert_rejected(text, "ascending order")

    def test_rejects_issue_without_a_week(self):
        self.assert_rejected(GOOD.replace("| 2026-12-07 | P0-03 |\n", ""), "no week")

    def test_rejects_issue_scheduled_twice(self):
        self.assert_rejected(GOOD.replace("| P0-03 |", "| P0-03, P0-01 |"), "scheduled twice")

    def test_rejects_week_for_an_issue_of_another_file(self):
        self.assert_rejected(GOOD.replace("| P0-03 |", "| P0-03, P0-09 |"), "not an issue")

    def test_rejects_file_without_issues(self):
        text = GOOD.split("## Issues")[0] + "## Issues\n"
        self.assert_rejected(text, "no issues")

    def test_rejects_issue_outside_a_repository_heading(self):
        self.assert_rejected(GOOD.replace("### work-hub\n\n", "", 1),
                             "not under a repository heading")

    def test_rejects_unknown_repository(self):
        self.assert_rejected(GOOD.replace("### work-hub-backend", "### somewhere-else"),
                             "unknown repository")

    def test_repository_heading_ends_with_the_section(self):
        text = GOOD + "\n## Measures\n\n- P0-04 [test p2] Late -- Done when: never.\n"
        self.assert_rejected(text, "not under a repository heading")

    def test_rejects_issue_from_another_milestone(self):
        text = GOOD.replace("- P0-03 [chore p3]", "- M01-01 [chore p3]")
        self.assert_rejected(text, "another milestone")

    def test_rejects_unknown_type(self):
        self.assert_rejected(GOOD.replace("[chore p2]", "[epic p2]"), "unknown type")

    def test_rejects_duplicate_id(self):
        text = GOOD.replace("- P0-03 [chore p3]", "- P0-02 [chore p3]")
        self.assert_rejected(text, "duplicate ID")

    def test_rejects_issue_line_without_id(self):
        text = GOOD.replace("- P0-03 [chore p3]", "- [chore p3]")
        self.assert_rejected(text, "malformed")

    def test_rejects_heading_that_does_not_match_file(self):
        self.assert_rejected(GOOD, "does not match", name="P1-runtime.md")

    def test_real_plan_files_parse(self):
        milestones, issues = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        self.assertEqual({m["id"] for m in milestones}, set(plan_sync.AREAS))
        self.assertEqual({i["milestone"] for i in issues}, set(plan_sync.AREAS))
        self.assertLessEqual({i["repo"] for i in issues}, set(plan_sync.REPOS))

    def test_real_plan_respects_its_dependencies(self):
        milestones, _ = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        start = {m["id"]: m["start"] for m in milestones}
        for module in milestones:
            for dep in module["deps"]:
                self.assertLessEqual(start[dep], module["start"],
                                     f"{module['id']} starts before {dep}")

    def test_real_plan_starts_every_week_on_a_monday(self):
        _, issues = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        for issue in issues:
            self.assertEqual(datetime.date.fromisoformat(issue["start"]).weekday(), 0, issue["id"])
            self.assertEqual(datetime.date.fromisoformat(issue["target"]).weekday(), 6, issue["id"])


class RepositoryViewsTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.issues = parse(GOOD)

    def test_repositories_in_use_follow_the_configured_order(self):
        self.assertEqual(plan_sync.repos_in_use(self.issues), ["work-hub", "work-hub-backend"])

    def test_home_is_in_use_even_without_issues(self):
        backend_only = [i for i in self.issues if i["repo"] == "work-hub-backend"]
        self.assertEqual(plan_sync.repos_in_use(backend_only), ["work-hub", "work-hub-backend"])

    def test_milestones_of_a_repository_are_only_those_with_issues_there(self):
        frontend = plan_sync.milestones_of("work-hub-frontend", self.milestones, self.issues)
        backend = plan_sync.milestones_of("work-hub-backend", self.milestones, self.issues)
        self.assertEqual(frontend, [])
        self.assertEqual([m["id"] for m in backend], ["P0"])

    def test_home_gets_every_milestone_for_its_epics(self):
        backend_only = [i for i in self.issues if i["repo"] == "work-hub-backend"]
        home = plan_sync.milestones_of("work-hub", self.milestones, backend_only)
        self.assertEqual([m["id"] for m in home], ["P0"])

    def test_every_repository_gets_priority_phase_and_flag_labels(self):
        labels = plan_sync.wanted_labels("work-hub-backend", self.milestones, self.issues)
        for name in ("type:security", "area:foundation", "prio:p1", "prio:p3", "phase:1",
                     "phase:2", "blocked", "needs:decision", "tech-debt", "breaking-change"):
            self.assertIn(name, labels)


class IssueContentTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.issues = parse(GOOD)

    def test_body_carries_marker_and_plan_link(self):
        issue = {"id": "M08-06", "done": "it holds.", "file": "M08-meetings.md"}
        body = plan_sync.issue_body(issue)
        self.assertEqual(plan_sync.MARKER.search(body)["id"], "M08-06")
        self.assertIn("work-hub/blob/main/docs/plan/M08-meetings.md", body)
        self.assertTrue(body.startswith("**Done when:** it holds."))

    def test_issue_labels_are_type_area_priority_and_phase(self):
        self.assertEqual(plan_sync.issue_labels(self.issues[1]),
                         ["type:security", "area:foundation", "prio:p1", "phase:1"])

    def test_manual_labels_survive_and_managed_ones_are_replaced(self):
        merged = plan_sync.merged_labels(
            ["good first issue", "type:chore", "area:old", "prio:p3", "blocked"],
            ["type:security", "area:meetings", "prio:p1", "phase:2"],
        )
        self.assertEqual(merged, ["good first issue", "blocked", "type:security", "area:meetings",
                                  "prio:p1", "phase:2"])

    def test_issue_url_gives_repository_and_number(self):
        found = plan_sync.ISSUE_URL.search(
            "https://github.com/SrZafkiell/work-hub-backend/issues/12\n")
        self.assertEqual((found["repo"], found["number"]), ("work-hub-backend", "12"))

    def test_epic_has_its_own_marker_and_no_issue_marker(self):
        module = self.milestones[0]
        body = plan_sync.epic_body(module)
        self.assertEqual(plan_sync.EPIC_MARKER.search(body)["id"], "P0")
        self.assertIsNone(plan_sync.MARKER.search(body))
        self.assertIn("**Depends on:** nothing", body)
        self.assertEqual(plan_sync.epic_title(module), "P0 Foundation")
        self.assertEqual(plan_sync.epic_labels(module), ["area:foundation", "phase:1"])

    def test_new_issue_is_typed_and_assigned_to_the_owner(self):
        want = plan_sync.wanted(None, "T", "B", ["type:chore"], plan_sync.TASK_TYPE, 7)
        self.assertEqual(want["assignees"], [plan_sync.ASSIGNEE])
        self.assertEqual((want["type"], want["milestone"]), ("Task", 7))

    def test_issue_someone_holds_keeps_its_assignee(self):
        cur = {"title": "T", "body": "B", "labels": [{"name": "type:chore"}], "milestone": None,
               "type": {"name": "Task"}, "assignees": [{"login": "someone"}]}
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.TASK_TYPE, None)
        self.assertNotIn("assignees", want)
        self.assertFalse(plan_sync._differs(cur, want))

    def test_unassigned_or_untyped_issue_is_updated(self):
        cur = {"title": "T", "body": "B", "labels": [{"name": "type:chore"}], "milestone": None,
               "type": None, "assignees": []}
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.TASK_TYPE, None)
        self.assertEqual(want["assignees"], [plan_sync.ASSIGNEE])
        self.assertTrue(plan_sync._differs(cur, want))
        cur["assignees"] = [{"login": "someone"}]
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.TASK_TYPE, None)
        self.assertTrue(plan_sync._differs(cur, want), "the missing type alone is a difference")


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.issues = parse(GOOD)

    def test_issue_card_carries_five_values(self):
        self.assertEqual(plan_sync.board_values(self.issues[2]), {
            "Priority": "P3", "Phase": "Phase 1", "Track": "A Platform",
            "Start": "2026-12-07", "Target": "2026-12-13"})

    def test_epic_card_spans_its_module_and_has_no_priority(self):
        self.assertEqual(plan_sync.board_values(self.milestones[0], epic=True), {
            "Phase": "Phase 1", "Track": "A Platform",
            "Start": "2026-11-30", "Target": "2026-12-13"})

    def test_field_options_cover_every_value_a_card_can_take(self):
        fields = {f["name"]: [name for name, _, _ in f["options"]] for f in plan_sync.board_fields()}
        self.assertEqual(fields["Priority"], ["P1", "P2", "P3"])
        self.assertIn("Phase 2", fields["Phase"])
        self.assertIn("C Schedule", fields["Track"])
        self.assertEqual((fields["Start"], fields["Target"]), ([], []))

    def test_cards_are_keyed_by_the_issue_and_epic_urls(self):
        records = {"P0-03": {"html_url": "https://github.com/o/r/issues/3"}}
        epics = {"P0": {"html_url": "https://github.com/o/h/issues/9"}}
        cards = plan_sync.board_cards(self.milestones, self.issues, records, epics)
        self.assertEqual(set(cards), {"https://github.com/o/r/issues/3",
                                      "https://github.com/o/h/issues/9"})
        self.assertNotIn("Priority", cards["https://github.com/o/h/issues/9"])

    def test_only_missing_or_different_values_are_written(self):
        cards = {"u1": {"Priority": "P1", "Start": "2026-11-30"}, "u2": {"Priority": "P2"},
                 "u3": {"Priority": "P3"}}
        items = {"u1": {"id": "I1", "values": {"Priority": "P1", "Start": "2026-11-23"}},
                 "u2": {"id": "I2", "values": {}}}
        self.assertEqual(plan_board.changed_values(cards, items),
                         [("I1", "Start", "2026-11-30"), ("I2", "Priority", "P2")])

    def test_value_mutation_uses_option_ids_and_dates(self):
        fields = {"Priority": {"id": "F1", "dataType": "SINGLE_SELECT",
                               "options": {"P1": {"id": "O1"}}},
                  "Start": {"id": "F2", "dataType": "DATE", "options": {}}}
        text = plan_board.value_mutation("P", fields, [("I1", "Priority", "P1"),
                                                      ("I1", "Start", "2026-11-30")])
        self.assertIn('fieldId: "F1", value: {singleSelectOptionId: "O1"}', text)
        self.assertIn('fieldId: "F2", value: {date: "2026-11-30"}', text)
        self.assertEqual(text.count("updateProjectV2ItemFieldValue"), 2)

    def test_view_definitions_are_unique_and_boards_have_columns(self):
        names = [view["name"] for view in plan_board.VIEWS]
        self.assertEqual(len(names), len(set(names)))
        for view in plan_board.VIEWS:
            if view["layout"] == "BOARD_LAYOUT":
                self.assertEqual(view["columns"], "Status", view["name"])
            if view["layout"] == "ROADMAP_LAYOUT":
                self.assertNotIn("fields", view, "a roadmap takes no field list")

    def test_view_gaps_name_what_the_browser_still_has_to_set(self):
        spec = plan_board.VIEWS[0]
        view = {"layout": "ROADMAP_LAYOUT", "filter": "type:Epic",
                "groupByFields": {"nodes": []}, "verticalGroupByFields": {"nodes": []},
                "sortByFields": {"nodes": []}}
        gaps = plan_board.view_gaps(spec, view)
        self.assertEqual(len(gaps), 2)
        self.assertIn("group none instead of ['Track']", gaps[0])
        view["groupByFields"]["nodes"] = [{"name": "Track"}]
        view["sortByFields"]["nodes"] = [{"direction": "ASC", "field": {"name": "Start"}}]
        self.assertEqual(plan_board.view_gaps(spec, view), [])
        self.assertEqual(plan_board.view_gaps(spec, None), ["missing"])

    def test_guide_lists_every_view_with_its_filter(self):
        text = plan_sync.GUIDE.read_text(encoding="utf-8")
        published = plan_sync.board_guide(text)
        self.assertNotIn("Keeping the board", published)
        settings = text.split(plan_sync.GUIDE_END, 1)[1].splitlines()
        for view in plan_board.VIEWS:
            self.assertIn(f"| {view['name']} |", published)
            row = next(line for line in settings if line.startswith(f"| {view['name']} | "))
            self.assertIn(f"| `{view['filter']}` |" if view["filter"] else "| none |", row)
            self.assertIn(f"| {view.get('group', '-')}", row)


if __name__ == "__main__":
    unittest.main()
