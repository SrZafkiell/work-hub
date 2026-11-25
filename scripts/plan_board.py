#!/usr/bin/env python3
"""The project board side of the plan sync: items, fields, values, views and the guide.

The board is a GitHub Projects (v2) board owned by a user. This module knows nothing
about the plan: plan_sync.py hands it the cards (issue URL -> field values) and the
field definitions.

The API creates a view and sets its name, layout, filter and visible fields. Grouping,
sorting, slicing, and the date fields, markers and zoom of a roadmap can only be set in
the browser; VIEWS records them, docs/BOARD.md lists them, and

    python scripts/plan_board.py <project number>

prints every setting of a saved view that differs from VIEWS.
"""
from __future__ import annotations

import json
import sys
from typing import Callable

BATCH = 10  # field values per request; larger batches ran into gateway timeouts

# group: the field a table or a roadmap is grouped by, or the swimlanes of a board.
# columns: the column field of a board. by_hand: what the API can neither set nor read.
VIEWS: tuple[dict, ...] = (
    {"name": "Roadmap", "layout": "ROADMAP_LAYOUT", "filter": "type:Epic",
     "group": "Track", "sort": ("Start", "ASC"),
     "by_hand": "dates Start and Target, markers Milestone, zoom Quarter"},
    {"name": "Progress", "layout": "TABLE_LAYOUT", "filter": "type:Epic",
     "fields": ("Title", "Sub-issues progress", "Status", "Phase", "Track", "Start", "Target"),
     "sort": ("Start", "ASC")},
    {"name": "Milestones", "layout": "TABLE_LAYOUT", "filter": "type:Task -label:tech-debt",
     "fields": ("Title", "Status", "Priority", "Repository", "Start", "Target", "Labels"),
     "group": "Milestone", "sort": ("Target", "ASC")},
    {"name": "By repository", "layout": "ROADMAP_LAYOUT", "filter": "type:Task",
     "group": "Repository", "sort": ("Start", "ASC"),
     "by_hand": "dates Start and Target, markers Milestone, zoom Month"},
    {"name": "This week", "layout": "BOARD_LAYOUT",
     "filter": "is:open target:<=@today+6d -type:Epic",
     "fields": ("Title", "Priority", "Target", "Labels"),
     "columns": "Status", "group": "Repository", "sort": ("Target", "ASC")},
    {"name": "Late", "layout": "TABLE_LAYOUT", "filter": "is:open target:<@today",
     "fields": ("Title", "Status", "Priority", "Target", "Milestone", "Labels"),
     "group": "Repository", "sort": ("Target", "ASC")},
    {"name": "Blocked", "layout": "TABLE_LAYOUT", "filter": "is:open label:blocked,needs:decision",
     "fields": ("Title", "Status", "Priority", "Target", "Repository", "Labels")},
    {"name": "In review", "layout": "TABLE_LAYOUT", "filter": "is:open has:linked-pull-requests",
     "fields": ("Title", "Linked pull requests", "Status", "Priority", "Target", "Repository")},
    {"name": "Done last 7 days", "layout": "TABLE_LAYOUT", "filter": "is:closed closed:>=@today-7d",
     "fields": ("Title", "Closed", "Milestone", "Linked pull requests"),
     "group": "Repository", "sort": ("Closed", "DESC")},
    {"name": "My work", "layout": "BOARD_LAYOUT", "filter": "assignee:@me -type:Epic",
     "fields": ("Title", "Priority", "Target", "Repository", "Labels"),
     "columns": "Status", "sort": ("Start", "ASC")},
    {"name": "Tech debt", "layout": "TABLE_LAYOUT", "filter": "label:tech-debt",
     "fields": ("Title", "Status", "Priority", "Repository", "Milestone", "Target"),
     "group": "Priority", "sort": ("Repository", "ASC")},
    {"name": "All work", "layout": "TABLE_LAYOUT", "filter": "",
     "fields": ("Title", "Assignees", "Status", "Priority", "Phase", "Track", "Start", "Target",
                "Milestone", "Repository", "Labels"),
     "group": "Phase", "sort": ("Start", "ASC"), "by_hand": "slice by Repository"},
)

