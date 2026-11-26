# M08 - Meetings

Track: C. Phase: 2. Size: M. Depends on: M05, M06. Unlocks: later modules (people,
transcripts).

## Goal

Notes for any meeting in two taps: what was agreed, who owes what, and the tasks that
follow, attached to the event even when it moves.

## Design notes

- A meeting note belongs to an event from a calendar or to a meeting created by hand. It
  has an agenda, notes, decisions and action items.
- Action items become tasks with an owner and a due date, linked back to the meeting.
- Notes follow the event through reschedules and series changes by its stable identity
  at the provider. When an event disappears, the note is kept and marked as detached.
- Notes are typed by the user. Imported transcripts and automatic notes are later
  modules with their own consent rules.
- Before a meeting, the previous notes of the same series and their open action items
  are one tap away.
- The note stores attendee names as they appear on the event. Nothing is sent to
  attendees.

## Tasks

- M08-A [feature] Notes on a meeting -- Done when: "take notes" on an agenda event, or on a meeting made by hand, opens its note, and the note stays attached or is marked as detached when the event is rescheduled, cancelled or split. -- Steps: M08-01, M08-10, M08-02, M08-03, M08-09
- M08-B [feature] Decisions and action items -- Done when: agenda, notes, decisions and action items are edited on one screen, an action item becomes a task that shows its state on the note, and the note gives a summary ready to paste. -- Steps: M08-04, M08-11, M08-07
- M08-C [feature] Series, templates and search -- Done when: a recurring meeting opens with its earlier notes, its open action items and its default template, and search finds notes, decisions and action items by meeting and attendee inside the workspaces in view. -- Steps: M08-06, M08-05, M08-08

## Steps

### work-hub

- M08-01 [adr p1 S] Meeting identity across calendar changes -- Done when: accepted: which provider identifiers attach a note to an event and to a series, and what happens on a reschedule, a split series and a deletion.

### work-hub-backend

- M08-04 [feature p2 M] Decisions and action items -- Done when: decisions are stored as marked blocks of a note, an action item becomes a linked task with an owner and a due date, and completing the task shows on the note.
- M08-05 [feature p3 S] Templates -- Done when: a workspace has note templates (for example 1:1, standup, client call) and a default template per recurring series.
- M08-08 [feature p2 S] Search covers meetings -- Done when: notes, decisions and action items are searchable with filters for meeting and attendee, under the same walls.
- M08-09 [test p1 M] Notes survive calendar changes -- Done when: tests reschedule, cancel and split a series against recorded provider data, and the notes stay attached or are marked as detached.
- M08-10 [feature p1 M] Meeting notes API -- Done when: a note attaches to an event or to a meeting made by hand through the identifiers of the ADR, carries an agenda, notes, decisions and action items, lists the earlier notes and open action items of its series, and follows the version and isolation rules of other notes.

### work-hub-frontend

- M08-02 [feature p1 M] Notes on an event -- Done when: "take notes" on an agenda event opens a note with the title, time and attendees filled in, and the note opens again from the event, the search and the reminder.
- M08-03 [feature p2 S] Meetings without an event -- Done when: a meeting can be created by hand in a workspace with the same note structure.
- M08-06 [feature p2 S] Series history -- Done when: a recurring meeting shows its earlier notes and the action items still open before the next one starts.
- M08-07 [feature p3 S] Follow-up summary -- Done when: a note produces a Markdown summary of its decisions and action items, ready to paste into a message.
- M08-11 [feature p1 M] Meeting note editor -- Done when: agenda, notes, decisions and action items are edited on one screen, an action item becomes a task in one step and shows its state, and a template can be chosen or set as the default of a series.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2027-02-22 | M08-01, M08-02, M08-03, M08-04, M08-05, M08-06, M08-07, M08-08, M08-09, M08-10, M08-11 |

## Measures

- Taps from a reminder to typing in the meeting's note.
