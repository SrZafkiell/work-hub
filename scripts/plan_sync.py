#!/usr/bin/env python3
"""Sync the plan files to GitHub: labels, milestones, issues and the project board.

docs/plan/*.md in this repository is the source of truth for every repository of the
project. Each issue line has the form

    - <ID> [type] Title -- Done when: ...

and sits under a heading that names the repository it belongs to:

    ### work-hub-backend

The script creates or updates one GitHub issue per line, in that repository, matched by
the plan ID kept in a hidden marker in the issue body, so it can be re-run at any time
and resumes after a failure. An issue whose line moved under another heading is
transferred to that repository. Titles, bodies, milestones and the type and area labels
are managed here; discussion belongs in issue comments, and labels added by hand are
kept.

It is a dry run unless --apply is given. Writes are paced and retried with back-off to
stay under GitHub's secondary rate limits for content creation.

Usage:
    python scripts/plan_sync.py --check            # parse and validate only
    python scripts/plan_sync.py                    # dry run
    python scripts/plan_sync.py --apply --only P0
    python scripts/plan_sync.py --apply --project 2
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

OWNER = "SrZafkiell"
HOME = "work-hub"
REPOS = ("work-hub", "work-hub-backend", "work-hub-frontend", "work-hub-desktop")
PLAN_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "plan"
PLAN_URL = f"https://github.com/{OWNER}/{HOME}/blob/main/docs/plan/"

ISSUE_LINE = re.compile(
    r"^- (?P<id>(?P<ms>P[0-9]|M[0-9]{2}|R[0-9])-[0-9]{2}) \[(?P<type>[a-z]+)\] "
    r"(?P<title>.+?) -- Done when: (?P<done>.+)$"
)
HEADING = re.compile(r"^# (?P<ms>P[0-9]|M[0-9]{2}|R[0-9]) - (?P<name>.+)$")
REPO_HEADING = re.compile(r"^### (?P<repo>\S+)$")
MARKER = re.compile(r"<!-- plan-id: (?P<id>[A-Z][0-9]{1,2}-[0-9]{2}) -->")
ISSUE_URL = re.compile(r"https://github\.com/[^/\s]+/(?P<repo>[^/\s]+)/issues/(?P<number>[0-9]+)")
RATE_LIMITED = re.compile(r"secondary rate limit|rate limit exceeded|abuse|HTTP 429", re.I)

TYPES = {
    "feature": ("1f6feb", "New capability"),
    "bug": ("d73a4a", "Something is broken"),
    "chore": ("6e7781", "Setup and maintenance"),
    "ci": ("8250df", "CI/CD and automation"),
    "docs": ("0e8a16", "Documentation"),
    "security": ("b60205", "Security control or hardening"),
    "test": ("fbca04", "Tests and measurements"),
    "adr": ("5319e7", "Architecture decision record"),
    "spike": ("c5def5", "Time-boxed investigation"),
}
AREAS = {
    "P0": "foundation", "P1": "runtime", "P2": "delivery",
    "M01": "skeleton", "M02": "sign-in", "M03": "workspaces", "M04": "tasks",
    "M05": "notes-search", "M06": "calendars", "M07": "reminders", "M08": "meetings",
}
AREA_COLOR = "bfdadc"
MANAGED_PREFIXES = ("type:", "area:")
RETRIES = 6


def _goal(lines: list[str]) -> str:
    """First paragraph of the '## Goal' section, joined into one line."""
    try:
        start = lines.index("## Goal") + 1
    except ValueError:
        return ""
    para: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            para.append(line.strip())
        elif para:
            break
    return " ".join(para)


def parse_plan(plan_dir: pathlib.Path) -> tuple[list[dict], list[dict]]:
    """Read every plan file; fail loudly on anything the sync could get wrong."""
    milestones: list[dict] = []
    issues: list[dict] = []
    seen: set[str] = set()
    for path in sorted(plan_dir.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        head = HEADING.match(lines[0]) if lines else None
        if not head:
            raise ValueError(f"{path.name}: first line must be '# <ID> - <name>'")
        ms = head["ms"]
        if ms not in AREAS:
            raise ValueError(f"{path.name}: unknown milestone {ms}")
        if not path.name.startswith(ms + "-"):
            raise ValueError(f"{path.name}: heading {ms} does not match the file name")
        milestones.append({
            "id": ms,
            "title": f"{ms} - {head['name']}",
            "file": path.name,
            "goal": _goal(lines),
        })
        section = ""
        repo = None
        for n, line in enumerate(lines, 1):
            if line.startswith("## "):
                section, repo = line[3:].strip(), None
                continue
            if section == "Issues" and line.startswith("### "):
                m = REPO_HEADING.match(line)
                if not m or m["repo"] not in REPOS:
                    raise ValueError(f"{path.name}:{n}: unknown repository in '{line}'")
                repo = m["repo"]
                continue
            if not line.startswith("- ") or " -- Done when: " not in line:
                continue
            m = ISSUE_LINE.match(line)
            if not m:
                raise ValueError(f"{path.name}:{n}: malformed issue line")
            if repo is None:
                raise ValueError(f"{path.name}:{n}: {m['id']} is not under a repository heading")
            if m["ms"] != ms:
                raise ValueError(f"{path.name}:{n}: {m['id']} belongs to another milestone")
            if m["type"] not in TYPES:
                raise ValueError(f"{path.name}:{n}: unknown type [{m['type']}]")
            if m["id"] in seen:
                raise ValueError(f"{path.name}:{n}: duplicate ID {m['id']}")
            seen.add(m["id"])
            issues.append({
                "id": m["id"],
                "milestone": ms,
                "repo": repo,
                "type": m["type"],
                "title": m["title"],
                "done": m["done"],
                "file": path.name,
            })
    return milestones, issues


def issue_body(issue: dict) -> str:
    return (
        f"**Done when:** {issue['done']}\n\n"
        f"Plan: [docs/plan/{issue['file']}]({PLAN_URL}{issue['file']})\n\n"
        f"<!-- plan-id: {issue['id']} -->\n"
    )


def issue_labels(issue: dict) -> list[str]:
    return [f"type:{issue['type']}", f"area:{AREAS[issue['milestone']]}"]


def merged_labels(current: list[str], wanted: list[str]) -> list[str]:
    """Wanted managed labels plus any label someone added by hand."""
    manual = [name for name in current if not name.startswith(MANAGED_PREFIXES)]
    return manual + [name for name in wanted if name not in manual]


def repos_in_use(issues: list[dict]) -> list[str]:
    """Repositories that have at least one issue, in the order of REPOS."""
    used = {issue["repo"] for issue in issues}
    return [repo for repo in REPOS if repo in used]


def milestones_of(repo: str, milestones: list[dict], issues: list[dict]) -> list[dict]:
    """The milestones that have at least one issue in the repository."""
    used = {issue["milestone"] for issue in issues if issue["repo"] == repo}
    return [m for m in milestones if m["id"] in used]


def gh(args: list[str], payload: dict | None = None, pace: float = 0.0) -> str:
    """Run gh; retry with back-off on rate limits; sleep `pace` after a write."""
    for attempt in range(RETRIES):
        proc = subprocess.run(
            ["gh", *args],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode == 0:
            if pace:
                time.sleep(pace)
            return proc.stdout
        err = (proc.stderr + proc.stdout).strip()
        if RATE_LIMITED.search(err) and attempt < RETRIES - 1:
            wait = 60 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s", flush=True)
            time.sleep(wait)
            continue
        raise RuntimeError(f"gh {' '.join(args)} failed: {err}")
    raise RuntimeError("unreachable")


def api_list(path: str) -> list[dict]:
    out = gh(["api", "--paginate", path, "--jq", ".[] | tojson"])
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def sync_labels(milestones: list[dict], issues: list[dict], apply: bool, pace: float) -> None:
    for repo in repos_in_use(issues):
        have = {label["name"] for label in api_list(f"repos/{OWNER}/{repo}/labels?per_page=100")}
        want = {f"type:{name}": spec for name, spec in TYPES.items()}
        for m in milestones_of(repo, milestones, issues):
            want[f"area:{AREAS[m['id']]}"] = (AREA_COLOR, f"Milestone {m['title']}")
        for name, (color, description) in want.items():
            if name in have:
                continue
            print(f"label + {repo} {name}", flush=True)
            if apply:
                gh(["api", "--method", "POST", f"repos/{OWNER}/{repo}/labels", "--input", "-"],
                   {"name": name, "color": color, "description": description}, pace)


def sync_milestones(milestones: list[dict], issues: list[dict], apply: bool,
                    pace: float) -> dict[tuple[str, str], int]:
    """Create each milestone in every repository that has issues for it.

    Milestones are matched by their ID prefix, so a renamed one is updated in place.
    """
    numbers: dict[tuple[str, str], int] = {}
    for repo in repos_in_use(issues):
        base = f"repos/{OWNER}/{repo}/milestones"
        have = {}
        for cur in api_list(f"{base}?state=all&per_page=100"):
            have[cur["title"].split(" - ", 1)[0]] = cur
        for m in milestones_of(repo, milestones, issues):
            description = f"{m['goal']}\n\nPlan: {PLAN_URL}{m['file']}"
            cur = have.get(m["id"])
            if cur is None:
                print(f"milestone + {repo} {m['title']}", flush=True)
                if apply:
                    out = gh(["api", "--method", "POST", base, "--input", "-"],
                             {"title": m["title"], "description": description}, pace)
                    numbers[(repo, m["id"])] = json.loads(out)["number"]
                continue
            numbers[(repo, m["id"])] = cur["number"]
            if cur["title"] != m["title"] or (cur.get("description") or "") != description:
                print(f"milestone ~ {repo} {m['title']}", flush=True)
                if apply:
                    gh(["api", "--method", "PATCH", f"{base}/{cur['number']}", "--input", "-"],
                       {"title": m["title"], "description": description}, pace)
    return numbers


def _differs(cur: dict, want: dict) -> bool:
    cur_labels = sorted(label["name"] for label in cur.get("labels", []))
    cur_milestone = cur["milestone"]["number"] if cur.get("milestone") else None
    return (
        cur["title"] != want["title"]
        or (cur.get("body") or "").replace("\r\n", "\n") != want["body"]
        or cur_labels != sorted(want["labels"])
        or ("milestone" in want and cur_milestone != want["milestone"])
    )


def find_existing() -> dict[str, tuple[str, dict]]:
    """Every issue that carries a plan ID, in any repository: ID -> (repository, issue)."""
    existing: dict[str, tuple[str, dict]] = {}
    for repo in REPOS:
        for item in api_list(f"repos/{OWNER}/{repo}/issues?state=all&per_page=100"):
            if "pull_request" in item:
                continue
            mark = MARKER.search(item.get("body") or "")
            if not mark:
                continue
            if mark["id"] in existing:
                print(f"warning: plan ID {mark['id']} is on more than one issue", flush=True)
            existing.setdefault(mark["id"], (repo, item))
    return existing


def transfer(number: int, source: str, target: str, pace: float) -> dict:
    """Move an issue to another repository and return it as it is there."""
    out = gh(["issue", "transfer", str(number), f"{OWNER}/{target}",
              "--repo", f"{OWNER}/{source}"], pace=pace)
    moved = ISSUE_URL.search(out)
    if not moved or moved["repo"] != target:
        raise RuntimeError(f"transfer of {source}#{number} gave no issue URL: {out.strip()}")
    return json.loads(gh(["api", f"repos/{OWNER}/{target}/issues/{moved['number']}"]))


def sync_issues(issues: list[dict], numbers: dict[tuple[str, str], int],
                only: set[str] | None, apply: bool, pace: float) -> list[str]:
    existing = find_existing()
    plan_ids = {issue["id"] for issue in issues}
    for orphan in sorted(set(existing) - plan_ids):
        repo, item = existing[orphan]
        print(f"warning: {repo}#{item['number']} ({orphan}) is no longer in the plan", flush=True)

    urls: list[str] = []
    created = moved = updated = unchanged = 0
    for issue in issues:
        if only and issue["milestone"] not in only:
            continue
        repo = issue["repo"]
        base = f"repos/{OWNER}/{repo}/issues"
        cur_repo, cur = existing.get(issue["id"], (repo, None))
        if cur is not None and cur_repo != repo:
            moved += 1
            print(f"issue > {cur_repo}#{cur['number']} to {repo}: {issue['id']} {issue['title']}",
                  flush=True)
            if not apply:
                continue
            cur = transfer(cur["number"], cur_repo, repo, pace)
        want = {
            "title": f"{issue['id']} {issue['title']}",
            "body": issue_body(issue),
            "labels": merged_labels(
                [label["name"] for label in cur.get("labels", [])] if cur else [],
                issue_labels(issue),
            ),
        }
        if (repo, issue["milestone"]) in numbers:
            want["milestone"] = numbers[(repo, issue["milestone"])]
        if cur is None:
            created += 1
            print(f"issue + {repo} {want['title']}", flush=True)
            if apply:
                out = gh(["api", "--method", "POST", base, "--input", "-"], want, pace)
                urls.append(json.loads(out)["html_url"])
            continue
        urls.append(cur["html_url"])
        if _differs(cur, want):
            updated += 1
            print(f"issue ~ {repo}#{cur['number']} {want['title']}", flush=True)
            if apply:
                gh(["api", "--method", "PATCH", f"{base}/{cur['number']}", "--input", "-"],
                   want, pace)
        else:
            unchanged += 1
    print(f"issues: {created} to create, {moved} to move, {updated} to update, "
          f"{unchanged} unchanged", flush=True)
    return urls


def sync_project(urls: list[str], project: int, apply: bool, pace: float) -> None:
    out = gh(["project", "item-list", str(project), "--owner", OWNER,
              "--format", "json", "--limit", "2000"])
    have = {(item.get("content") or {}).get("url") for item in json.loads(out)["items"]}
    missing = [url for url in urls if url not in have]
    print(f"project: {len(missing)} to add", flush=True)
    for url in missing:
        print(f"project + {url}", flush=True)
        if apply:
            gh(["project", "item-add", str(project), "--owner", OWNER, "--url", url], pace=pace)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the changes (default: dry run)")
    parser.add_argument("--only", help="comma-separated milestone IDs, for example P0,M01")
    parser.add_argument("--project", type=int, help="number of the user project to fill")
    parser.add_argument("--pace", type=float, default=3.0, help="seconds to wait after each write")
    parser.add_argument("--check", action="store_true", help="only parse and validate the plan")
    args = parser.parse_args(argv)

    milestones, issues = parse_plan(PLAN_DIR)
    per_repo = ", ".join(
        f"{repo} {sum(1 for issue in issues if issue['repo'] == repo)}"
        for repo in repos_in_use(issues)
    )
    print(f"plan: {len(milestones)} milestones, {len(issues)} issues ({per_repo})", flush=True)
    if args.check:
        return 0
    only = set(args.only.split(",")) if args.only else None
    if only and only - set(AREAS):
        parser.error(f"unknown milestone IDs: {', '.join(sorted(only - set(AREAS)))}")

    sync_labels(milestones, issues, args.apply, args.pace)
    numbers = sync_milestones(milestones, issues, args.apply, args.pace)
    urls = sync_issues(issues, numbers, only, args.apply, args.pace)
    if args.project:
        sync_project(urls, args.project, args.apply, args.pace)
    if not args.apply:
        print("dry run: nothing changed; pass --apply to make these changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
