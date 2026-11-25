# P0 - Foundation

Track: A. Phase: 1. Size: M. Depends on: nothing. Unlocks: everything.

## Goal

Repositories that are safe to build in public from day one: the same rules, templates,
decisions, threat model and CI security gates in every one of them before the first
line of product code.

## Scope

- Repository settings, governance files and rulesets, in every repository.
- Project management: labels, milestones, one public project board across the
  repositories, and the plan-to-issues sync.
- The ADR process and the first ADRs.
- Threat model v1 for a service on the public internet.
- CI security gates as reusable workflows.
- Developer tooling that works on Windows and Linux.
- The demo data set, and the guard that keeps real data out of the repositories.

## Design notes

- One rule, one issue: an issue here covers every repository, and it is done only when
  `work-hub`, `work-hub-backend` and `work-hub-frontend` all comply. `work-hub-desktop`
  joins when its module starts.
- The CI gates are reusable workflows in this repository. The others call them pinned by
  commit SHA, so a gate is fixed in one place and no repository drifts.
- Merge commits, not rebase merges: GitHub rewrites rebased commits without signature
  verification, which conflicts with required signed commits; squash merges would lose
  the per-concern commits.
- Git for Windows converts LF to CRLF on checkout by default; `.gitattributes` keeps
  every text file LF except PowerShell scripts.
- When it runs, the app holds private notes and calendars. The repositories must never
  hold any: fixtures, screenshots, issues and test recordings use the demo data set
  only, and a CI guard backs the rule.
- The source is public while the service is on the internet. Nothing in the design may
  depend on the code being secret; the threat model says so explicitly.

## Issues

### work-hub

