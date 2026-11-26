# P2 - Secure delivery

Track: A. Phase: 1. Size: L. Depends on: P1, M01. Unlocks: the first deploy to the server.

## Goal

Every image that runs on the server was built by CI from a reviewed commit, scanned,
signed and verified before it started, the pair of images was tested together, and a bad
release rolls back by itself.

## Scope

- Image builds, SBOMs, scans, signatures and build provenance, in both code
  repositories.
- The release manifest, the deploy agent on the server and the release workflow.
- Rollback and the migration rules that make it possible.
- The slow gates: DAST and performance budgets.

## Design notes

- Build once on `main` in each code repository; a release promotes the same digests that
  were tested.
- Building, scanning and signing are one reusable workflow in `work-hub`, called by the
  backend and the frontend. The signature names that workflow and the repository that
  called it, so verification checks both: who built it, and from which source.
- A product release is a signed manifest in `work-hub` that pins one backend digest and
  one frontend digest. The pair must have passed the end-to-end tests together. Either
  side can be rolled back alone, because the API serves the previous contract version.
- CI runs on GitHub-hosted runners and holds no credential for the server. The server
  polls for a newer manifest, verifies its signature, then the signature and provenance
  of each image, and pulls by digest.
- The deploy agent is a small script on a systemd timer that uses cosign and Docker
  Compose. It is the only thing on the host allowed to change the hub's containers.
- Migrations follow expand and contract. A release that migrates takes a backup first;
  rolling back across a contract step means a restore.
- The rule covers the whole host, not only the hub: a deploy key for any service on the
  same server is a path from CI to the hub's data.
- Fast gates block the merge. Slow gates (DAST, load tests) run nightly and block the
  promotion to a release.
- The signer identity includes repository names, so the names are settled before the
  first signed build, and verification also checks the repository IDs.

## Tasks

- P2-A [ci] Trusted images -- Done when: every merge to main in either code repository produces one image with an SBOM, a scan without critical or high findings, a keyless signature and provenance that verification ties to its workflow and its repository. -- Steps: P2-04, P2-01, P2-15, P2-02, P2-03
- P2-B [ci] Releases -- Done when: a tag created by the owner tests a pair of image digests end to end and publishes a signed manifest that pins both, and a migration that drops or rewrites without its expand step cannot reach a release. -- Steps: P2-16, P2-10, P2-08, P2-09
- P2-C [feature] Pull-based deploys -- Done when: the server installs a signed release by itself, refuses an unsigned one, returns to the previous release when the health check fails, and no CI system holds a credential for it; merge-to-running and rollback times are on record. -- Steps: P2-05, P2-06, P2-07, P2-13, P2-14
- P2-D [ci] DAST and performance budgets -- Done when: a medium or higher DAST finding or an API p95 regression blocks the promotion to a release, and a web bundle over its budget fails its pull request. -- Steps: P2-11, P2-12, P2-17

## Steps

### work-hub

- P2-02 [ci p1 M] SBOM and image scan -- Done when: the reusable build workflow gives every image an SBOM and fails on critical or high findings, every exception carries an expiry date, and both code repositories use it.
- P2-03 [ci p1 M] Signing and provenance -- Done when: the reusable build workflow signs images keyless, attests build provenance, and verification checks the building workflow, the calling repository's ID and its name.
- P2-04 [adr p2 S] Build once, promote digests -- Done when: accepted.
- P2-05 [adr p2 S] Deploy agent and its access to Docker -- Done when: accepted, covering the polling model, what is verified, the agent's permissions, and why no CI system connects to the server.
- P2-06 [feature p1 L] Deploy agent -- Done when: a timer on the server reads the release manifest, verifies its signature and the signature and provenance of each image, pulls by digest, takes a backup when the release migrates, restarts the stack, and refuses an unsigned image or manifest in a test.
- P2-07 [feature p1 L] Health-checked rollout and rollback -- Done when: a deploy that fails its health check returns to the previous manifest by itself and alerts the owner, and the drill is recorded.
- P2-08 [adr p2 S] Database migrations -- Done when: accepted: expand and contract, a backup before every migrating release, and what rollback means across each step.
- P2-10 [ci p1 L] Release workflow -- Done when: a tag created by the owner here runs the end-to-end tests on a backend digest and a frontend digest, and on success publishes a release with the signed manifest that pins both, notes and the SBOMs.
- P2-11 [ci p2 M] Nightly DAST -- Done when: OWASP ZAP runs nightly against a stack started in CI from the latest images with demo data, including the signed-in pages, and a medium or higher finding blocks promotion.
- P2-13 [security p1 S] No CI credential for the server -- Done when: every service on the host deploys by pull and verify, no SSH deploy key for the host exists in any CI system, and the check is part of the release checklist.
- P2-14 [test p2 M] Delivery drill -- Done when: merge-to-running time and rollback time are measured on the server and recorded in `docs/results/`.
- P2-16 [adr p2 S] Release manifest that pins a tested pair of images -- Done when: accepted: what the manifest holds, how it is signed, how a pair is tested before it is pinned, and how either side rolls back alone.

### work-hub-backend

- P2-01 [ci p1 M] Build the API image once on main -- Done when: a multi-stage build produces the API image on a minimal pinned base through the reusable workflow, with the registry path lowercased, and the same digest is used from test to release.
- P2-09 [ci p2 M] Migration checks -- Done when: CI applies every migration to an empty database and to the schema of the previous release, and fails on a migration that drops or rewrites without its expand step.
- P2-12 [ci p3 M] API performance budget -- Done when: a nightly k6 run on seeded demo data checks API p95 against a recorded baseline with an absolute limit and a regression limit, and a failure blocks promotion.

### work-hub-frontend

- P2-15 [ci p1 M] Build the web image once on main -- Done when: a multi-stage build produces an image of static files on a minimal pinned base through the reusable workflow, with the registry path lowercased, and the same digest is used from test to release.
- P2-17 [ci p3 S] Web bundle budget -- Done when: a pull request fails when the entry bundle grows past its budget, and the budget only moves in its own pull request.

## Schedule

Planned weeks. Each step starts on the Monday shown and is due that Sunday; a task runs
from its first step to its last, and the module's epic and its milestone end with the
last week. Dates change here first, and the sync script moves the board.

| Week of | Steps |
|---|---|
| 2027-01-04 | P2-04 |
| 2027-01-11 | P2-01, P2-02, P2-03, P2-05, P2-08, P2-09, P2-15, P2-16 |
| 2027-01-18 | P2-10 |
| 2027-01-25 | P2-06, P2-07, P2-11, P2-12, P2-13, P2-14, P2-17 |

## Measures

- Merge-to-running time and rollback time.
- Critical and high CVEs in released images (target 0).
- Medium or higher DAST findings (target 0).
