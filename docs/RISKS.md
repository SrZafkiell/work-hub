# Risks and constraints

Known constraints of running a personal work hub on one small server on the public
internet, and how the plan handles each one. The list is reviewed at the end of every
milestone; the issue IDs point to the plan files in [plan/](plan/).

## Exposure

| Risk | Effect | Mitigation | Where |
|---|---|---|---|
| The sign-in page is on the public internet | Anyone can attack it | Passkeys only, so there is nothing to guess or phish; no self-registration and no HTTP endpoint that creates an account; limits in the proxy and in the app; bans after repeated failures; alerts on new devices | M02-02, M02-04, M02-09, M02-11, P1-08, P1-17 |
| The source code is public | Attackers can study it | Nothing depends on the code being secret: threat model, scanners in CI, nightly DAST, dependency updates, private vulnerability reporting | P0-03, P0-15, P0-16, P0-17, P2-11 |
| A flaw in the app or in a dependency | Every workspace could leak at once | Row-level security below the application code, a database role that cannot bypass it, containers without privileges, a small public surface, image scans on every build | M03-03, P1-09, P1-11, P2-02 |
| A stolen session (script injection, a copied cookie) | Access without the passkey | A strict content security policy, sanitized Markdown, host-only HttpOnly cookies, short timeouts, a fresh passkey check for sensitive actions, sessions that can be listed and revoked | M02-05, M02-08, M02-10, M05-03 |
| The server also runs other services, some of them public | A compromise of one could reach the hub | Separate Compose projects, networks, volumes and users; loopback-only ports; no shared credentials; no Docker socket in any container of the hub | P1-04, P1-05, P1-09 |
| Docker publishes ports past the host firewall | A container port becomes public by accident | Every port binds to 127.0.0.1, a check on compose files, a scan from outside | P1-03 |
| No network firewall in front of the server | Any listening port is public | The host firewall denies by default; the outside scan is part of the runbook | P1-03 |
| The hostname appears in certificate transparency logs | The service is easy to find | Accepted: nothing relies on the name being unknown, and the name says nothing about the content | P1-07 |
| Every passkey of an account is lost | The account is locked out | Several passkeys per account, recovery codes, re-enrollment by the owner on the server | M02-03, M02-07 |
| Passkeys are bound to the hostname | Changing the hostname invalidates every passkey | The hostname is settled before the first enrollment; after a change, accounts are re-enrolled from the server | P1-07, M02-07 |

## Data that belongs to others

| Risk | Effect | Mitigation | Where |
|---|---|---|---|
| Work calendars and notes on a personal server | It may conflict with your organization's policy or with a contract | Check the policy before connecting an account; connected accounts are off by default; a workspace can be exported, archived or deleted when a job or a project ends | M03-08, M03-09, M03-10, M06-01 |
| An organization refuses a personal app | The calendar cannot be connected | A spike per provider before anything is built; fallbacks: an administrator's approval, an ICS subscription, sharing the calendar with a personal account | M06-01, M06-08 |
| Connected-account tokens are the most valuable data on the server | A database leak would give access to calendars | Read-only scopes, encryption with a key outside the database and its backups, revocation in one step, a runbook that revokes everything | M06-05, M06-16 |
| Google disconnects apps in testing mode after seven days | Sync stops every week | The OAuth app runs in production mode; the unverified-app screen is accepted once | M06-06 |
| Event text is written by other people, including strangers | Malicious markup or links in an invitation | Plain text only, markup stripped, the server never fetches a link from an event | M06-15 |
| A subscription address or a webhook is used to reach internal addresses | The server makes requests for an attacker | The fetcher refuses private addresses and redirects to them; notifications are validated | M06-08, M06-11 |
| Notes about people | The most sensitive content in the app | Workspace walls, focus mode, export and deletion, no third-party processing | M03-03, M03-06, M03-09 |
| Recording and transcribing meetings (later modules) | Consent and legal exposure | Off by default, consent recorded per meeting, processing on your own machine | Later modules |
| Private content in logs or error reports | Notes and titles leak into files with weaker protection | Structured logs with a test that proves bodies, titles, tokens and cookies never appear | P1-14 |

## Reminders

| Risk | Effect | Mitigation | Where |
|---|---|---|---|
| Push delivery fails silently (expired subscription, battery saver, server down) | A missed appointment | An outside heartbeat on the reminder loop, cleanup and an alert when a subscription dies, a test on a real phone, the morning digest as a second chance | M07-06, M07-08, M07-09 |
| Polling delay | A last-minute change arrives late | Short polling intervals, change notifications that trigger an early sync | M06-10, M06-11 |
| Time zones and daylight saving in other countries | A reminder at the wrong time | Times in UTC with the event's zone, recurrences expanded by the provider, tests across daylight-saving changes | M06-12, M07-04 |
| Notifications on a locked or shared screen | A title is seen by the wrong person | Details can be hidden per workspace; focus mode silences the other workspaces | M07-07 |
| iOS delivers Web Push only to an installed app | No reminders on an iPhone at first | Android is the first target; iPhone support is a later module | Later modules |

## Delivery and operations

| Risk | Effect | Mitigation | Where |
|---|---|---|---|
| A CI system holds a key to the server | Whoever compromises CI reaches the data | Pull-based delivery for every service on the host; no deploy key exists | P2-06, P2-13 |
| Migrations cannot be undone | A bad release damages data | Expand-and-contract migrations, a backup before every migrating release, a rollback drill | P2-07, P2-08, P2-09 |
| One server | An outage stops the service; a lost disk loses the data | Encrypted off-server backups, a restore drill with a measured time, an outside alert | P1-12, P1-13, P1-16 |
| Backups hold everything | A leaked backup exposes every workspace | Encryption before upload, the token key backed up separately | P1-12 |
| A deleted workspace survives in backups | Data outlives its deletion | The retention period is documented, and the runbook says when backups stop containing it | M03-09, P1-12 |
| Single maintainer | Reviews are self-reviews | Required checks, signed commits and scanners; the cap is noted in the Scorecard results | P0-05, P0-18 |
| Signer identity tied to the repository name | A rename breaks verification; a re-created name could pass a name-only check | The name is settled before the first signed build; verification also checks the repository ID | P2-03 |
| Rebase merges create commits without signature verification | Required signed commits and per-concern commits conflict | Merge commits: branch commits are signed by the author, merge commits by GitHub | P0-05, P0-06 |
| Public repository: untrusted pull requests | Secrets or runners exposed | GitHub-hosted runners only; no `pull_request_target`; actionlint and zizmor; secrets only in jobs on `main` | P0-16 |
| Git for Windows converts LF to CRLF on checkout by default | Shell scripts and configs break on the server | `.gitattributes` forces LF (CRLF only for PowerShell scripts) | P0-02 |
| Real data reaches the repository | Private notes or names become public for good | Demo data only, a CI guard on email addresses, secret scanning with push protection | P0-03, P0-23, P0-24 |

## Sync and offline (later)

| Risk | Effect | Mitigation | Where |
|---|---|---|---|
| Offline edits conflict when a desktop client arrives | Lost updates | Version counters and tombstones from the first migration; conflict rules decided with the desktop module | M01-02 |
| Private data cached on a device | A lost phone exposes notes | Only the app shell is cached in the first phases; device storage is decided with the offline module | M01-08 |