- P0-01 [chore p2] Repository files: LICENSE, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CODEOWNERS -- Done when: every repository has them under the same license, and each SECURITY.md points to GitHub private vulnerability reporting.
- P0-02 [chore p2] .gitattributes and .gitignore -- Done when: in every repository LF is enforced for every text file except PowerShell scripts, binaries are marked, keys, .env files, database dumps and build output are ignored, and a fresh checkout on Windows with autocrlf=true keeps LF.
- P0-03 [security p1] Repository security settings -- Done when: in every repository private vulnerability reporting, secret scanning with push protection and Dependabot alerts are on; the default Actions token is read-only; and workflows from fork pull requests need approval.
- P0-04 [chore p1] Commit signing -- Done when: an SSH signing key is registered on GitHub, git signs every commit, and commits show as Verified.
- P0-05 [security p1] Rulesets for main and release tags -- Done when: in every repository main requires pull requests, required status checks and signed commits, allows merge commits only, and blocks force pushes and deletion; only the owner can create or delete v* tags; enabled after P0-04.
- P0-06 [adr p2] Merge strategy and signed commits -- Done when: accepted, explaining why rebase and squash merges are not used.
- P0-07 [chore p2] Labels, milestones and public project board -- Done when: the type, area, priority and phase labels and the milestones with their due dates exist in every repository that has issues for them, and one public project lists every issue of every repository under its module's epic, with an assignee, a priority, a phase, a track and start and target dates, and with the saved views of docs/BOARD.md.
- P0-08 [chore p2] Plan-to-issues sync script -- Done when: it reads docs/plan/*.md, creates or updates each issue by plan ID in the repository named by its heading, moves an issue whose heading changed, keeps one epic per module as the parent of its issues, sets assignees, labels, milestones and the board's priority, phase, track and date fields, paces requests under GitHub's secondary rate limits, and resumes after a failure.
- P0-09 [chore p3] Issue and pull request templates -- Done when: every repository has feature, bug, spike and ADR issue templates, plus a pull request template with the definition-of-done checklist.
- P0-10 [adr p2] Record architecture decisions -- Done when: a template in `docs/adr/` and an index that CI keeps current, and the other repositories link to it instead of keeping their own records.
- P0-11 [adr p2] Public service with owner-provisioned accounts -- Done when: accepted, with the alternative considered (a private network in front of the app) and what the choice demands from sign-in, the proxy and monitoring.
- P0-12 [adr p2] Stack: FastAPI, PostgreSQL, React and TypeScript -- Done when: accepted, with the alternatives considered and the reasons: row-level security, full-text search in two languages, one contract for web and desktop clients.
- P0-13 [adr p2] Web app first, desktop app later on the same API -- Done when: accepted, with what the web app must respect now so that a desktop client with offline sync can follow.
- P0-14 [adr p2] Pull-based signed delivery -- Done when: accepted, with the threat it removes: no CI system holds a credential for the server.
- P0-15 [security p1] Threat model v1 -- Done when: `docs/threat-model/` has the system context, trust boundaries, data flows and a STRIDE table for the public sign-in, the workspace walls, connected accounts and the CI/CD path across the repositories, linked to RISKS.md, with an issue for every open risk.
- P0-16 [ci p1] CI skeleton -- Done when: reusable workflows here run actionlint, zizmor, gitleaks, an ASCII guard, a Conventional Commits check and dependency review; every repository calls them on every pull request, pinned by commit SHA; every action is pinned by commit SHA; workflow permissions default to read-only; no workflow uses pull_request_target, and untrusted input never reaches a run step directly.
- P0-17 [ci p2] Code scanning -- Done when: CodeQL and Semgrep run on pull requests and weekly in the backend (Python) and in the frontend (TypeScript), each enabled when its first code lands.
- P0-18 [ci p3] OpenSSF Scorecard -- Done when: a weekly run in every repository publishes results to code scanning and a README badge, and the README notes the checks a new single-maintainer repository cannot pass yet.
- P0-19 [ci p2] Dependabot -- Done when: in every repository action SHAs, image digests and the Python or npm dependencies it has get grouped weekly pull requests.
- P0-20 [ci p3] License check -- Done when: dependency licenses are checked against an allow list in the CI of the backend and of the frontend, and third-party notices are generated.
- P0-21 [ci p3] Runner hardening -- Done when: StepSecurity harden-runner runs on every job of every repository, first in audit mode, then blocking with an egress allow list.
- P0-22 [chore p1] Developer tooling -- Done when: each repository has a Taskfile with lint and test tasks and pre-commit hooks for formatting and gitleaks that work on Windows and Linux, and `task up` here starts the whole stack on a developer machine from local checkouts of the backend and the frontend.
- P0-24 [security p1] Real-data guard -- Done when: CONTRIBUTING states that issues, fixtures, screenshots and logs never contain real names, calendars or notes, and a shared CI check fails in every repository on email addresses outside the documented example domains.
- P0-25 [adr p2] Separate repositories with a home repository -- Done when: accepted: one repository per part (backend, frontend, desktop) and this one for the plan, the server and the releases, with the costs (rules and CI in every repository, a versioned contract) and how each is handled.

### work-hub-backend

- P0-23 [chore p2] Demo data set -- Done when: a seed command creates one made-up company workspace and personal workspaces with made-up people, tasks, notes and events, and it is the only data used in fixtures, screenshots and recordings in any repository.

## Schedule

Planned weeks. Each issue starts on the Monday shown and is due that Sunday; the module's
epic and its milestone end with the last week. Dates change here first, and the sync
script moves the board.

| Week of | Issues |
|---|---|
| 2026-11-30 | P0-01, P0-02, P0-03, P0-04, P0-05, P0-06, P0-07, P0-08, P0-09, P0-10, P0-11, P0-12, P0-13, P0-14, P0-15, P0-16, P0-17, P0-18, P0-19, P0-20, P0-21, P0-22, P0-23, P0-24, P0-25 |

## Measures

- OpenSSF Scorecard score of each repository at the end of P0 (baseline, with the known
  caps noted).
