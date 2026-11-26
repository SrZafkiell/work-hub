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

## Tasks

- M07-A [feature] Push to a device -- Done when: a signed-in device subscribes from the settings screen after a user action, gets a name, receives a test notification with the app closed, and unsubscribes. -- Steps: M07-01, M07-02, M07-11
- M07-B [feature] Reminders on time -- Done when: a reminder for an event or a task arrives once per device at the right minute, by the lead times and quiet hours set in the app, and a restart neither loses nor repeats one. -- Steps: M07-03, M07-04, M07-12
- M07-C [feature] Digest, actions and privacy -- Done when: the morning digest opens Today, a notification on Android can snooze, complete a task or open the join link, and the server respects a workspace that hides details and a focus mode that is on. -- Steps: M07-06, M07-05, M07-07
- M07-D [test] Delivery proven and watched -- Done when: on a real Android phone with the app closed and the screen locked reminders arrive within a minute across a day of use, the owner is alerted when an account has no working device, and a second channel is chosen or rejected. -- Steps: M07-08, M07-09, M07-10

## Steps

### work-hub

- M07-01 [adr p1 S] Reminders by Web Push -- Done when: accepted, with the payload contents, the privacy levels and the delivery limits of each platform.
- M07-09 [test p1 M] Reminder test on a real phone -- Done when: on an Android phone with the app installed, closed and the screen locked, reminders arrive within a minute of their time across a day of use, and the result is recorded.
- M07-10 [spike p3 S] Second channel for critical reminders -- Done when: the options for a reminder that push failed to deliver are compared with their privacy cost, and one is chosen or rejected.

### work-hub-backend

- M07-02 [feature p1 M] Device subscriptions -- Done when: a signed-in device can register a push subscription, name it, ask for a test notification and remove it, and the server keys can be rotated.
- M07-03 [feature p2 M] Reminder rules -- Done when: default lead times exist per workspace and per calendar, an event or a task can override them, and quiet hours apply to task reminders.
- M07-04 [feature p1 L] Reminder scheduler -- Done when: reminders are sent once per device at the right minute, survive restarts and retries without duplicates, can be snoozed, and follow the late policy after downtime, with a test for each.
- M07-06 [feature p3 S] Morning digest -- Done when: at a chosen time the account receives the day's meetings, clashes and due tasks in one notification that opens Today.
- M07-07 [feature p2 M] Notification privacy -- Done when: a workspace can hide details in notifications, focus mode silences the other workspaces, and both are enforced on the server.
- M07-08 [security p1 M] Delivery monitoring -- Done when: the reminder loop reports to the outside heartbeat, dead subscriptions are removed, the owner is alerted when an account has no working device, and each alert was triggered once on purpose.

### work-hub-frontend

- M07-05 [feature p3 M] Notification actions -- Done when: on Android a notification can open the event's notes, open the join link, snooze, or complete a task.
- M07-11 [feature p1 L] Push in the web app -- Done when: the service worker receives and shows notifications with the app closed, a device subscribes, is named, tests itself and unsubscribes from the settings screen, and the permission prompt appears only after a user action.
- M07-12 [feature p2 M] Reminder settings -- Done when: lead times per workspace and calendar, the override on an event or a task, quiet hours, the digest time and the detail level are editable.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2027-03-22 | M07-01, M07-02, M07-03, M07-04, M07-11 |
| 2027-03-29 | M07-05, M07-06, M07-07, M07-08, M07-09, M07-10, M07-12 |

## Measures

- Delay between the scheduled and the delivered time (median and p95) on Android.
- Delivery success over a week of daily use.
