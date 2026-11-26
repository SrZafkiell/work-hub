# M06 - Calendars

Track: C. Phase: 2. Size: XL. Depends on: M03, P1. Unlocks: M07 (event reminders), M08.

## Goal

Every calendar you use, from Google and Microsoft accounts, in one agenda that is
read-only, current within minutes, and honest about clashes.

## Design notes

- Read-only scopes only: the calendar list and events. Writing to a calendar is a later
  module with its own consent.
- An organization can refuse a personal app, or require an administrator's approval.
  The first step is a spike that tests each kind of account before anything else is
  built, and the plan has two fallbacks: a read-only ICS subscription, and sharing the
  calendar with a personal account that can connect.
- Check your organization's policy before connecting a work account to a personal tool.
  Connected accounts are off by default in every workspace.
- Tokens are the most valuable data on the server. They are encrypted with a key that
  is not in the database or its backups, never logged, never returned by the API, and
  revoked at the provider when an account is disconnected.
- Polling with incremental sync is the base (sync tokens on Google, delta queries on
  Microsoft Graph). Change notifications from the providers only trigger an earlier
  poll, so a lost notification costs minutes, not correctness.
- Recurring events are expanded by the provider inside a rolling window; the hub never
  implements recurrence rules itself.
- Only the fields the agenda needs are stored: title, times and time zone, location,
  join link, attendee names and response status. Bodies and attachments are not stored.
  A calendar can be set to "busy only", which stores no titles.
- Event text is written by other people, including strangers who send invitations. It
  is untrusted input everywhere: stored and shown as plain text, never fetched, never
  interpreted, in the backend and in the web app.
- Each calendar feeds exactly one workspace, chosen when it is connected.
- A Google OAuth app left in testing mode loses its tokens every seven days, so the app
  runs in production mode and the unverified-app screen is accepted once.
- The provider's redirect back to the hub arrives from another site, so the strict
  session cookie is not sent with it: the callback page finishes the exchange with a
  request from the hub's own origin.
- The worker process arrives with this module: one more container from the API image,
  with a job queue in PostgreSQL instead of a message broker.

## Tasks

- M06-A [spike] Calendar access decided -- Done when: it is written down which personal and organization accounts can grant read-only calendar access at each provider, with the fallback for each refusal, and the access model is accepted. -- Steps: M06-01, M06-02
- M06-B [feature] Background worker -- Done when: a worker container runs scheduled and queued jobs from a queue in PostgreSQL, survives a restart without losing or repeating work, and is watched by the outside heartbeat. -- Steps: M06-03, M06-04, M06-19
- M06-C [feature] Connected accounts -- Done when: a person connects a Google account, a Microsoft account or an ICS address behind the step-up prompt, gives each calendar a workspace and a detail level, and disconnects with one action that revokes the grant; no token can be read from a database dump. -- Steps: M06-05, M06-06, M06-07, M06-08, M06-09, M06-20, M06-16
- M06-D [feature] Calendar sync -- Done when: each chosen calendar stays in sync incrementally, recovers from an expired sync token and from provider limits, reports its state, and the owner is alerted when an account stops syncing. -- Steps: M06-10, M06-11, M06-17, M06-18
- M06-E [feature] Merged agenda -- Done when: day and week views show every calendar in view in the right local time, with clashes marked and the join link as one action. -- Steps: M06-21, M06-13, M06-14, M06-12
- M06-F [security] Untrusted event content -- Done when: text from a calendar event is stored and shown as plain text on every screen and in every notification, the server never fetches a link from an event, and tests cover script, markup and oversized fields. -- Steps: M06-15, M06-22

## Steps

### work-hub

- M06-01 [spike p1 L] Which accounts can connect -- Done when: a test app asks for read-only calendar access from a personal and an organization account at each provider, and the result, the approval an administrator must give and the fallback for each refusal are written down; runs during Phase 1.
- M06-02 [adr p1 S] Calendar access model -- Done when: accepted: read-only scopes, polling with incremental sync, the stored fields, the busy-only level and the fallbacks.
- M06-03 [adr p2 S] Background jobs on PostgreSQL -- Done when: accepted: a worker process with a database-backed queue instead of a message broker, with the limits that would change the choice.
- M06-19 [chore p1 S] Worker in the Compose stack -- Done when: the worker container runs from the API image with the same hardening, limits and health check as the API, and the outside heartbeat watches it.

