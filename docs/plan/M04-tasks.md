# M04 - Tasks

Track: B. Size: M. Depends on: M03. Unlocks: M05, M07.

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
  due. With focus mode on, that is one workspace.
- Times are stored in UTC. A due date is a calendar date in the account's time zone.
- Changes of status, owner and dates are kept as history; the weekly summary of a later
  module is built from it.

## Issues

- M04-01 [feature] Task model and API -- Done when: tasks have the fields in the design notes with the sync-ready conventions, validated and documented in the contract.
- M04-02 [feature] Quick add -- Done when: one field creates a task with shortcuts for the workspace, the due date and tags, from a keyboard shortcut on a desktop and as the first control on a phone.
- M04-03 [feature] Today view -- Done when: overdue, due, scheduled and follow-up items appear grouped by workspace, respect focus mode, and can be completed, rescheduled or deferred in one action.
- M04-04 [feature] Workspace lists and filters -- Done when: inbox, next, waiting and done lists exist per workspace, with sorting and filters by tag, owner and date.
- M04-05 [feature] Waiting on -- Done when: a task owned by someone else carries a follow-up date, appears in a waiting list per person, and returns to Today on that date.
- M04-06 [feature] Recurring tasks -- Done when: daily, weekly and monthly rules create the next task when one is completed, with tests across month ends and time zone changes.
- M04-07 [feature] Share into the inbox on Android -- Done when: text or a link shared from another Android app into the installed web app becomes an inbox task in a chosen workspace.
- M04-08 [feature] Keyboard and bulk actions -- Done when: lists are usable without a mouse, and several tasks can be completed, rescheduled, tagged or moved at once.
- M04-09 [feature] Task history -- Done when: changes of status, owner and dates are recorded per task and shown on it.
- M04-10 [test] Today view budget -- Done when: a baseline is measured on seeded demo data, a p95 budget is set from it, and CI fails on a regression.

## Measures

- Time from opening the app to a saved task, on a phone.
- Today view p95 on seeded data.
