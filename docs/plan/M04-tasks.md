# M04 - Tasks

Track: B. Phase: 1. Size: M. Depends on: M03. Unlocks: M05, M07.

## Goal

Capture a task in two seconds from the phone or the keyboard, and see what matters today
across every workspace.

## Design notes

- A task has a title, Markdown notes, a status (inbox, next, waiting, done, dropped), an
  optional due date and scheduled date, a priority, an owner and tags. Checklists live
  in the notes as Markdown checkboxes; there are no subtasks.
- The owner is the account or a named person (free text until the people module
  exists). A task owned by someone else is "waiting on" and carries a follow-up date.
- Quick add is one text field with shortcuts for the workspace, the date and tags. On a
  phone it is the first control on the first screen.
- Today spans the workspaces in view: overdue, due today, scheduled today and follow-ups
  due. With focus mode on, that is one workspace. It is one query in the backend, with a
  budget.
- Times are stored in UTC. A due date is a calendar date in the account's time zone.
- Changes of status, owner and dates are kept as history; the weekly summary of a later
  module is built from it.

## Tasks

- M04-A [feature] Tasks and lists -- Done when: a task is created, edited with the version check, and found again in the inbox, next, waiting and done lists of its workspace, with its history. -- Steps: M04-01, M04-04, M04-13, M04-09
- M04-B [feature] Today -- Done when: Today shows the overdue, due, scheduled and follow-up items of the workspaces in view from a single query, each one completed, rescheduled or deferred in one action, inside a measured p95 budget. -- Steps: M04-11, M04-03, M04-10
- M04-C [feature] Capture -- Done when: a task is saved from one field with shortcuts, on a desktop and on a phone, and from the share sheet of another Android app. -- Steps: M04-02, M04-07
- M04-D [feature] Follow-ups and recurrence -- Done when: a task that waits on someone returns to Today on its follow-up date, and a recurring task creates its next occurrence correctly across month ends and time zone changes. -- Steps: M04-05, M04-06
- M04-E [feature] Bulk and keyboard actions -- Done when: several tasks are completed, rescheduled, tagged or moved in one all-or-none request, without a mouse, with a confirmation before a move to another workspace. -- Steps: M04-12, M04-08

## Steps

### work-hub-backend

- M04-01 [feature p1 M] Task model and API -- Done when: tasks have the fields in the design notes with the sync-ready conventions, can be listed, sorted and filtered by status, tag, owner and date, and are validated and documented in the contract.
- M04-06 [feature p2 M] Recurring tasks -- Done when: daily, weekly and monthly rules create the next task when one is completed, with tests across month ends and time zone changes.
- M04-09 [feature p3 S] Task history -- Done when: changes of status, owner and dates are recorded per task and returned with it.
- M04-10 [test p3 S] Today view budget -- Done when: a baseline is measured on seeded demo data, a p95 budget is set from it, and CI fails on a regression.
- M04-11 [feature p1 M] Today query -- Done when: one endpoint returns the overdue, due, scheduled and follow-up items of the workspaces in view, grouped by workspace, in a single query.
- M04-12 [feature p3 M] Bulk task changes -- Done when: one request completes, reschedules, tags or moves several tasks, all or none, under the same isolation rules as a single change.

### work-hub-frontend

- M04-02 [feature p1 M] Quick add -- Done when: one field creates a task with shortcuts for the workspace, the due date and tags, from a keyboard shortcut on a desktop and as the first control on a phone.
- M04-03 [feature p1 M] Today view -- Done when: overdue, due, scheduled and follow-up items appear grouped by workspace, respect focus mode, and can be completed, rescheduled or deferred in one action.
- M04-04 [feature p1 M] Workspace lists and filters -- Done when: inbox, next, waiting and done lists exist per workspace, with sorting and filters by tag, owner and date.
- M04-05 [feature p2 S] Waiting on -- Done when: a task owned by someone else shows its follow-up date, appears in a waiting list per person, and returns to Today on that date.
- M04-07 [feature p3 M] Share into the inbox on Android -- Done when: text or a link shared from another Android app into the installed web app becomes an inbox task in a chosen workspace.
- M04-08 [feature p3 M] Keyboard and bulk actions -- Done when: lists are usable without a mouse, and several tasks can be completed, rescheduled, tagged or moved at once, with a confirmation before a move to another workspace.
- M04-13 [feature p2 M] Task detail -- Done when: a task opens with its notes rendered, its checklist usable, its links and its history, and an edit is saved with the version check.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2027-02-15 | M04-01, M04-04, M04-13 |
| 2027-02-22 | M04-02, M04-03, M04-05, M04-06, M04-07, M04-08, M04-09, M04-10, M04-11, M04-12 |

## Measures

- Time from opening the app to a saved task, on a phone.
- Today query p95 on seeded data.
