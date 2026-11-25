# work-hub

One place for your work and your personal projects: tasks, meetings, notes and all your
calendars, kept in separate workspaces.

work-hub is a self-hosted web app. You install it on your phone and your computer, sign
in with a passkey, and see what matters today across your workspaces. A wall stands
between them: focus mode shows one workspace only, so sharing your screen never shows
the rest.

> Status: planning. See [the plan](docs/PLAN.md); work is tracked in issues, milestones
> and one [project board](https://github.com/users/SrZafkiell/projects/2) across the
> repositories.

## Repositories

| Repository | What it holds |
|---|---|
| work-hub (this one) | The plan, decisions and risk register; the server setup, the deploy agent and the release manifests; end-to-end tests; the shared CI workflows |
| [work-hub-backend](https://github.com/SrZafkiell/work-hub-backend) | The FastAPI application, the worker, the admin CLI and the OpenAPI contract |
| [work-hub-frontend](https://github.com/SrZafkiell/work-hub-frontend) | The React and TypeScript web app |
| [work-hub-desktop](https://github.com/SrZafkiell/work-hub-desktop) | The desktop app, planned as a later module |

The contract published by the backend is the only coupling between them. A release of
the product is a signed manifest here that pins a backend image and a frontend image
that were tested together.

## Modules

| Area | Module | What it does |
|---|---|---|
| Core | M01 App skeleton | An installable web app, an API with a versioned contract, a real database in tests |
| Core | M02 Accounts and sign-in | Passkeys only; the owner creates every account, there is no sign-up page |
| Core | M03 Workspaces | Work, side projects, personal and studies, kept apart by the database, with a focus mode |
| Core | M04 Tasks | Quick add, a Today view across workspaces, follow-ups for what others owe you |
| Core | M05 Notes and search | Markdown notes linked to tasks; one search in English and Spanish |
| Schedule | M06 Calendars | Google and Microsoft calendars in one read-only agenda, with clash detection |
| Schedule | M07 Reminders | Notifications on phone and computer, a morning digest, and a check that reminders still arrive |
| Schedule | M08 Meetings | Notes on any event: agenda, decisions and action items that become tasks |

Platform work: P0 foundation, P1 server runtime and P2 secure delivery (signed images,
pull-based deploys).

Planned after these: people and 1:1s, weekly reports, tasks from other trackers, iPhone
support, a desktop app with offline sync, meeting transcripts, access for AI agents and
shared workspaces. See [later modules](docs/PLAN.md#later-modules).

## How it runs

- FastAPI, PostgreSQL, React and TypeScript, on one small Linux server with Docker
  Compose.
- The app is on the public internet, so sign-in is the perimeter: passkeys only, no
  self-registration, rate limits, bans and alerts.
- PostgreSQL row-level security keeps every workspace apart, below the application code.
- Connected calendar accounts are read-only, and their tokens are encrypted with a key
  that is not in the database.
- CI builds, scans and signs every image. The server pulls and verifies; no CI system
  holds a credential for the server.

## Engineering standards

- The plan is kept as files and synced to GitHub: every issue has an epic, an owner, a
  priority and a planned week on a public project board with a roadmap
  ([how to read it](docs/BOARD.md)); every change goes through a pull request, in every
  repository.
- CI security gates shared by the repositories: secret scanning, CodeQL, Semgrep,
  dependency review, image scanning, DAST, OpenSSF Scorecard.
- Signed commits; signed images with an SBOM and build provenance.
- An architecture decision record for every significant decision, a threat model and a
  [risk register](docs/RISKS.md).
- Numbers come from tests and scripts, recorded with hardware and versions.
- Demo data only: fixtures and screenshots use a made-up company and made-up people.

## License

Apache-2.0. See [LICENSE](LICENSE).
