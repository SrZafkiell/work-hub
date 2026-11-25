# M06 - Calendars

Track: C. Size: XL. Depends on: M03, P1. Unlocks: M07 (event reminders), M08.

## Goal

Every calendar you use, from Google and Microsoft accounts, in one agenda that is
read-only, current within minutes, and honest about clashes.

## Design notes

- Read-only scopes only: the calendar list and events. Writing to a calendar is a later
  module with its own consent.
- An organization can refuse a personal app, or require an administrator's approval.
  The first issue is a spike that tests each kind of account before anything else is
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
  is untrusted input everywhere: shown as plain text, never fetched, never interpreted.
- Each calendar feeds exactly one workspace, chosen when it is connected.
- A Google OAuth app left in testing mode loses its tokens every seven days, so the app
  runs in production mode and the unverified-app screen is accepted once.
- The provider's redirect back to the hub arrives from another site, so the strict
  session cookie is not sent with it: the callback page finishes the exchange with a
  request from the hub's own origin.
- The worker process arrives with this module: one more container from the same image,
  with a job queue in PostgreSQL instead of a message broker.

## Issues

- M06-01 [spike] Which accounts can connect -- Done when: a test app asks for read-only calendar access from a personal and an organization account at each provider, and the result, the approval an administrator must give and the fallback for each refusal are written down; runs during Phase 1.
- M06-02 [adr] Calendar access model -- Done when: accepted: read-only scopes, polling with incremental sync, the stored fields, the busy-only level and the fallbacks.
- M06-03 [adr] Background jobs on PostgreSQL -- Done when: accepted: a worker process with a database-backed queue instead of a message broker, with the limits that would change the choice.
- M06-04 [feature] Worker service -- Done when: a worker container runs scheduled and queued jobs with retries, back-off and a heartbeat, joins the Compose stack with the same hardening, and survives a restart without losing or repeating work.
- M06-05 [security] Token vault -- Done when: refresh tokens are encrypted with a key outside the database and its backups, the key can be rotated, tokens never appear in logs or API responses, and a test on a database dump proves it.
- M06-06 [feature] Connect a Google account -- Done when: the authorization-code flow with PKCE, state and an exact redirect address grants the read-only calendar scopes after a step-up check, and the OAuth app is in production mode.
- M06-07 [feature] Connect a Microsoft account -- Done when: the same flow works for organization and personal Microsoft accounts with delegated read-only calendar access.
- M06-08 [feature] ICS subscription -- Done when: a secret calendar address can be added as a read-only source, stored like a token, and fetched by a client that refuses private addresses, redirects to them, large bodies and slow responses.
- M06-09 [feature] Calendar selection and workspace mapping -- Done when: after connecting, the user chooses which calendars sync, the workspace each one feeds and its detail level, and nothing syncs before that.
- M06-10 [feature] Sync engine -- Done when: each calendar syncs incrementally, recovers from an expired sync token with a full resync, backs off on limits, handles moved, cancelled and deleted events, and repeating a sync changes nothing.
- M06-11 [feature] Change notifications -- Done when: provider notifications are validated, trigger an early sync, are renewed before they expire, and losing them only falls back to the polling interval.
- M06-12 [feature] Merged agenda -- Done when: day and week views show every calendar in view with workspace colors, all-day and multi-day events, the right local time for events created in other time zones, and focus mode.
- M06-13 [feature] Clash detection -- Done when: overlapping events from different calendars are marked in the agenda, busy-only events included, and declined events are ignored.
- M06-14 [feature] Join links -- Done when: the meeting link of an event is found and offered as one action in the agenda.
- M06-15 [security] Untrusted event content -- Done when: titles, locations and names render as plain text, the server never fetches a link from an event, and tests cover script, markup and oversized fields.
- M06-16 [security] Disconnect and revoke -- Done when: one action revokes the grant at the provider, deletes the stored tokens and, on request, the synced events; a runbook revokes every account at once and was run once.
- M06-17 [feature] Sync status and alerts -- Done when: the status page shows the last and next sync and the errors per account, and the owner is alerted when an account stops syncing.
- M06-18 [test] Provider contract tests -- Done when: recorded provider responses with made-up data cover paging, expired tokens, throttling and deletions, and a nightly job checks the live APIs with test accounts.

## Measures

- Sync lag from a change at the provider to the agenda, with polling only and with
  change notifications.
- API calls per connected account per day.