PROJECT = """
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      readme
      fields(first: 50) { nodes {
        ... on ProjectV2FieldCommon { id name dataType }
        ... on ProjectV2SingleSelectField { options { id name color description } }
      } }
      views(first: 50) { nodes {
        id number name layout filter
        fields(first: 30) { nodes { ... on ProjectV2FieldCommon { name } } }
        groupByFields(first: 5) { nodes { ... on ProjectV2FieldCommon { name } } }
        verticalGroupByFields(first: 5) { nodes { ... on ProjectV2FieldCommon { name } } }
        sortByFields(first: 5) { nodes { direction field { ... on ProjectV2FieldCommon { name } } } }
      } }
    }
  }
}
"""
ITEMS = """
query($project: ID!, $after: String) {
  node(id: $project) { ... on ProjectV2 { items(first: 100, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      content { ... on Issue { url } ... on PullRequest { url } }
      fieldValues(first: 30) { nodes {
        ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
        ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
      } }
    }
  } } }
}
"""
CREATE_FIELD = """
mutation($input: CreateProjectV2FieldInput!) {
  createProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2FieldCommon { id name } } }
}
"""
UPDATE_FIELD = """
mutation($input: UpdateProjectV2FieldInput!) {
  updateProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2FieldCommon { id name } } }
}
"""
CREATE_VIEW = """
mutation($input: CreateProjectV2ViewInput!) {
  createProjectV2View(input: $input) { projectV2View { id name } }
}
"""
UPDATE_VIEW = """
mutation($input: UpdateProjectV2ViewInput!) {
  updateProjectV2View(input: $input) { projectV2View { id name } }
}
"""
UPDATE_PROJECT = """
mutation($input: UpdateProjectV2Input!) {
  updateProjectV2(input: $input) { projectV2 { id } }
}
"""


def changed_values(cards: dict[str, dict[str, str]],
                   items: dict[str, dict]) -> list[tuple[str, str, str]]:
    """(item ID, field, value) for every wanted value a card on the board does not have."""
    changes = []
    for url, want in cards.items():
        item = items.get(url)
        if item is None:
            continue
        for name, value in want.items():
            if item["values"].get(name) != value:
                changes.append((item["id"], name, value))
    return changes


def value_mutation(project_id: str, fields: dict[str, dict],
                   changes: list[tuple[str, str, str]]) -> str:
    """One GraphQL document that sets every value in `changes`."""
    parts = []
    for n, (item, name, value) in enumerate(changes):
        field = fields[name]
        if field["dataType"] == "DATE":
            literal = f"{{date: {json.dumps(value)}}}"
        else:
            literal = f"{{singleSelectOptionId: {json.dumps(field['options'][value]['id'])}}}"
        parts.append(
            f"  m{n}: updateProjectV2ItemFieldValue(input: {{projectId: {json.dumps(project_id)}, "
            f"itemId: {json.dumps(item)}, fieldId: {json.dumps(field['id'])}, value: {literal}}}) "
            "{ projectV2Item { id } }"
        )
    return "mutation {\n" + "\n".join(parts) + "\n}\n"


def view_gaps(spec: dict, view: dict | None) -> list[str]:
    """What a saved view lacks against its definition, as far as the API can tell."""
    if view is None:
        return ["missing"]
    gaps = []
    if view["layout"] != spec["layout"]:
        gaps.append(f"layout {view['layout']} instead of {spec['layout']}")
    if (view["filter"] or "") != spec["filter"]:
        gaps.append(f"filter '{view['filter'] or ''}' instead of '{spec['filter']}'")
    board = spec["layout"] == "BOARD_LAYOUT"
    group = [node.get("name") for node in view["groupByFields"]["nodes"]]
    columns = [node.get("name") for node in view["verticalGroupByFields"]["nodes"]]
    sort = [(node["field"].get("name"), node["direction"]) for node in view["sortByFields"]["nodes"]]
    want_group = [spec["group"]] if spec.get("group") else []
    if group != want_group:
        kind = "swimlanes" if board else "group"
        gaps.append(f"{kind} {group or 'none'} instead of {want_group or 'none'}")
    if board and columns != [spec["columns"]]:
        gaps.append(f"columns {columns or 'none'} instead of {[spec['columns']]}")
    want_sort = [spec["sort"]] if spec.get("sort") else []
    if sort != want_sort:
        gaps.append(f"sort {sort or 'none'} instead of {want_sort or 'none'}")
    return gaps


