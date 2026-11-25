# P1 - Server runtime

Track: A. Size: L. Depends on: P0. Unlocks: P2, and the public callback addresses M06
needs.

## Goal

A small Linux server that is safe to put on the public internet with private data on it:
a hardened baseline, one way in for users (HTTPS through the proxy), encrypted backups
with a tested restore, and alerts when something stops.

## Scope

- The server baseline as code (Ansible).
- The host firewall, least privilege, and the rules for sharing the host with other
  services.
- The DNS name, TLS and the reverse proxy.
- The Compose stack: web, API and PostgreSQL (the worker joins in M06).
- Secrets, database roles, backups and the restore drill.
- Logs, health checks, an outside heartbeat and runbooks.

## Design notes

- The server is shared with other small services, some of them public. The hub gets its
  own Compose project, network, volumes and system user. It shares no credentials and no
  volumes with anything else, and it never mounts the Docker socket.
- Docker publishes container ports past the host firewall. Every published port binds to
  127.0.0.1, and nginx on the host is the only listener on the public interface.
- nginx sends the API and webhook paths to the API container and everything else to the
  web container, under one hostname, so the web app and the API share an origin.
- The plan assumes no network firewall in front of the server: the host firewall is the
  only filter, and a scan from outside is part of the runbook.
- The baseline runs with Ansible from a developer machine (WSL on Windows). The become
  password is typed, never stored.
- Secrets are generated on the server. The repositories hold names and templates, never
  values.
- The key that encrypts connected-account tokens (M06) lives outside the database volume
  and is backed up separately, so a database dump alone is not enough to use a token.
- Backups are encrypted before they leave the server. A backup that was never restored
  does not count, so the restore drill is part of every release.
- Sign-in is the perimeter, so the proxy is strict: only the paths the app uses, small
  bodies, short timeouts, rate limits, and a switch that closes the service.

## Issues

### work-hub

- P1-01 [spike] Server inventory -- Done when: what runs on the server, which ports listen on which interface, who can become root and which accounts can reach Docker are listed in a private note, and every gap against this plan becomes an issue without host details.
- P1-02 [chore] Ansible baseline -- Done when: one idempotent playbook sets users, SSH (keys only, no root login), automatic security updates, time sync and fail2ban; it runs from WSL with a typed become password, and a second run changes nothing.
- P1-03 [security] Host firewall that holds with Docker -- Done when: inbound traffic is denied by default except SSH, HTTP and HTTPS; every container port binds to 127.0.0.1; a check fails on any compose file that publishes on another address; and a scan from outside shows only those three ports.
- P1-04 [security] Least privilege on the host -- Done when: the hub runs under its own system user, no daily-use account is in the docker group, the deploy agent is the only path that changes the hub's containers, and the sudo rules are documented.
- P1-05 [adr] Sharing the host with other services -- Done when: accepted, covering separate Compose projects, networks, volumes and users, how the other services are kept patched, and what would justify a dedicated server.
- P1-06 [adr] Admin access to the server -- Done when: accepted: whether SSH stays public with keys and bans or moves behind a private network, and how break-glass access works.
- P1-07 [chore] DNS name and TLS certificate -- Done when: the hub has its own hostname, the certificate renews automatically and the renewal was tested, HSTS is on, and a TLS scan shows no weak protocol or cipher.
- P1-08 [security] Reverse proxy rules -- Done when: nginx sends the API and webhook paths to the API and everything else to the web container, caps body size and timeouts, rate-limits the sign-in and API paths, sets `X-Robots-Tag: noindex`, hides versions, and no other virtual host can reach the hub.
- P1-09 [chore] Compose stack: web, API and PostgreSQL -- Done when: images are pinned by digest; containers run as non-root with read-only root filesystems, dropped capabilities and no-new-privileges; resource limits, health checks and log rotation are set; and the network is private to the hub.
- P1-10 [security] Secrets on the server -- Done when: database passwords, session keys, push keys and the token-encryption key are generated on the server, readable only by the hub's user, kept outside the repositories and the database volume, and the rotation runbook was run once.
- P1-11 [security] Database roles -- Done when: a migration role owns the schema; the app role cannot change the schema, bypass row-level security or read another database; and the backup role is read-only.
- P1-12 [chore] Encrypted off-server backups -- Done when: a nightly job dumps the database, encrypts it before upload, stores it off the server with a retention policy, backs up the token key separately, and a failed run raises an alert.
- P1-13 [test] Restore drill -- Done when: a script restores the latest backup into a clean environment, the app starts on it, and the time taken is recorded in `docs/results/`; repeated before every release.
- P1-16 [security] Outside heartbeat -- Done when: a monitor outside the server alerts the owner when the site, the API or a background loop stops, and each alert was triggered once on purpose.
- P1-17 [security] Bans for repeated failures -- Done when: repeated failed sign-ins and path probing ban the source address at the firewall, with a test for the ban and for the release.
- P1-18 [feature] Maintenance switch -- Done when: one command closes sign-in and the API with a clear page, keeps the health endpoint, and is part of the incident runbook.
- P1-19 [docs] Runbooks -- Done when: start and stop, rotate secrets, restore, revoke every session, close the service and rebuild the server from the repository are written, and each was run once.
- P1-20 [adr] Backup target and encryption -- Done when: accepted: where the encrypted backups go, who holds the keys, the retention period, and what a restore needs.

### work-hub-backend

- P1-14 [chore] Structured logs without private content -- Done when: the API and the worker write JSON logs with request IDs, and a test proves that note bodies, event titles, tokens and cookies never reach them.
- P1-15 [feature] Health and status endpoints -- Done when: liveness and readiness endpoints exist, metrics are reachable only from the host, and a status endpoint reports backups and deploys to the owner, and background jobs once the worker exists.

### work-hub-frontend

- P1-21 [feature] Owner status page -- Done when: the owner sees the state of backups and deploys on one page, and of background jobs once the worker exists, fed by the status endpoint.

## Measures

- Restore time from the latest backup.
- Time from stopping a component to the outside alert.
- Ports open from outside (target: SSH, HTTP and HTTPS only).
