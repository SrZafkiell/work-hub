# P2 - Secure delivery

Track: A. Size: L. Depends on: P1, M01. Unlocks: the first deploy to the server.

## Goal

Every image that runs on the server was built by CI from a reviewed commit, scanned,
signed and verified before it started, and a bad release rolls back by itself.

## Scope

- Image builds, SBOMs, scans, signatures and build provenance.
- The deploy agent on the server and the release workflow.
- Rollback and the migration rules that make it possible.
- The slow gates: DAST and performance budgets.

## Design notes

- Build once on `main`; a release promotes the same digest that was tested.
- CI runs on GitHub-hosted runners and holds no credential for the server. The server
  polls for a newer release manifest, verifies the signature and the provenance
  (repository ID, workflow and branch), then pulls by digest.
- The deploy agent is a small script on a systemd timer that uses cosign and Docker
  Compose. It is the only thing on the host allowed to change the hub's containers.
- Migrations follow expand and contract. A release that migrates takes a backup first;
  rolling back across a contract step means a restore.
- The rule covers the whole host, not only the hub: a deploy key for any service on the
  same server is a path from CI to the hub's data.
- Fast gates block the merge. Slow gates (DAST, load tests) run nightly and block the
  promotion to a release.
- The signer identity includes the repository name, so the name is settled before the
  first signed build, and verification also checks the repository ID.

## Issues

- P2-01 [ci] Build images once on main -- Done when: a multi-stage build produces the API image with the web app inside, on a minimal pinned base, with the registry path lowercased, and the same digest is used from test to release.
- P2-02 [ci] SBOM and image scan -- Done when: every image gets an SBOM, a scan fails the build on critical or high findings, and every exception carries an expiry date.
- P2-03 [ci] Signing and provenance -- Done when: images are signed keyless with the workflow identity, build provenance is attested, and verification checks the repository ID as well as its name.
- P2-04 [adr] Build once, promote digests -- Done when: accepted.
- P2-05 [adr] Deploy agent and its access to Docker -- Done when: accepted, covering the polling model, what is verified, the agent's permissions, and why no CI system connects to the server.
- P2-06 [feature] Deploy agent -- Done when: a timer on the server reads the release manifest, verifies the signature and the provenance, pulls by digest, takes a backup when the release migrates, restarts the stack, and refuses an unsigned image in a test.
- P2-07 [feature] Health-checked rollout and rollback -- Done when: a deploy that fails its health check returns to the previous digest by itself and alerts the owner, and the drill is recorded.
- P2-08 [adr] Database migrations -- Done when: accepted: expand and contract, a backup before every migrating release, and what rollback means across each step.
- P2-09 [ci] Migration checks -- Done when: CI applies every migration to an empty database and to the schema of the previous release, and fails on a migration that drops or rewrites without its expand step.
- P2-10 [ci] Release workflow -- Done when: a tag created by the owner produces a GitHub release with notes, SBOMs, signatures and the manifest the agent reads.
- P2-11 [ci] Nightly DAST -- Done when: OWASP ZAP runs nightly against a stack started in CI with demo data, including the signed-in pages, and a medium or higher finding blocks promotion.
- P2-12 [ci] Performance budgets -- Done when: a k6 run on seeded demo data checks API p95 against a recorded baseline with an absolute limit and a regression limit, and the web bundle has a size budget on every pull request.
- P2-13 [security] No CI credential for the server -- Done when: every service on the host deploys by pull and verify, no SSH deploy key for the host exists in any CI system, and the check is part of the release checklist.
- P2-14 [test] Delivery drill -- Done when: merge-to-running time and rollback time are measured on the server and recorded in `docs/results/`.

## Measures

- Merge-to-running time and rollback time.
- Critical and high CVEs in released images (target 0).
- Medium or higher DAST findings (target 0).