class Board:
    """A user's project board, changed only when `apply` is set."""

    def __init__(self, gh: Callable[..., str], owner: str, number: int, apply: bool, pace: float):
        self.gh = gh
        self.owner = owner
        self.number = number
        self.apply = apply
        self.pace = pace

    def graphql(self, query: str, variables: dict | None = None, write: bool = False,
                repeatable: bool = False) -> dict:
        """Run a query or a mutation; a read, or a write marked so, is retried on a gateway error."""
        out = self.gh(["api", "graphql", "--input", "-"],
                      {"query": query, "variables": variables or {}},
                      self.pace if write else 0.0, repeatable=repeatable or not write)
        return json.loads(out)["data"]

    def project(self) -> dict:
        data = self.graphql(PROJECT, {"owner": self.owner, "number": self.number})
        project = data["user"]["projectV2"]
        fields = {}
        for node in project["fields"]["nodes"]:
            if node:
                fields[node["name"]] = {
                    "id": node["id"],
                    "dataType": node["dataType"],
                    "options": {option["name"]: option for option in node.get("options", [])},
                }
        return {
            "id": project["id"],
            "readme": project["readme"] or "",
            "fields": fields,
            "views": {view["name"]: view for view in project["views"]["nodes"]},
        }

    def items(self, project_id: str) -> dict[str, dict]:
        """Issue or pull request URL -> the card and its single-select and date values."""
        items: dict[str, dict] = {}
        after = None
        while True:
            page = self.graphql(ITEMS, {"project": project_id, "after": after})["node"]["items"]
            for node in page["nodes"]:
                url = (node.get("content") or {}).get("url")
                if not url:
                    continue
                values = {}
                for value in node["fieldValues"]["nodes"]:
                    if value:
                        values[value["field"]["name"]] = value.get("name") or value.get("date")
                items[url] = {"id": node["id"], "values": values}
            if not page["pageInfo"]["hasNextPage"]:
                return items
            after = page["pageInfo"]["endCursor"]

    def sync_items(self, urls: list[str]) -> None:
        out = self.gh(["project", "item-list", str(self.number), "--owner", self.owner,
                       "--format", "json", "--limit", "2000"])
        have = {(item.get("content") or {}).get("url") for item in json.loads(out)["items"]}
        missing = [url for url in urls if url not in have]
        print(f"project: {len(missing)} to add", flush=True)
        for url in missing:
            print(f"project + {url}", flush=True)
            if self.apply:
                self.gh(["project", "item-add", str(self.number), "--owner", self.owner,
                         "--url", url], pace=self.pace)

    def sync_fields(self, specs: list[dict]) -> None:
        """Create the custom fields; add options that a single-select field lacks."""
        project = self.project()
        for spec in specs:
            options = [{"name": name, "color": color, "description": text}
                       for name, color, text in spec["options"]]
            cur = project["fields"].get(spec["name"])
            if cur is None:
                print(f"field + {spec['name']}", flush=True)
                if self.apply:
                    payload = {"projectId": project["id"], "dataType": spec["type"],
                               "name": spec["name"]}
                    if options:
                        payload["singleSelectOptions"] = options
                    self.graphql(CREATE_FIELD, {"input": payload}, write=True)
                continue
            if cur["dataType"] != spec["type"]:
                raise RuntimeError(f"field {spec['name']} is {cur['dataType']}, not {spec['type']}")
            new = [option for option in options if option["name"] not in cur["options"]]
            if new:
                print(f"field ~ {spec['name']}: + {', '.join(o['name'] for o in new)}", flush=True)
                if self.apply:
                    # The mutation replaces the whole set: resend every option with its ID.
                    keep = [{"id": o["id"], "name": o["name"], "color": o["color"],
                             "description": o["description"]} for o in cur["options"].values()]
                    self.graphql(UPDATE_FIELD, {"input": {"fieldId": cur["id"],
                                                         "singleSelectOptions": keep + new}},
                                 write=True)

    def sync_values(self, cards: dict[str, dict[str, str]]) -> None:
        project = self.project()
        changes = changed_values(cards, self.items(project["id"]))
        touched = len({item for item, _, _ in changes})
        print(f"fields: {len(changes)} values to set on {touched} cards", flush=True)
        if not self.apply:
            return
        for start in range(0, len(changes), BATCH):
            batch = changes[start:start + BATCH]
            # Setting a value twice is harmless, so a batch cut short by a gateway error is resent.
            self.graphql(value_mutation(project["id"], project["fields"], batch), write=True,
                         repeatable=True)
            print(f"fields: {min(start + BATCH, len(changes))} of {len(changes)} set", flush=True)

    def sync_views(self) -> None:
        """Create each view of VIEWS and keep its layout and filter.

        The first view takes over the "View 1" of a new board, so the board opens on it.
        """
        project = self.project()
        views = project["views"]
        spare = views.get("View 1")
        for spec in VIEWS:
            cur = views.get(spec["name"])
            visible = [project["fields"][name]["id"] for name in spec.get("fields", ())
                       if name in project["fields"]]
            if cur is None and spare is not None and spec is VIEWS[0]:
                print(f"view ~ View 1 becomes {spec['name']}", flush=True)
                if self.apply:
                    self.graphql(UPDATE_VIEW, {"input": {
                        "viewId": spare["id"], "name": spec["name"], "layout": spec["layout"],
                        "filter": spec["filter"]}}, write=True)
                continue
            if cur is None:
                print(f"view + {spec['name']}", flush=True)
                if self.apply:
                    payload = {"projectId": project["id"], "name": spec["name"],
                               "layout": spec["layout"]}
                    if visible:
                        payload["configuration"] = {"visibleFieldIds": visible}
                    made = self.graphql(CREATE_VIEW, {"input": payload}, write=True)
                    if spec["filter"]:
                        self.graphql(UPDATE_VIEW, {"input": {
                            "viewId": made["createProjectV2View"]["projectV2View"]["id"],
                            "filter": spec["filter"]}}, write=True)
                continue
            if cur["layout"] != spec["layout"] or (cur["filter"] or "") != spec["filter"]:
                print(f"view ~ {spec['name']}", flush=True)
                if self.apply:
                    self.graphql(UPDATE_VIEW, {"input": {
                        "viewId": cur["id"], "layout": spec["layout"],
                        "filter": spec["filter"]}}, write=True)
        print("views: grouping, sorting and roadmap dates are set in the browser, "
              "see docs/BOARD.md", flush=True)

    def sync_guide(self, text: str) -> None:
        project = self.project()
        if project["readme"].replace("\r\n", "\n").strip() == text.strip():
            print("guide: unchanged", flush=True)
            return
        print("guide ~ board README", flush=True)
        if self.apply:
            self.graphql(UPDATE_PROJECT, {"input": {"projectId": project["id"], "readme": text}},
                         write=True)

    def report_views(self) -> int:
        """Print what each saved view lacks; return the number of views with a gap."""
        views = self.project()["views"]
        behind = 0
        for spec in VIEWS:
            gaps = view_gaps(spec, views.get(spec["name"]))
            behind += bool(gaps)
            print(f"{spec['name']}: {'; '.join(gaps) if gaps else 'ok'}", flush=True)
            if spec.get("by_hand"):
                print(f"  check in the browser: {spec['by_hand']}", flush=True)
        for name in sorted(set(views) - {spec["name"] for spec in VIEWS}):
            print(f"{name}: not in VIEWS", flush=True)
        return behind


def main(argv: list[str] | None = None) -> int:
    import plan_sync

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not args[0].isdigit():
        print("usage: python scripts/plan_board.py <project number>", file=sys.stderr)
        return 2
    board = Board(plan_sync.gh, plan_sync.OWNER, int(args[0]), apply=False, pace=0.0)
    return 1 if board.report_views() else 0


if __name__ == "__main__":
    sys.exit(main())
