# M03 - Workspaces

Track: B. Size: L. Depends on: M02. Unlocks: M04, M06.

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
  on. It is the mode for sharing a screen.
- Nothing moves between workspaces except by an explicit move, which asks for
  confirmation and is recorded.
- A workspace can be exported, archived or deleted as a whole, for the day a job or a
  project ends.
- Each workspace decides which optional features are on: connected accounts, details in
  notifications, and later agent access and transcripts. Everything optional starts off.
- Accounts and memberships exist from the first migration, although sharing a workspace
  with another account is a later module.

## Issues

- M03-01 [adr] Workspace isolation with row-level security -- Done when: accepted, covering the policy model, the per-transaction settings, pooling, the database roles and how tests prove it.
- M03-02 [feature] Workspaces and memberships -- Done when: an account can create, rename, color and archive workspaces of a kind (work, side project, personal, studies), and a new account starts with a personal workspace.
- M03-03 [security] Row-level security policies and guard -- Done when: every table with a workspace ID has forced policies for reads and writes, the app role cannot bypass them, and CI fails on a new table without a policy.
- M03-04 [test] Isolation tests in both directions -- Done when: for every endpoint a member can, and a non-member cannot, read, write or reference a row by ID across workspaces and across accounts, and the suite fails when a new endpoint has no such test.
- M03-05 [test] Pooled connections start clean -- Done when: a test proves that the workspace settings of one request never apply to the next request on the same connection.
- M03-06 [feature] Focus mode -- Done when: one shortcut narrows the session to a workspace, the database enforces the limit, every list, count and search shows only that workspace, and the app shows clearly that focus is on.
- M03-07 [feature] Moving items between workspaces -- Done when: a move is the only way data crosses a workspace, it asks for confirmation, and it is recorded in the audit log.
- M03-08 [feature] Workspace export -- Done when: a workspace exports to an archive of JSON and Markdown after a step-up check, and an export of the demo data imports again without loss.
- M03-09 [feature] Archive and delete a workspace -- Done when: an archived workspace is read-only and hidden; deletion removes its rows after a step-up check and a waiting period; and the runbook says when backups stop containing it.
- M03-10 [feature] Workspace settings -- Done when: each workspace has switches for the optional features, all off by default, and the API refuses a feature that is off.
- M03-11 [feature] Audit log -- Done when: exports, moves, deletions, connections and setting changes are recorded per workspace in an append-only table that the app role cannot update or delete.

## Measures

- Endpoints covered by isolation tests, and the number of tests.
- Overhead of row-level security on the Today query.
