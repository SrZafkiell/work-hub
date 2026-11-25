# M01 - App skeleton

Track: B. Size: M. Depends on: P0. Unlocks: M02 and every module after it; P2 (an image
to build).

## Goal

An empty but complete application: a web app you can install, an API with a checked
contract, a real database in tests and a sync-ready data model, so every later module
only adds features.

## Design notes

- One origin: nginx serves the web app and the API under the same hostname, so there is
  no CORS and cookies stay host-only.
- The OpenAPI document is the contract. The TypeScript client is generated from it, and
  CI fails when the committed contract and the code disagree, or when a change breaks
  existing clients.
- Sync-ready conventions from the first migration: UUIDv7 primary keys that a client may
  generate, a version counter and an update time on every row, tombstones instead of
  hard deletes for synced rows, and idempotency keys on writes. The web app does not
  need them yet; the desktop and offline clients will.
- Tests run against a real PostgreSQL, never an in-memory substitute, because row-level
  security and full-text search are part of the behavior.
- The service worker caches the app shell only. Responses with private data are not
  cached on the device in this phase.
- Errors use one format (problem details, RFC 9457) with a request ID that matches the
  logs.

## Issues

- M01-01 [adr] Web app and API architecture -- Done when: accepted: a single-page app and a JSON API on one origin, the OpenAPI contract, and where state lives.
- M01-02 [adr] Sync-ready data conventions -- Done when: accepted: UUIDv7 IDs, version counters, tombstones and idempotency keys, with their cost today and what they enable later.
- M01-03 [feature] API skeleton -- Done when: an app factory, typed settings, database sessions, migrations, problem-details errors and request IDs are in place, and the health endpoints answer.
- M01-04 [feature] Web app shell -- Done when: routing, a layout that works on a phone and on a desktop, light and dark themes from design tokens, empty and error states, and a signed-out page exist.
- M01-05 [ci] API contract check -- Done when: the OpenAPI document is committed, the TypeScript client is generated from it, and CI fails on drift and on breaking changes.
- M01-06 [test] Backend test harness -- Done when: pytest runs against a real PostgreSQL with the migrations applied, factories build demo data, and coverage can only go up.
- M01-07 [test] Web and end-to-end harness -- Done when: unit tests run with Vitest, one Playwright test drives the built app against the API in CI, and traces are kept on failure.
- M01-08 [feature] Installable web app -- Done when: a manifest, icons and a service worker that caches only the app shell pass an installability check in CI, and an update prompt appears when a new version is deployed.
- M01-09 [feature] Accessibility and keyboard baseline -- Done when: automated accessibility checks run in CI with no serious finding, focus is managed on navigation, and a shortcut registry exists for later modules.
- M01-10 [ci] Lint, format and type gates -- Done when: Ruff and a type checker for Python, and ESLint with TypeScript strict mode for the web app, run on every pull request.

## Measures

- Lighthouse performance and accessibility scores of the empty shell.
- Cold start time of the API container.
