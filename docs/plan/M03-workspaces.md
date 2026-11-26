# M03 - Workspaces

Track: B. Phase: 1. Size: L. Depends on: M02. Unlocks: M04, M06.

## Goal

Workspaces that keep work, side projects, personal life and studies apart in the
database itself, with a focus mode that makes one workspace the whole app.

## Design notes

- Every table with user data carries a workspace ID. PostgreSQL row-level security
  decides what a request can see, from two settings the API sets for each transaction:
  the signed-in account and the workspaces in view.
- The app's database role cannot bypass row-level security, and forced policies cover
  the table owner too. A CI check fails when a table with a workspace ID has no policy.
- Connection pooling must not leak the settings from one request to the next: they are
  set for the transaction only, and a test proves that a reused connection starts clean.
- Focus mode narrows the workspaces in view to one. The same policies enforce it, so
  counts, search, notifications and exports cannot show another workspace while it is
  on. It is the mode for sharing a screen, so the web app also drops what it holds of
  the other workspaces when focus turns on.
- Nothing moves between workspaces except by an explicit move, which asks for
  confirmation and is recorded.
- A workspace can be exported, archived or deleted as a whole, for the day a job or a
  project ends.
- Each workspace decides which optional features are on: connected accounts, details in
  notifications, and later agent access and transcripts. Everything optional starts off.
- Accounts and memberships exist from the first migration, although sharing a workspace
  with another account is a later module.

## Tasks

- M03-A [security] Isolation between workspaces -- Done when: on every endpoint a member reads and writes only inside their own workspaces, the database enforces it when the app forgets, and CI fails on a table without a policy or an endpoint without its isolation test. -- Steps: M03-01, M03-03, M03-05, M03-04
- M03-B [feature] Workspaces -- Done when: a person creates, renames, colors, archives and switches workspaces from any screen, and each workspace has its switches for the optional features, off by default. -- Steps: M03-02, M03-12, M03-10
- M03-C [feature] Focus mode -- Done when: one shortcut narrows the whole app to one workspace, the database enforces the limit, and no screen, cache or notification shows another workspace while it is on. -- Steps: M03-06, M03-13
- M03-D [feature] Moves, export and deletion -- Done when: data crosses or leaves a workspace only through an explicit move, an export or a deletion, each sensitive action sits behind the step-up prompt, and each is recorded in an audit log that a member can read. -- Steps: M03-11, M03-07, M03-08, M03-09, M03-14

## Steps

### work-hub

- M03-01 [adr p1 S] Workspace isolation with row-level security -- Done when: accepted, covering the policy model, the per-transaction settings, pooling, the database roles and how tests prove it.

### work-hub-backend

- M03-02 [feature p1 M] Workspaces and memberships -- Done when: an account can create, rename, color and archive workspaces of a kind (work, side project, personal, studies), and a new account starts with a personal workspace.
- M03-03 [security p1 L] Row-level security policies and guard -- Done when: every table with a workspace ID has forced policies for reads and writes, the app role cannot bypass them, and CI fails on a new table without a policy.
- M03-04 [test p1 L] Isolation tests in both directions -- Done when: for every endpoint a member can, and a non-member cannot, read, write or reference a row by ID across workspaces and across accounts, and the suite fails when a new endpoint has no such test.
- M03-05 [test p1 S] Pooled connections start clean -- Done when: a test proves that the workspace settings of one request never apply to the next request on the same connection.
- M03-06 [feature p2 M] Focus mode in the session -- Done when: a session can be narrowed to one workspace and widened again, the database enforces the limit, and every list, count, search and export returns only that workspace while it is on.
- M03-07 [feature p2 M] Moving items between workspaces -- Done when: a move is the only way data crosses a workspace, the request must confirm it explicitly, and it is recorded in the audit log.
- M03-08 [feature p3 M] Workspace export -- Done when: a workspace exports to an archive of JSON and Markdown after a step-up check, and an export of the demo data imports again without loss.
- M03-09 [feature p3 M] Archive and delete a workspace -- Done when: an archived workspace is read-only and hidden; deletion removes its rows after a step-up check and a waiting period; and the runbook says when backups stop containing it.
- M03-10 [feature p2 S] Workspace settings -- Done when: each workspace has switches for the optional features, all off by default, and the API refuses a feature that is off.
- M03-11 [feature p2 M] Audit log -- Done when: exports, moves, deletions, connections and setting changes are recorded per workspace in an append-only table that the app role cannot update or delete, and a member can read it.

### work-hub-frontend

- M03-12 [feature p1 M] Workspace switcher and management -- Done when: the user creates, renames, colors and archives workspaces, and switches between them from any screen with the keyboard or a tap.
- M03-13 [feature p2 M] Focus mode in the app -- Done when: one shortcut turns focus on or off, the app shows clearly that it is on, and no screen, cache or notification keeps data of another workspace while it is on.
- M03-14 [feature p3 M] Workspace settings, export and deletion screens -- Done when: a workspace's switches, export, archive, deletion and audit log are on its settings page, with each sensitive action behind the step-up prompt and a typed confirmation.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2026-12-21 | M03-01, M03-02, M03-03, M03-04, M03-05, M03-06, M03-07, M03-08, M03-09, M03-10, M03-11, M03-12, M03-13, M03-14 |

## Measures

- Endpoints covered by isolation tests, and the number of tests.
- Overhead of row-level security on the Today query.
