# M07 - Reminders

Track: C. Phase: 2. Size: L. Depends on: M04, and the worker of M06 (M06-04); event
reminders need the rest of M06. Unlocks: nothing.

## Goal

A reminder before every meeting and every due task, on the phone and the computer, plus
proof that reminders are still being delivered.

## Design notes

- Web Push: the worker sends through the browsers' push services, and the payload is
  encrypted end to end to the device. Android with Chrome is the first target; iPhone
  support is a later module, because iOS delivers only to an installed app.
- A missed reminder is the failure this module exists to prevent, and push can fail
  silently. Three defenses: a heartbeat on the reminder loop watched from outside the
  server, removal and an alert when a device's subscription dies, and a morning digest
  as a second chance.
- Reminders are computed from events and tasks into a schedule with a stable key per
  reminder and device, so a restart or a retry cannot send one twice.
- After downtime, a late reminder is sent only while it is still useful (the meeting has
  not ended); the rest are summarized once.
- Notification text respects the workspace: with details off, a notification says that
  something starts soon and nothing else. Focus mode silences the other workspaces. The
  server decides what a notification may say; the web app only shows it.
- Quiet hours are per account and apply to task reminders; an event inside quiet hours
  still reminds.

## Issues

### work-hub

- M07-01 [adr p1] Reminders by Web Push -- Done when: accepted, with the payload contents, the privacy levels and the delivery limits of each platform.
- M07-09 [test p1] Reminder test on a real phone -- Done when: on an Android phone with the app installed, closed and the screen locked, reminders arrive within a minute of their time across a day of use, and the result is recorded.
- M07-10 [spike p3] Second channel for critical reminders -- Done when: the options for a reminder that push failed to deliver are compared with their privacy cost, and one is chosen or rejected.

### work-hub-backend

- M07-02 [feature p1] Device subscriptions -- Done when: a signed-in device can register a push subscription, name it, ask for a test notification and remove it, and the server keys can be rotated.
- M07-03 [feature p2] Reminder rules -- Done when: default lead times exist per workspace and per calendar, an event or a task can override them, and quiet hours apply to task reminders.
- M07-04 [feature p1] Reminder scheduler -- Done when: reminders are sent once per device at the right minute, survive restarts and retries without duplicates, can be snoozed, and follow the late policy after downtime, with a test for each.
- M07-06 [feature p3] Morning digest -- Done when: at a chosen time the account receives the day's meetings, clashes and due tasks in one notification that opens Today.
- M07-07 [feature p2] Notification privacy -- Done when: a workspace can hide details in notifications, focus mode silences the other workspaces, and both are enforced on the server.
- M07-08 [security p1] Delivery monitoring -- Done when: the reminder loop reports to the outside heartbeat, dead subscriptions are removed, the owner is alerted when an account has no working device, and each alert was triggered once on purpose.

### work-hub-frontend

- M07-05 [feature p3] Notification actions -- Done when: on Android a notification can open the event's notes, open the join link, snooze, or complete a task.
- M07-11 [feature p1] Push in the web app -- Done when: the service worker receives and shows notifications with the app closed, a device subscribes, is named, tests itself and unsubscribes from the settings screen, and the permission prompt appears only after a user action.
- M07-12 [feature p2] Reminder settings -- Done when: lead times per workspace and calendar, the override on an event or a task, quiet hours, the digest time and the detail level are editable.

## Schedule

Planned weeks. Each issue starts on the Monday shown and is due that Sunday; the module's
epic and its milestone end with the last week. Dates change here first, and the sync
script moves the board.

| Week of | Issues |
|---|---|
| 2027-01-25 | M07-01, M07-02, M07-03, M07-04, M07-05, M07-06, M07-07, M07-08, M07-10, M07-11, M07-12 |
| 2027-02-01 | M07-09 |

## Measures

- Delay between the scheduled and the delivered time (median and p95) on Android.
- Delivery success over a week of daily use.
