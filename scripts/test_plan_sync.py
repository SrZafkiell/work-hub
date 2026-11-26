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

## Tasks

- P0-A [chore] Repository rules -- Done when: a bad push is refused. -- Steps: P0-01, P0-02
- P0-B [test] Demo data -- Done when: fixtures come from the seed. -- Steps: P0-03

## Steps

### work-hub

- P0-01 [chore p2 S] Repository files -- Done when: merged.
- P0-02 [security p1 M] Settings -- Done when: the settings are on.

### work-hub-backend

- P0-03 [chore p3 L] Demo data set -- Done when: a seed command exists.

## Schedule

| Week of | Steps |
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

    def test_parses_milestone_tasks_and_steps(self):
        milestones, tasks, steps = parse(GOOD)
        self.assertEqual(milestones[0]["title"], "P0 - Foundation")
        self.assertEqual(milestones[0]["goal"], "A repository that is safe to build in public.")
        self.assertEqual([t["id"] for t in tasks], ["P0-A", "P0-B"])
        self.assertEqual([s["id"] for s in steps], ["P0-01", "P0-02", "P0-03"])
        self.assertEqual(steps[1]["type"], "security")
        self.assertEqual(steps[1]["done"], "the settings are on.")

    def test_step_takes_the_repository_of_its_heading(self):
        _, _, steps = parse(GOOD)
        self.assertEqual([s["repo"] for s in steps],
                         ["work-hub", "work-hub", "work-hub-backend"])

    def test_step_carries_priority_phase_and_track(self):
        _, _, steps = parse(GOOD)
        self.assertEqual([s["prio"] for s in steps], ["p2", "p1", "p3"])
        self.assertEqual({(s["phase"], s["track"]) for s in steps}, {("1", "A")})

    def test_step_carries_its_size_in_hours_and_its_task(self):
        _, _, steps = parse(GOOD)
        self.assertEqual([(s["size"], s["hours"]) for s in steps],
                         [("S", plan_sync.SIZES["S"]), ("M", plan_sync.SIZES["M"]),
                          ("L", plan_sync.SIZES["L"])])
        self.assertEqual([s["task"] for s in steps], ["P0-A", "P0-A", "P0-B"])

    def test_task_lives_at_home_and_names_its_steps(self):
        _, tasks, _ = parse(GOOD)
        self.assertEqual({t["repo"] for t in tasks}, {plan_sync.HOME})
        self.assertEqual(tasks[0]["steps"], ["P0-01", "P0-02"])
        self.assertEqual((tasks[1]["type"], tasks[1]["title"], tasks[1]["done"]),
                         ("test", "Demo data", "fixtures come from the seed."))

    def test_task_takes_priority_dates_and_hours_from_its_steps(self):
        _, tasks, _ = parse(GOOD)
        hours = plan_sync.SIZES
        self.assertEqual(
            [(t["prio"], t["start"], t["target"], t["hours"]) for t in tasks],
            [("p1", "2026-11-30", "2026-12-06", hours["S"] + hours["M"]),
             ("p3", "2026-12-07", "2026-12-13", hours["L"])])

    def test_header_gives_track_phase_size_and_dependencies(self):
        text = GOOD.replace("Depends on: nothing.",
                            "Depends on: P1, and the worker of M06 (M06-04); the rest of M06.")
        milestones, _, _ = parse(text)
        module = milestones[0]
        self.assertEqual((module["track"], module["phase"], module["size"]), ("A", "1", "M"))
        self.assertEqual(module["deps"], ["P1", "M06"])

    def test_no_dependency_is_an_empty_list(self):
        milestones, _, _ = parse(GOOD)
        self.assertEqual(milestones[0]["deps"], [])

    def test_schedule_gives_each_step_its_week(self):
        milestones, _, steps = parse(GOOD)
        self.assertEqual([(s["start"], s["target"]) for s in steps], [
            ("2026-11-30", "2026-12-06"), ("2026-11-30", "2026-12-06"),
            ("2026-12-07", "2026-12-13")])
        self.assertEqual((milestones[0]["start"], milestones[0]["target"]),
                         ("2026-11-30", "2026-12-13"))

    def test_module_adds_up_the_hours_of_its_steps(self):
        milestones, _, steps = parse(GOOD)
        self.assertEqual(milestones[0]["hours"], sum(s["hours"] for s in steps))

    def test_rejects_header_without_phase(self):
        self.assert_rejected(GOOD.replace(" Phase: 1.", ""), "the header must read")

    def test_rejects_unknown_track(self):
        self.assert_rejected(GOOD.replace("Track: A.", "Track: Z."), "unknown track")

    def test_rejects_unknown_module_in_dependencies(self):
        self.assert_rejected(GOOD.replace("Depends on: nothing.", "Depends on: M77."),
                             "unknown module")

    def test_rejects_step_without_priority_or_size(self):
        self.assert_rejected(GOOD.replace("[chore p2 S]", "[chore S]"), "malformed step")
        self.assert_rejected(GOOD.replace("[chore p2 S]", "[chore p2]"), "malformed step")

    def test_rejects_unknown_priority(self):
        self.assert_rejected(GOOD.replace("[chore p2 S]", "[chore p9 S]"), "unknown priority")

    def test_rejects_unknown_size(self):
        self.assert_rejected(GOOD.replace("[chore p2 S]", "[chore p2 XL]"), "unknown size")

    def test_rejects_week_that_is_not_a_monday(self):
        self.assert_rejected(GOOD.replace("| 2026-12-07 |", "| 2026-12-08 |"), "not a Monday")

    def test_rejects_weeks_out_of_order(self):
        text = GOOD.replace("| 2026-11-30 |", "| 2026-12-14 |")
        self.assert_rejected(text, "ascending order")

    def test_rejects_step_without_a_week(self):
        self.assert_rejected(GOOD.replace("| 2026-12-07 | P0-03 |\n", ""), "no week")

    def test_rejects_step_scheduled_twice(self):
        self.assert_rejected(GOOD.replace("| P0-03 |", "| P0-03, P0-01 |"), "scheduled twice")

    def test_rejects_week_for_a_step_of_another_file(self):
        self.assert_rejected(GOOD.replace("| P0-03 |", "| P0-03, P0-09 |"), "not a step")

    def test_rejects_file_without_steps(self):
        text = GOOD.split("## Steps")[0] + "## Steps\n"
        self.assert_rejected(text, "no steps")

    def test_rejects_step_outside_a_repository_heading(self):
        self.assert_rejected(GOOD.replace("### work-hub\n\n", "", 1),
                             "not under a repository heading")

    def test_rejects_unknown_repository(self):
        self.assert_rejected(GOOD.replace("### work-hub-backend", "### somewhere-else"),
                             "unknown repository")

    def test_repository_heading_ends_with_the_section(self):
        text = GOOD + "\n## Measures\n\n- P0-04 [test p2 S] Late -- Done when: never.\n"
        self.assert_rejected(text, "not under a repository heading")

    def test_rejects_step_from_another_milestone(self):
        text = GOOD.replace("- P0-03 [chore p3 L]", "- M01-01 [chore p3 L]")
        self.assert_rejected(text, "another milestone")

    def test_rejects_unknown_type(self):
        self.assert_rejected(GOOD.replace("[chore p2 S]", "[epic p2 S]"), "unknown type")
        self.assert_rejected(GOOD.replace("- P0-B [test]", "- P0-B [epic]"), "unknown type")

    def test_rejects_duplicate_id(self):
        text = GOOD.replace("- P0-03 [chore p3 L]", "- P0-02 [chore p3 L]")
        self.assert_rejected(text, "duplicate ID")
        self.assert_rejected(GOOD.replace("- P0-B [test]", "- P0-A [test]"), "duplicate ID")

    def test_rejects_step_line_without_id(self):
        text = GOOD.replace("- P0-03 [chore p3 L]", "- [chore p3 L]")
        self.assert_rejected(text, "malformed step")

    def test_rejects_task_without_its_steps(self):
        self.assert_rejected(GOOD.replace(" -- Steps: P0-03", ""), "malformed task")

    def test_rejects_task_with_a_priority_of_its_own(self):
        self.assert_rejected(GOOD.replace("- P0-B [test]", "- P0-B [test p1]"), "malformed task")

    def test_rejects_task_from_another_milestone(self):
        self.assert_rejected(GOOD.replace("- P0-B [test]", "- P1-B [test]"), "another milestone")

    def test_rejects_step_without_a_task(self):
        self.assert_rejected(GOOD.replace("-- Steps: P0-01, P0-02", "-- Steps: P0-01"),
                             "no task for P0-02")

    def test_rejects_step_in_two_tasks(self):
        self.assert_rejected(GOOD.replace("-- Steps: P0-03", "-- Steps: P0-03, P0-01"),
                             "P0-01 is in P0-A and in P0-B")

    def test_rejects_task_that_names_an_unknown_step(self):
        self.assert_rejected(GOOD.replace("-- Steps: P0-03", "-- Steps: P0-03, P0-09"),
                             "P0-B names P0-09")

    def test_rejects_heading_that_does_not_match_file(self):
        self.assert_rejected(GOOD, "does not match", name="P1-runtime.md")

    def test_real_plan_files_parse(self):
        milestones, tasks, steps = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        self.assertEqual({m["id"] for m in milestones}, set(plan_sync.AREAS))
        self.assertEqual({t["milestone"] for t in tasks}, set(plan_sync.AREAS))
        self.assertEqual({s["milestone"] for s in steps}, set(plan_sync.AREAS))
        self.assertLessEqual({s["repo"] for s in steps}, set(plan_sync.REPOS))

    def test_real_plan_gives_every_task_more_than_one_step(self):
        _, tasks, _ = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        for task in tasks:
            self.assertGreater(len(task["steps"]), 1, f"{task['id']} is a step, not a task")

    def test_real_plan_respects_its_dependencies(self):
        milestones, _, _ = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        start = {m["id"]: m["start"] for m in milestones}
        for module in milestones:
            for dep in module["deps"]:
                self.assertLessEqual(start[dep], module["start"],
                                     f"{module['id']} starts before {dep}")

    def test_real_plan_starts_every_week_on_a_monday(self):
        _, _, steps = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        for step in steps:
            self.assertEqual(datetime.date.fromisoformat(step["start"]).weekday(), 0, step["id"])
            self.assertEqual(datetime.date.fromisoformat(step["target"]).weekday(), 6, step["id"])


class RepositoryViewsTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.tasks, self.steps = parse(GOOD)

    def test_repositories_in_use_follow_the_configured_order(self):
        self.assertEqual(plan_sync.repos_in_use(self.steps), ["work-hub", "work-hub-backend"])

    def test_home_is_in_use_even_without_steps(self):
        backend_only = [s for s in self.steps if s["repo"] == "work-hub-backend"]
        self.assertEqual(plan_sync.repos_in_use(backend_only), ["work-hub", "work-hub-backend"])

    def test_milestones_of_a_repository_are_only_those_with_steps_there(self):
        frontend = plan_sync.milestones_of("work-hub-frontend", self.milestones, self.steps)
        backend = plan_sync.milestones_of("work-hub-backend", self.milestones, self.steps)
        self.assertEqual(frontend, [])
        self.assertEqual([m["id"] for m in backend], ["P0"])

    def test_home_gets_every_milestone_for_its_epics_and_tasks(self):
        backend_only = [s for s in self.steps if s["repo"] == "work-hub-backend"]
        home = plan_sync.milestones_of("work-hub", self.milestones, backend_only)
        self.assertEqual([m["id"] for m in home], ["P0"])

    def test_every_repository_gets_priority_phase_and_flag_labels(self):
        labels = plan_sync.wanted_labels("work-hub-backend", self.milestones, self.steps)
        for name in ("type:security", "area:foundation", "prio:p1", "prio:p3", "phase:1",
                     "phase:2", "blocked", "needs:decision", "tech-debt", "breaking-change"):
            self.assertIn(name, labels)


class IssueContentTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.tasks, self.steps = parse(GOOD)

    def markers_in(self, body: str) -> dict[str, str]:
        found = {kind: marker.search(body) for kind, marker in plan_sync.MARKERS.items()}
        return {kind: mark["id"] for kind, mark in found.items() if mark}

    def test_step_body_carries_marker_size_and_plan_link(self):
        step = {"id": "M08-06", "done": "it holds.", "size": "M", "file": "M08-meetings.md"}
        body = plan_sync.step_body(step)
        self.assertEqual(self.markers_in(body), {"step": "M08-06"})
        self.assertIn("work-hub/blob/main/docs/plan/M08-meetings.md", body)
        self.assertTrue(body.startswith("**Done when:** it holds."))
        self.assertIn("**Size:** M", body)

    def test_task_body_has_its_own_marker(self):
        body = plan_sync.task_body(self.tasks[0])
        self.assertEqual(self.markers_in(body), {"task": "P0-A"})
        self.assertTrue(body.startswith("**Done when:** a bad push is refused."))

    def test_labels_are_type_area_priority_and_phase(self):
        self.assertEqual(plan_sync.item_labels(self.steps[1]),
                         ["type:security", "area:foundation", "prio:p1", "phase:1"])
        self.assertEqual(plan_sync.item_labels(self.tasks[0]),
                         ["type:chore", "area:foundation", "prio:p1", "phase:1"])

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

    def test_epic_has_its_own_marker(self):
        module = self.milestones[0]
        body = plan_sync.epic_body(module)
        self.assertEqual(self.markers_in(body), {"epic": "P0"})
        self.assertIn("**Depends on:** nothing", body)
        self.assertEqual(plan_sync.epic_title(module), "P0 Foundation")
        self.assertEqual(plan_sync.epic_labels(module), ["area:foundation", "phase:1"])

    def test_each_level_gets_its_issue_type_and_repository(self):
        specs = plan_sync.specs(self.milestones, self.tasks, self.steps)
        self.assertEqual(list(specs), ["epic", "task", "step"])
        self.assertEqual([(s["type"], s["repo"], s["title"]) for s in specs["epic"]],
                         [("Epic", "work-hub", "P0 Foundation")])
        self.assertEqual([(s["type"], s["repo"], s["title"]) for s in specs["task"]],
                         [("Task", "work-hub", "P0-A Repository rules"),
                          ("Task", "work-hub", "P0-B Demo data")])
        self.assertEqual((specs["step"][2]["type"], specs["step"][2]["repo"],
                          specs["step"][2]["title"]),
                         ("Step", "work-hub-backend", "P0-03 Demo data set"))
        self.assertEqual({s["milestone"] for kind in specs.values() for s in kind}, {"P0"})

    def test_tasks_hang_from_the_epic_and_steps_from_their_task(self):
        self.assertEqual(plan_sync.families(self.tasks, self.steps), {
            ("epic", "P0"): [("task", "P0-A"), ("task", "P0-B")],
            ("task", "P0-A"): [("step", "P0-01"), ("step", "P0-02")],
            ("task", "P0-B"): [("step", "P0-03")],
        })

    def test_new_issue_is_typed_and_assigned_to_the_owner(self):
        want = plan_sync.wanted(None, "T", "B", ["type:chore"], plan_sync.STEP_TYPE, 7)
        self.assertEqual(want["assignees"], [plan_sync.ASSIGNEE])
        self.assertEqual((want["type"], want["milestone"]), ("Step", 7))

    def test_issue_someone_holds_keeps_its_assignee(self):
        cur = {"title": "T", "body": "B", "labels": [{"name": "type:chore"}], "milestone": None,
               "type": {"name": "Step"}, "assignees": [{"login": "someone"}]}
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.STEP_TYPE, None)
        self.assertNotIn("assignees", want)
        self.assertFalse(plan_sync._differs(cur, want))

    def test_unassigned_or_untyped_issue_is_updated(self):
        cur = {"title": "T", "body": "B", "labels": [{"name": "type:chore"}], "milestone": None,
               "type": None, "assignees": []}
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.STEP_TYPE, None)
        self.assertEqual(want["assignees"], [plan_sync.ASSIGNEE])
        self.assertTrue(plan_sync._differs(cur, want))
        cur["assignees"] = [{"login": "someone"}]
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.STEP_TYPE, None)
        self.assertTrue(plan_sync._differs(cur, want), "the missing type alone is a difference")

    def test_issue_of_another_level_is_retyped(self):
        cur = {"title": "T", "body": "B", "labels": [{"name": "type:chore"}], "milestone": None,
               "type": {"name": "Task"}, "assignees": [{"login": "someone"}]}
        want = plan_sync.wanted(cur, "T", "B", ["type:chore"], plan_sync.STEP_TYPE, None)
        self.assertTrue(plan_sync._differs(cur, want))


class PlanDocTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.tasks, self.steps = parse(GOOD)
        self.hours = plan_sync.SIZES

    def test_task_table_lists_each_module_and_its_tasks(self):
        text = plan_sync.hours_text
        first, second = self.hours["S"] + self.hours["M"], self.hours["L"]
        table = plan_sync.task_table(self.milestones, self.tasks, self.steps)
        self.assertEqual(table.splitlines()[2:], [
            f"| **P0 Foundation** | 3 | {text(first + second)} | 2026-11-30 | 2026-12-13 |",
            f"| P0-A Repository rules | 2 | {text(first)} | 2026-11-30 | 2026-12-06 |",
            f"| P0-B Demo data | 1 | {text(second)} | 2026-12-07 | 2026-12-13 |",
        ])

    def test_load_table_adds_up_each_week(self):
        text = plan_sync.hours_text
        first, second = self.hours["S"] + self.hours["M"], self.hours["L"]
        self.assertEqual(plan_sync.load_table(self.steps).splitlines()[2:], [
            f"| 2026-11-30 | 2 | {text(first)} | P0 {text(first)} |",
            f"| 2026-12-07 | 1 | {text(second)} | P0 {text(second)} |",
            f"| **Total** | 3 | {text(first + second)} | |",
        ])

    def test_hours_are_printed_without_a_trailing_zero(self):
        self.assertEqual([plan_sync.hours_text(value) for value in (3, 3.0, 1.5, 20.5)],
                         ["3", "3", "1.5", "20.5"])

    def test_fill_replaces_only_what_is_between_the_markers(self):
        text = "before\n<!-- load:start -->\nold\nrows\n<!-- load:end -->\nafter\n"
        self.assertEqual(plan_sync.fill(text, {"load": "new"}),
                         "before\n<!-- load:start -->\nnew\n<!-- load:end -->\nafter\n")
        with self.assertRaisesRegex(ValueError, "no 'tasks' block"):
            plan_sync.fill(text, {"tasks": "new"})

    def test_plan_document_matches_the_plan_files(self):
        milestones, tasks, steps = plan_sync.parse_plan(plan_sync.PLAN_DIR)
        text = plan_sync.PLAN_DOC.read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(plan_sync.plan_doc(text, milestones, tasks, steps), text,
                         "run python scripts/plan_sync.py --write")


