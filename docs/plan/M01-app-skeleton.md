# M01 - App skeleton

Track: B. Size: M. Depends on: P0. Unlocks: M02 and every module after it; P2 (images to
build).

## Goal

An empty but complete application in two repositories: a web app you can install, an API
with a versioned contract between them, a real database in tests and a sync-ready data
model, so every later module only adds features.

## Design notes

- One origin: nginx serves the web container and the API under the same hostname, so
  there is no CORS and cookies stay host-only.
- The OpenAPI document is the contract and lives in the backend. It is published with
  every backend release. The frontend pins a contract version and generates its
  TypeScript client from it; a newer contract arrives as an automated pull request.
- The backend may not break a published contract: within a major version every change
  is additive, CI compares each change with the last released contract, and the API
  serves the previous version for at least one release.
- The API reports the contract versions it supports. A client that is too old gets a
  clear error and asks the user to update; the same rule will serve the desktop app.
- Sync-ready conventions from the first migration: UUIDv7 primary keys that a client may
  generate, a version counter and an update time on every row, tombstones instead of
  hard deletes for synced rows, and idempotency keys on writes. The web app does not
  need them yet; the desktop and offline clients will.
- Backend tests run against a real PostgreSQL, never an in-memory substitute, because
  row-level security and full-text search are part of the behavior. Frontend tests run
  against the pinned contract. End-to-end tests, in `work-hub`, run a web image and an
  API image together.
- The service worker caches the app shell only. Responses with private data are not
  cached on the device in this phase.
- Errors use one format (problem details, RFC 9457) with a request ID that matches the
  logs.

## Issues

### work-hub

- M01-01 [adr] Web app and API architecture -- Done when: accepted: a single-page app and a JSON API on one origin, the OpenAPI contract, and where state lives.
- M01-02 [adr] Sync-ready data conventions -- Done when: accepted: UUIDv7 IDs, version counters, tombstones and idempotency keys, with their cost today and what they enable later.
- M01-12 [adr] Contract versioning between repositories -- Done when: accepted: how the contract is versioned and published, what counts as a breaking change, how long the API serves an older version, and how a client learns that it is too old.
- M01-14 [test] End-to-end harness -- Done when: one Playwright test drives a web image against an API image and a seeded database in CI, runs on every candidate pair of images, and keeps traces on failure.

### work-hub-backend

- M01-03 [feature] API skeleton -- Done when: an app factory, typed settings, database sessions, migrations, problem-details errors and request IDs are in place, and the health endpoints answer.
- M01-05 [ci] API contract check -- Done when: the OpenAPI document is committed, CI fails on drift between the code and the document and on a breaking change against the last released contract, and every release publishes the contract as a versioned artifact.
- M01-06 [test] Backend test harness -- Done when: pytest runs against a real PostgreSQL with the migrations applied, factories build demo data, and coverage can only go up.
- M01-10 [ci] Lint, format and type gates -- Done when: Ruff and a type checker run on every pull request.
- M01-13 [feature] Version handshake -- Done when: an open endpoint reports the contract versions the API supports, and a request from a client that is too old gets a clear error instead of a failure deep in a call.

### work-hub-frontend

- M01-04 [feature] Web app shell -- Done when: routing, a layout that works on a phone and on a desktop, light and dark themes from design tokens, empty and error states, and a signed-out page exist.
- M01-07 [test] Web test harness -- Done when: unit and component tests run with Vitest against the pinned contract, and coverage can only go up.
- M01-08 [feature] Installable web app -- Done when: a manifest, icons and a service worker that caches only the app shell pass an installability check in CI, an update prompt appears when a new version is deployed, and the app asks the user to update when the API no longer supports its contract.
- M01-09 [feature] Accessibility and keyboard baseline -- Done when: automated accessibility checks run in CI with no serious finding, focus is managed on navigation, and a shortcut registry exists for later modules.
- M01-11 [ci] Generated API client -- Done when: the web app pins a contract version, CI generates the TypeScript client from it and fails on a hand-edited client, and a newer contract arrives as an automated pull request.
- M01-15 [ci] Lint and type gates -- Done when: ESLint and TypeScript strict mode run on every pull request.

## Measures

- Lighthouse performance and accessibility scores of the empty shell.
- Cold start time of the API container.
