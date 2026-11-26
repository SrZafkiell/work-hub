# M02 - Accounts and sign-in

Track: B. Phase: 1. Size: L. Depends on: M01. Unlocks: M03.

## Goal

Only people the owner enrolled can sign in, with a passkey and nothing else, on a
sign-in page that the whole internet can reach.

## Design notes

- No self-registration, and no HTTP endpoint that creates an account. The owner runs the
  admin CLI on the server; it prints a one-time enrollment link.
- Passkeys (WebAuthn) are the only sign-in method: there is no password to guess, reuse
  or phish, and no email reset to hijack. User verification is required.
- An account can hold several passkeys (a phone, a computer, a hardware key). Recovery
  codes are shown once and stored hashed. The last resort is the owner on the server.
- Sessions are rows on the server. The cookie is an opaque ID with the `__Host-` prefix,
  HttpOnly, Secure and SameSite=Strict. Sessions end on idle and absolute timeouts and
  can be listed and revoked.
- Sensitive actions (managing passkeys, connecting an account, exporting or deleting a
  workspace) ask for a fresh passkey check.
- Responses never reveal whether an account exists. Limits apply per address and per
  account, in the proxy and in the app.
- The web image sets the content security policy, because the policy depends on how the
  app is built. The API sets its own headers.
- The identity layer stays replaceable: a later module can add single sign-on through an
  identity provider without changing the session model.

## Tasks

- M02-A [feature] Enrollment -- Done when: the owner creates an account on the server, the person opens the one-time link and registers a passkey on a phone or a computer, and a used or expired link is refused. -- Steps: M02-01, M02-02, M02-03, M02-14
- M02-B [feature] Sign-in and sessions -- Done when: an enrolled person signs in with a passkey on Android and on a desktop, the session ends on its idle and absolute timeouts, and the account page lists and revokes sessions. -- Steps: M02-04, M02-15, M02-05, M02-16
- M02-C [security] Step-up, recovery and security log -- Done when: a sensitive action asks for a fresh passkey check, a lost device is recovered with a single-use code or by the owner on the server, and each of these is in the security log of the account and warns its other devices. -- Steps: M02-08, M02-17, M02-07, M02-11
- M02-D [security] Abuse protection -- Done when: a cross-site request is refused, sign-in and enrollment are throttled without revealing whether an account exists, and the web app is served under an enforced content security policy, each with its test. -- Steps: M02-06, M02-09, M02-10
- M02-E [test] Sign-in proven end to end -- Done when: the end-to-end suite passes on a web image and an API image together, and every procedure of the account runbook was run once. -- Steps: M02-12, M02-13

## Steps

### work-hub

- M02-01 [adr p1 S] Sign-in with passkeys only and owner-provisioned accounts -- Done when: accepted against passwords with one-time codes and against an external identity provider, with the recovery model.
- M02-12 [test p2 M] Sign-in test suite -- Done when: end-to-end tests with virtual authenticators cover enrollment, sign-in, recovery, a replayed challenge, a wrong origin and a revoked session, on a web image and an API image together.
- M02-13 [docs p2 M] Account runbook -- Done when: enrolling, losing a device, losing every passkey and closing an account are documented, and each was run once.

### work-hub-backend

- M02-02 [feature p1 M] Admin CLI for accounts -- Done when: `hubctl` on the server creates, lists and disables accounts, prints enrollment links and revokes sessions; none of it is reachable over HTTP; and every use is logged.
- M02-03 [feature p1 L] Passkey enrollment -- Done when: a single-use link that expires registers a passkey with user verification, a second use or an expired link fails, and an account can add, name and remove passkeys.
- M02-04 [feature p1 M] Passkey sign-in -- Done when: the API verifies a sign-in with a discoverable credential, every challenge is single-use and bound to the hub's origin, and a failure never says why.
- M02-05 [feature p1 M] Server-side sessions -- Done when: the cookie is an opaque host-only ID, idle and absolute timeouts apply, the session ID rotates at sign-in and at step-up, and sessions can be listed and revoked.
- M02-06 [security p1 S] Cross-site request protection -- Done when: state-changing requests require the app's own origin and a token, with tests for cross-site form posts and fetches.
- M02-07 [feature p2 M] Recovery -- Done when: recovery codes are generated at enrollment, returned once, stored hashed and single-use; the owner can re-enroll an account from the CLI; and no email is involved.
- M02-08 [security p2 M] Step-up for sensitive actions -- Done when: the listed actions are refused without a fresh user-verified passkey check, and the check expires after a short window.
- M02-09 [security p1 M] Throttling without account enumeration -- Done when: limits per address and per account apply to every sign-in and enrollment endpoint, responses and timings do not reveal whether an account exists, and both are tested.
- M02-11 [feature p2 M] Security log and alerts -- Done when: sign-ins, failures, new passkeys, recovery code use and admin actions are recorded and returned to the account that owns them, and a new passkey or a recovery raises a warning for every signed-in device (and a notification once M07 exists).

### work-hub-frontend

- M02-10 [security p2 M] Content security policy and headers -- Done when: the web image serves the app with a strict policy without inline scripts, enforced after a report-only period, with frame, referrer and permissions policies, and CI checks them.
- M02-14 [feature p1 M] Enrollment and passkey screens -- Done when: an enrollment link leads through registering a passkey and shows the recovery codes once, a used or expired link gets a clear page, and the account page lists, names, adds and removes passkeys.
- M02-15 [feature p1 L] Sign-in screen -- Done when: sign-in works with a passkey on Android and on a desktop, including signing in on a computer with the phone, and every failure shows the same message.
- M02-16 [feature p2 S] Sessions and security activity -- Done when: the account page lists sessions and recent security events, revokes a session, and shows the warning for a new passkey or a recovery.
- M02-17 [feature p2 S] Step-up prompt -- Done when: a sensitive action asks for the passkey again in place and then continues without losing what the user was doing.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2026-12-21 | M02-01, M02-02, M02-03, M02-04, M02-05, M02-14, M02-15, M02-16 |
| 2026-12-28 | M02-06, M02-07, M02-08, M02-09, M02-10, M02-11, M02-12, M02-13, M02-17 |

## Measures

- Sign-in time with a passkey (median).
- Failed attempts allowed before a ban.