class BoardTest(unittest.TestCase):
    def setUp(self):
        self.milestones, self.tasks, self.steps = parse(GOOD)

    def test_step_card_carries_six_values(self):
        self.assertEqual(plan_sync.board_values(self.steps[2], "step"), {
            "Priority": "P3", "Phase": "Phase 1", "Track": "A Platform",
            "Start": "2026-12-07", "Target": "2026-12-13", "Estimate": plan_sync.SIZES["L"]})

    def test_task_card_spans_its_steps_and_has_no_estimate(self):
        self.assertEqual(plan_sync.board_values(self.tasks[0], "task"), {
            "Priority": "P1", "Phase": "Phase 1", "Track": "A Platform",
            "Start": "2026-11-30", "Target": "2026-12-06"})

    def test_epic_card_spans_its_module_and_has_no_priority(self):
        self.assertEqual(plan_sync.board_values(self.milestones[0], "epic"), {
            "Phase": "Phase 1", "Track": "A Platform",
            "Start": "2026-11-30", "Target": "2026-12-13"})

    def test_field_options_cover_every_value_a_card_can_take(self):
        specs = {f["name"]: f for f in plan_sync.board_fields()}
        fields = {name: [option for option, _, _ in f["options"]] for name, f in specs.items()}
        self.assertEqual(fields["Priority"], ["P1", "P2", "P3"])
        self.assertIn("Phase 2", fields["Phase"])
        self.assertIn("C Schedule", fields["Track"])
        self.assertEqual((fields["Start"], fields["Target"], fields["Estimate"]), ([], [], []))
        self.assertEqual(specs["Estimate"]["type"], "NUMBER")

    def test_cards_are_keyed_by_the_url_of_each_level(self):
        records = {"epic": {"P0": {"html_url": "https://github.com/o/h/issues/9"}},
                   "task": {"P0-A": {"html_url": "https://github.com/o/h/issues/10"}},
                   "step": {"P0-03": {"html_url": "https://github.com/o/r/issues/3"}}}
        cards = plan_sync.board_cards(self.milestones, self.tasks, self.steps, records)
        self.assertEqual(set(cards), {"https://github.com/o/h/issues/9",
                                      "https://github.com/o/h/issues/10",
                                      "https://github.com/o/r/issues/3"})
        self.assertNotIn("Priority", cards["https://github.com/o/h/issues/9"])
        self.assertNotIn("Estimate", cards["https://github.com/o/h/issues/10"])
        self.assertIn("Estimate", cards["https://github.com/o/r/issues/3"])

    def test_only_missing_or_different_values_are_written(self):
        cards = {"u1": {"Priority": "P1", "Start": "2026-11-30", "Estimate": 3},
                 "u2": {"Priority": "P2", "Estimate": 6}, "u3": {"Priority": "P3"}}
        items = {"u1": {"id": "I1", "values": {"Priority": "P1", "Start": "2026-11-23",
                                               "Estimate": 3.0}},
                 "u2": {"id": "I2", "values": {"Estimate": 1.0}}}
        self.assertEqual(plan_board.changed_values(cards, items),
                         [("I1", "Start", "2026-11-30"), ("I2", "Priority", "P2"),
                          ("I2", "Estimate", 6)])

    def test_stored_value_reads_options_dates_and_numbers(self):
        self.assertEqual(plan_board.stored_value({"name": "P1"}), "P1")
        self.assertEqual(plan_board.stored_value({"date": "2026-11-30"}), "2026-11-30")
        self.assertEqual(plan_board.stored_value({"number": 0.0}), 0.0)
        self.assertIsNone(plan_board.stored_value({"field": {"name": "Notes"}}))

    def test_value_mutation_uses_option_ids_dates_and_numbers(self):
        fields = {"Priority": {"id": "F1", "dataType": "SINGLE_SELECT",
                               "options": {"P1": {"id": "O1"}}},
                  "Start": {"id": "F2", "dataType": "DATE", "options": {}},
                  "Estimate": {"id": "F3", "dataType": "NUMBER", "options": {}}}
        text = plan_board.value_mutation("P", fields, [("I1", "Priority", "P1"),
                                                      ("I1", "Start", "2026-11-30"),
                                                      ("I1", "Estimate", 3)])
        self.assertIn('fieldId: "F1", value: {singleSelectOptionId: "O1"}', text)
        self.assertIn('fieldId: "F2", value: {date: "2026-11-30"}', text)
        self.assertIn('fieldId: "F3", value: {number: 3}', text)
        self.assertEqual(text.count("updateProjectV2ItemFieldValue"), 3)

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
