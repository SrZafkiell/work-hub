# How to read this board

One board for every repository of work-hub. The plan files in
[docs/plan](https://github.com/SrZafkiell/work-hub/tree/main/docs/plan) are the source: a
script files the issues and sets the fields, so plan data is changed there, not here.

## Levels

- **Epic**: one per module, in the home repository. Its bar on the roadmap runs from the
  module's first week to its last.
- **Task**: an issue with a "Done when" line, in the repository that does the work. It is
  a sub-issue of its module's epic.
- **Step**: an optional sub-issue of a task, added when the task needs to be split.

## What every card carries

| Field | Meaning |
|---|---|
| Assignees | Who answers for it. Never empty. |
| Status | Todo; In Progress once a pull request is linked; Done when it is closed. |
| Priority | P1 blocks other work or a safety property. P2 is part of the release. P3 can ship after the release. |
| Phase | The release it belongs to. |
| Track | A Platform, B Core or C Schedule. |
| Start, Target | Its planned week, Monday to Sunday. |
| Milestone | Its module. The milestone is due on the module's last day. |
| Labels | `type:*`, `area:*`, `prio:*` and `phase:*`, one of each, plus the flags below. |

Flags are set by hand when they apply: `blocked`, `needs:decision` and `tech-debt` on an
issue, `breaking-change` on a pull request.

## Views

| View | Shows |
|---|---|
| Roadmap | The epics on a timeline, by track, with the milestones as markers. |
| Progress | The epics with the share of their tasks that is done. |
| Milestones | The tasks of each module, by target date. |
| By repository | The tasks on a timeline, one band per repository. |
| This week | Open tasks due by Sunday, as a board with one lane per repository. |
| Late | Open cards past their target date. |
| Blocked | Open cards flagged `blocked` or `needs:decision`. |
| In review | Open cards with a linked pull request. |
| Done last 7 days | What was closed in the last week, by repository. |
| My work | Your tasks as a board. |
| Tech debt | What was left for later, by priority. |
| All work | Everything, by phase; slice it by repository. |

## Rules

- A pull request names its issue in its body: `Closes #12` when it finishes the issue,
  `Refs #12` when it does not. Linking moves the card to In Progress; merging or closing
  moves it to Done.
- Every pull request has an assignee and carries the type and area labels and the
  milestone of its issue.
- A task is closed only when its "Done when" holds and none of its steps is open. A late
  card gets a new date in the plan, not an early close.
- An epic is closed by hand, when every task under it is done.
- Dates, priorities and wording change in the plan file first; the sync script then
  updates the issues and this board.

<!-- maintenance -->

## Keeping the board

Everything above this section is published as the README of the board.

`python scripts/plan_sync.py --apply --project 2 --views --guide` files the plan, sets
the fields of every card, creates the views with their filters and publishes the guide.
What the API cannot set on a view is saved once in the browser, in the View menu of its
tab. `python scripts/plan_board.py 2` reports every view that still differs from the
table below.

| View | Layout | Filter | Group by | Sort | Saved in the browser |
|---|---|---|---|---|---|
| Roadmap | Roadmap | `type:Epic` | Track | Start, ascending | Dates Start and Target; markers Milestone; zoom Quarter |
| Progress | Table | `type:Epic` | - | Start, ascending | - |
| Milestones | Table | `type:Task -label:tech-debt` | Milestone | Target, ascending | - |
| By repository | Roadmap | `type:Task` | Repository | Start, ascending | Dates Start and Target; markers Milestone; zoom Month |
| This week | Board | `is:open target:<=@today+6d -type:Epic` | Repository (swimlanes) | Target, ascending | Columns by Status |
| Late | Table | `is:open target:<@today` | Repository | Target, ascending | - |
| Blocked | Table | `is:open label:blocked,needs:decision` | - | - | - |
| In review | Table | `is:open has:linked-pull-requests` | - | - | - |
| Done last 7 days | Table | `is:closed closed:>=@today-7d` | Repository | Closed, descending | - |
| My work | Board | `assignee:@me -type:Epic` | - | Start, ascending | Columns by Status |
| Tech debt | Table | `label:tech-debt` | Priority | Repository, ascending | - |
| All work | Table | none | Phase | Start, ascending | Slice by Repository |

Built-in workflows of the board, all on: a new item starts as Todo; a pull request linked
to an issue moves it to In Progress; a closed item and a merged pull request move to Done;
an issue set to Done is closed; sub-issues of a card are added by themselves.

A new board for another project starts as a copy of this one (`gh project copy`), which
brings the fields, the views and the workflows.
