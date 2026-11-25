# M05 - Notes and search

Track: B. Phase: 1. Size: M. Depends on: M04. Unlocks: M08.

## Goal

Notes that stay connected to the work they belong to, and one search box that finds
anything in view, in English or Spanish.

## Design notes

- Notes are Markdown, per workspace, saved automatically with the version counter, so
  two devices cannot silently overwrite each other.
- Links connect notes and tasks (later meetings and people); each side shows what links
  to it.
- Markdown is rendered in the web app and is untrusted: HTML is sanitized, scripts never
  run, remote images are not loaded (they would reveal that a note was opened), and
  links open without a referrer.
- Search uses PostgreSQL full-text search with English and Spanish configurations and
  accent-insensitive matching. It runs under the same row-level security, so it cannot
  return another workspace or ignore focus mode.
- No file attachments in this phase: files bring storage, scanning and quota questions
  that are not needed yet.

## Issues

### work-hub-backend

- M05-01 [feature p1] Notes -- Done when: Markdown notes can be created, pinned, tagged and updated with the version counter, and a stale update is refused with the current version in the answer.
- M05-02 [feature p2] Links and backlinks -- Done when: a note and a task can be linked from either side inside one workspace, and each returns what links to it.
- M05-04 [feature p1] Full-text search -- Done when: one query searches tasks and notes in English and Spanish, ignores accents, ranks by relevance and recency, and filters by workspace, kind and date.
- M05-05 [test p1] Search respects the walls -- Done when: tests prove that search never returns rows outside the workspaces in view, with and without focus mode.
- M05-07 [test p3] Search quality and budget -- Done when: fixture queries in both languages return the expected items, and a p95 budget from a measured baseline is enforced in CI.

### work-hub-frontend

- M05-03 [security p1] Safe Markdown rendering -- Done when: a corpus of script, HTML and link attacks renders harmlessly, remote images are blocked by the content security policy, and the test runs in CI.
- M05-06 [feature p2] Command palette -- Done when: one shortcut opens a palette that searches, jumps to a workspace or an item, and creates a task or a note.
- M05-08 [feature p1] Note editor -- Done when: a note is edited as Markdown with a preview and autosave, and a stale save offers a merge instead of overwriting.
- M05-09 [feature p2] Links and backlinks in the app -- Done when: a note and a task are linked from either side with a picker, and each shows what links to it.

## Schedule

Planned weeks. Each issue starts on the Monday shown and is due that Sunday; the module's
epic and its milestone end with the last week. Dates change here first, and the sync
script moves the board.

| Week of | Issues |
|---|---|
| 2027-01-04 | M05-01, M05-02, M05-03, M05-04, M05-05, M05-06, M05-07, M05-08, M05-09 |

## Measures

- Search p95 on seeded data.
- Fixture queries answered correctly, per language.
