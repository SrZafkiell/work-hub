"""Tests for plan_schedule: the order of the steps and how the weeks are filled.

Run from the repository root:
    python -m unittest discover -s scripts -p "test_*.py"
"""
import unittest

import plan_schedule
import plan_sync

WEEKS = ("2026-11-30", "2026-12-07", "2026-12-14", "2026-12-21")


def step(plan_id: str, hours: float, start: str = WEEKS[0], milestone: str = "P0") -> dict:
    return {"id": plan_id, "hours": hours, "start": start, "milestone": milestone, "phase": "1"}


def task(plan_id: str, *steps: str) -> dict:
    return {"id": plan_id, "steps": list(steps)}


class OrderTest(unittest.TestCase):
    def test_steps_go_by_week_then_module_then_task_then_position(self):
        steps = [step("M01-01", 1, milestone="M01"), step("P0-03", 1), step("P0-02", 1),
                 step("P0-01", 1), step("P0-04", 1, start=WEEKS[1])]
        tasks = [task("P0-A", "P0-01", "P0-04"), task("P0-B", "P0-03", "P0-02"),
                 task("M01-A", "M01-01")]
        weeks = {s["id"]: s["start"] for s in steps}
        self.assertEqual([s["id"] for s in plan_schedule.in_order(tasks, steps, weeks)],
                         ["P0-01", "P0-03", "P0-02", "M01-01", "P0-04"])


class SpreadTest(unittest.TestCase):
    def weeks_of(self, hours: list[float], capacity: float) -> list[str]:
        steps = [step(f"P0-{n:02d}", value) for n, value in enumerate(hours, 1)]
        weeks = plan_schedule.spread(steps, capacity, WEEKS[0])
        return [weeks[s["id"]] for s in steps]

    def test_each_week_is_filled_up_to_the_capacity(self):
        self.assertEqual(self.weeks_of([3, 3, 3, 1], 6), [WEEKS[0], WEEKS[0], WEEKS[1], WEEKS[1]])

    def test_a_step_that_does_not_fit_starts_the_next_week(self):
        self.assertEqual(self.weeks_of([3, 1, 3, 0.5], 6), [WEEKS[0], WEEKS[0], WEEKS[1], WEEKS[1]])

    def test_a_step_larger_than_the_capacity_gets_a_week_of_its_own(self):
        self.assertEqual(self.weeks_of([3, 8, 1], 6), [WEEKS[0], WEEKS[1], WEEKS[2]])

    def test_half_hours_add_up_to_a_full_week(self):
        self.assertEqual(self.weeks_of([0.5] * 5, 2), [WEEKS[0]] * 4 + [WEEKS[1]])


class SettleTest(unittest.TestCase):
    def setUp(self):
        self.steps = [step("P0-01", 3), step("P0-02", 3), step("P0-03", 3),
                      step("P0-04", 1, start=WEEKS[1]), step("P0-05", 3, start=WEEKS[1])]
        self.tasks = [task("P0-A", "P0-01", "P0-02", "P0-03"), task("P0-B", "P0-04", "P0-05")]

    def settled(self, capacity: float, since: str = WEEKS[0]) -> dict[str, str]:
        return plan_schedule.settle(self.tasks, self.steps, capacity, since)

    def test_the_plan_is_packed_in_its_own_order(self):
        self.assertEqual(self.settled(6), {
            "P0-01": WEEKS[0], "P0-02": WEEKS[0], "P0-03": WEEKS[1], "P0-04": WEEKS[1],
            "P0-05": WEEKS[2]})

    def test_a_second_run_changes_nothing(self):
        first = self.settled(6)
        for item in self.steps:
            item["start"] = first[item["id"]]
        self.assertEqual(self.settled(6), first)

    def test_weeks_before_since_keep_their_steps(self):
        weeks = self.settled(3, since=WEEKS[1])
        self.assertEqual([weeks[f"P0-0{n}"] for n in (1, 2, 3)], [WEEKS[0]] * 3)
        self.assertEqual((weeks["P0-04"], weeks["P0-05"]), (WEEKS[1], WEEKS[2]))

    def test_load_adds_up_the_hours_of_each_week(self):
        self.assertEqual(plan_schedule.load(self.steps, self.settled(6)),
                         {WEEKS[0]: 6, WEEKS[1]: 4, WEEKS[2]: 3})


class RewriteTest(unittest.TestCase):
    TEXT = ("## Schedule\n\nPlanned weeks.\n\n| Week of | Steps |\n|---|---|\n"
            "| 2026-11-30 | P0-01, P0-02 |\n| 2026-12-07 | P0-03 |\n\n## Measures\n\n- One.\n")

    def test_only_the_rows_of_the_table_change(self):
        text = plan_schedule.rewrite(self.TEXT, {WEEKS[0]: ["P0-01"], WEEKS[1]: ["P0-03", "P0-02"]})
        self.assertEqual(text, self.TEXT.replace(
            "| 2026-11-30 | P0-01, P0-02 |\n| 2026-12-07 | P0-03 |\n",
            "| 2026-11-30 | P0-01 |\n| 2026-12-07 | P0-02, P0-03 |\n"))

    def test_a_file_without_a_schedule_table_is_refused(self):
        with self.assertRaisesRegex(ValueError, "one Schedule table"):
            plan_schedule.rewrite("## Schedule\n\nNo table.\n", {WEEKS[0]: ["P0-01"]})


class RealPlanTest(unittest.TestCase):
    def setUp(self):
        _, self.tasks, self.steps = plan_sync.parse_plan(plan_sync.PLAN_DIR)

    def test_no_week_holds_more_than_the_capacity(self):
        weeks = {s["id"]: s["start"] for s in self.steps}
        for week, hours in plan_schedule.load(self.steps, weeks).items():
            self.assertLessEqual(hours, plan_schedule.CAPACITY, f"week of {week}")

    def test_the_schedule_is_what_the_script_would_write(self):
        first = min(s["start"] for s in self.steps)
        weeks = plan_schedule.settle(self.tasks, self.steps, plan_schedule.CAPACITY, first)
        moved = [s["id"] for s in self.steps if weeks[s["id"]] != s["start"]]
        self.assertEqual(moved, [], "run python scripts/plan_schedule.py --write")


if __name__ == "__main__":
    unittest.main()