### work-hub-backend

- M06-04 [feature p1 L] Worker service -- Done when: a worker command runs scheduled and queued jobs with retries, back-off and a heartbeat, and survives a restart without losing or repeating work.
- M06-05 [security p1 L] Token vault -- Done when: refresh tokens are encrypted with a key outside the database and its backups, the key can be rotated, tokens never appear in logs or API responses, and a test on a database dump proves it.
- M06-06 [feature p1 L] Connect a Google account -- Done when: the authorization-code flow with PKCE, state and an exact redirect address grants the read-only calendar scopes after a step-up check, and the OAuth app is in production mode.
- M06-07 [feature p1 L] Connect a Microsoft account -- Done when: the same flow works for organization and personal Microsoft accounts with delegated read-only calendar access.
- M06-08 [feature p2 M] ICS subscription -- Done when: a secret calendar address can be added as a read-only source, stored like a token, and fetched by a client that refuses private addresses, redirects to them, large bodies and slow responses.
- M06-09 [feature p1 M] Calendar selection and workspace mapping -- Done when: after connecting, the calendars of an account can be listed and each one given a workspace and a detail level, and nothing syncs before that.
- M06-10 [feature p1 L] Sync engine -- Done when: each calendar syncs incrementally, recovers from an expired sync token with a full resync, backs off on limits, handles moved, cancelled and deleted events, and repeating a sync changes nothing.
- M06-11 [feature p3 M] Change notifications -- Done when: provider notifications are validated, trigger an early sync, are renewed before they expire, and losing them only falls back to the polling interval.
- M06-13 [feature p2 S] Clash detection -- Done when: the agenda query marks overlapping events from different calendars, busy-only events included, and ignores declined events.
- M06-14 [feature p2 S] Join links -- Done when: the meeting link of an event is found at sync time and returned with the event.
- M06-15 [security p1 S] Untrusted event content -- Done when: event text is stored as plain text with size limits, the server never fetches a link from an event, and tests cover script, markup and oversized fields.
- M06-16 [security p1 M] Disconnect and revoke -- Done when: one request revokes the grant at the provider, deletes the stored tokens and, on request, the synced events; and a `hubctl` command revokes every connected account at once and was run once.
- M06-17 [feature p2 S] Sync status and alerts -- Done when: the status endpoint reports the last and next sync and the errors per account, and the owner is alerted when an account stops syncing.
- M06-18 [test p2 M] Provider contract tests -- Done when: recorded provider responses with made-up data cover paging, expired tokens, throttling and deletions, and a nightly job checks the live APIs with test accounts.
- M06-21 [feature p1 M] Agenda query -- Done when: one endpoint returns the events of the calendars in view for a range of days, with all-day and multi-day events and each event's time zone, under the same walls as everything else.

### work-hub-frontend

- M06-12 [feature p1 L] Merged agenda -- Done when: day and week views show every calendar in view with workspace colors, all-day and multi-day events, the right local time for events created in other time zones, clashes marked, the join link as one action, and focus mode.
- M06-20 [feature p1 M] Connected accounts screens -- Done when: the user connects a Google or a Microsoft account or adds an ICS address behind the step-up prompt, chooses the calendars with their workspace and detail level, sees the sync state of each, and disconnects with one action.
- M06-22 [security p1 S] Event text renders as plain text -- Done when: titles, locations and names from events are never interpreted as markup or links on any screen or in any notification, with tests for script and markup.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2027-01-18 | M06-01 |
| 2027-02-01 | M06-02, M06-03, M06-04, M06-05, M06-19 |
| 2027-02-08 | M06-06, M06-07, M06-08, M06-09, M06-10, M06-11, M06-15, M06-16, M06-17, M06-20 |
| 2027-02-15 | M06-12, M06-13, M06-14, M06-18, M06-21, M06-22 |

## Measures

- Sync lag from a change at the provider to the agenda, with polling only and with
  change notifications.
- API calls per connected account per day.
