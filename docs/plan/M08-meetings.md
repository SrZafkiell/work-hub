# M08 - Meetings

Track: C. Size: M. Depends on: M05, M06. Unlocks: later modules (people, transcripts).

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

## Issues

- M08-01 [adr] Meeting identity across calendar changes -- Done when: accepted: which provider identifiers attach a note to an event and to a series, and what happens on a reschedule, a split series and a deletion.
- M08-02 [feature] Notes on an event -- Done when: "take notes" on an agenda event opens a note with the title, time and attendees filled in, and the note opens again from the event, the search and the reminder.
- M08-03 [feature] Meetings without an event -- Done when: a meeting can be created by hand in a workspace with the same note structure.
- M08-04 [feature] Decisions and action items -- Done when: decisions are marked in a note, action items become linked tasks with an owner and a due date, and completing the task shows in the note.
- M08-05 [feature] Templates -- Done when: a workspace has note templates (for example 1:1, standup, client call) and a default template per recurring series.
- M08-06 [feature] Series history -- Done when: a recurring meeting shows its earlier notes and the action items still open before the next one starts.
- M08-07 [feature] Follow-up summary -- Done when: a note produces a Markdown summary of its decisions and action items, ready to paste into a message.
- M08-08 [feature] Search covers meetings -- Done when: notes, decisions and action items are searchable with filters for meeting and attendee, under the same walls.
- M08-09 [test] Notes survive calendar changes -- Done when: tests reschedule, cancel and split a series against recorded provider data, and the notes stay attached or are marked as detached.

## Measures

- Taps from a reminder to typing in the meeting's note.
