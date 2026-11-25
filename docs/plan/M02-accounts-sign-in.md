# M02 - Accounts and sign-in

Track: B. Size: L. Depends on: M01. Unlocks: M03.

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
- The identity layer stays replaceable: a later module can add single sign-on through an
  identity provider without changing the session model.

## Issues

- M02-01 [adr] Sign-in with passkeys only and owner-provisioned accounts -- Done when: accepted against passwords with one-time codes and against an external identity provider, with the recovery model.
- M02-02 [feature] Admin CLI for accounts -- Done when: `hubctl` on the server creates, lists and disables accounts, prints enrollment links and revokes sessions; none of it is reachable over HTTP; and every use is logged.
- M02-03 [feature] Passkey enrollment -- Done when: a single-use link that expires registers a passkey with user verification, a second use or an expired link fails, and an account can add and name more passkeys.
- M02-04 [feature] Passkey sign-in -- Done when: sign-in works with a discoverable credential on Android and on a desktop, including signing in on a computer with the phone, and every challenge is single-use.
- M02-05 [feature] Server-side sessions -- Done when: the cookie is an opaque host-only ID, idle and absolute timeouts apply, the session ID rotates at sign-in and at step-up, and a user can list and revoke sessions.
- M02-06 [security] Cross-site request protection -- Done when: state-changing requests require the app's own origin and a token, with tests for cross-site form posts and fetches.
- M02-07 [feature] Recovery -- Done when: recovery codes are generated at enrollment, shown once, stored hashed and single-use; the owner can re-enroll an account from the CLI; and no email is involved.
- M02-08 [security] Step-up for sensitive actions -- Done when: a fresh user-verified passkey check is required for the listed actions and expires after a short window.
- M02-09 [security] Throttling without account enumeration -- Done when: limits per address and per account apply to every sign-in and enrollment endpoint, responses and timings do not reveal whether an account exists, and both are tested.
- M02-10 [security] Content security policy and headers -- Done when: a strict policy without inline scripts is enforced after a report-only period, with frame, referrer and permissions policies, and CI checks them.
- M02-11 [feature] Security log and alerts -- Done when: sign-ins, failures, new passkeys, recovery code use and admin actions are recorded, the user sees recent activity, and a new passkey or a recovery shows a warning on every signed-in device (and sends a notification once M07 exists).
- M02-12 [test] Sign-in test suite -- Done when: Playwright with virtual authenticators covers enrollment, sign-in, recovery, a replayed challenge, a wrong origin and a revoked session.
- M02-13 [docs] Account runbook -- Done when: enrolling, losing a device, losing every passkey and closing an account are documented, and each was run once.

## Measures

- Sign-in time with a passkey (median).
- Failed attempts allowed before a ban.
