#!/usr/bin/env python3
"""Synchronize EnglishApp issue lifecycle labels with Project LangstudyGuard.

GOV-0E-A1 / R2 pilot. Status tracking only — never sets Done or Approval Gate=Approved.
Uses typed GraphQL variables; never interpolates issue title/body into queries.

Tracking-removal policy (F2):
  Removing lsg:tracked disables further automatic Status changes for that issue.
  Existing Project items are NOT removed and Status is NOT auto-reset.
  A sanitized diagnostic is emitted; Project cleanup requires authorized manual action.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, MutableMapping, Optional

GITHUB_GRAPHQL = "https://api.github.com/graphql"

# Allowed automation statuses only.
ALLOWED_STATUS_NAMES = frozenset({"Backlog", "In Progress", "In Review", "Blocked"})
FORBIDDEN_STATUS_NAMES = frozenset({"Done", "Ready"})  # Ready is Owner/manual; Done never automated

LABEL_TRACKED = "lsg:tracked"
LABEL_DOING = "lsg:doing"
LABEL_REVIEW = "lsg:review"
LABEL_BLOCKED = "lsg:blocked"
TRACKED_LABELS = frozenset({LABEL_TRACKED, LABEL_DOING, LABEL_REVIEW, LABEL_BLOCKED})
# Explicit lifecycle labels that may move an item out of Ready.
EXPLICIT_LIFECYCLE_LABELS = frozenset({LABEL_DOING, LABEL_REVIEW, LABEL_BLOCKED})

# Highest priority wins when multiple lifecycle labels are present.
STATUS_PRIORITY = (
    (LABEL_BLOCKED, "Blocked"),
    (LABEL_REVIEW, "In Review"),
    (LABEL_DOING, "In Progress"),
    (LABEL_TRACKED, "Backlog"),
)

# Project V2 field reads/writes are not compare-and-swap. A concurrent Owner/Leader
# approval can still race an in-flight sync; this pilot never claims absolute protection.

TRACKING_DISABLED_MESSAGE = (
    "lsg:tracked absent; automation will not change Project Status; "
    "existing Project item (if any) is left unchanged; "
    "Project cleanup requires an authorized manual action"
)


class SyncError(RuntimeError):
    """Fail-closed sync failure with sanitized diagnostics only."""

    def __init__(
        self,
        category: str,
        *,
        operation: str,
        issue_number: Optional[int] = None,
        http_status: Optional[int] = None,
    ) -> None:
        self.category = category
        self.operation = operation
        self.issue_number = issue_number
        self.http_status = http_status
        parts = [f"category={category}", f"operation={operation}"]
        if issue_number is not None:
            parts.append(f"issue_number={issue_number}")
        if http_status is not None:
            parts.append(f"http_status={http_status}")
        super().__init__("; ".join(parts))

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action": "failed",
            "category": self.category,
            "operation": self.operation,
        }
        if self.issue_number is not None:
            payload["issue_number"] = self.issue_number
        if self.http_status is not None:
            payload["http_status"] = self.http_status
        return payload


@dataclass(frozen=True)
class IssueRef:
    node_id: str
    number: int
    labels: frozenset[str]


@dataclass(frozen=True)
class ProjectRefs:
    project_id: str
    status_field_id: str
    status_option_ids: Mapping[str, str]


GraphQLClient = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def desired_status_from_labels(labels: frozenset[str]) -> Optional[str]:
    """Return target Status when lsg:tracked is present; else None."""
    if LABEL_TRACKED not in labels:
        return None
    for label, status in STATUS_PRIORITY:
        if label in labels:
            return status
    return None


def tracking_disabled(labels: frozenset[str]) -> bool:
    """True when the issue is no longer in the automated tracking set."""
    return LABEL_TRACKED not in labels


def assert_status_allowed(status_name: str) -> None:
    if status_name in FORBIDDEN_STATUS_NAMES or status_name not in ALLOWED_STATUS_NAMES:
        raise SyncError(
            "unauthorized_status",
            operation="assert_status_allowed",
        )


def parse_issue_event(event: Mapping[str, Any]) -> Optional[tuple[IssueRef, str, str]]:
    """Parse issues labeled/unlabeled event.

    Returns (IssueRef from event payload, label_name, action) or None if not a pilot label.
    Callers MUST refresh labels from GitHub before mutating (stale-event safety).
    """
    action = event.get("action")
    if action not in {"labeled", "unlabeled"}:
        return None
    label_obj = event.get("label") or {}
    label_name = label_obj.get("name")
    if not isinstance(label_name, str) or not label_name.startswith("lsg:"):
        return None
    if label_name not in TRACKED_LABELS:
        raise SyncError(
            "unsupported_lsg_label",
            operation="parse_issue_event",
        )
    issue = event.get("issue") or {}
    node_id = issue.get("node_id")
    number = issue.get("number")
    if not isinstance(node_id, str) or not isinstance(number, int):
        raise SyncError(
            "malformed_issue_event",
            operation="parse_issue_event",
        )
    labels = frozenset(
        str(x.get("name"))
        for x in (issue.get("labels") or [])
        if isinstance(x, Mapping) and x.get("name")
    )
    return IssueRef(node_id=node_id, number=number, labels=labels), label_name, str(action)


def http_graphql_client(
    token: str,
    *,
    endpoint: str = GITHUB_GRAPHQL,
    token_name: str = "token",
) -> GraphQLClient:
    if not token:
        raise SyncError(
            "missing_token",
            operation=f"http_graphql_client:{token_name}",
        )

    def _call(query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = "graphql"
        payload = json.dumps({"query": query, "variables": dict(variables)}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "EnglishApp-lsg-project-sync/0.2",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # F5: never print raw response bodies or headers.
            raise SyncError(
                "http_error",
                operation=operation,
                http_status=int(exc.code),
            ) from None
        except urllib.error.URLError as exc:
            raise SyncError(
                "network_error",
                operation=operation,
            ) from None
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SyncError(
                "invalid_json",
                operation=operation,
            ) from None
        if not isinstance(data, dict):
            raise SyncError("unexpected_envelope", operation=operation)
        if data.get("errors"):
            raise SyncError("graphql_errors", operation=operation)
        result = data.get("data")
        if not isinstance(result, Mapping):
            raise SyncError("missing_data", operation=operation)
        return result

    return _call


def fetch_current_issue_labels(
    client: GraphQLClient,
    *,
    node_id: str,
    issue_number: int,
) -> frozenset[str]:
    """Re-read live issue labels (all pages). Fail closed if a page is incomplete/unusable."""
    names: set[str] = set()
    cursor: Optional[str] = None
    while True:
        if cursor is None:
            query = """
            query($id: ID!) {
              node(id: $id) {
                ... on Issue {
                  id
                  number
                  labels(first: 100) {
                    nodes { name }
                    pageInfo { hasNextPage endCursor }
                  }
                }
              }
            }
            """
            variables: dict[str, Any] = {"id": node_id}
        else:
            query = """
            query($id: ID!, $after: String!) {
              node(id: $id) {
                ... on Issue {
                  id
                  number
                  labels(first: 100, after: $after) {
                    nodes { name }
                    pageInfo { hasNextPage endCursor }
                  }
                }
              }
            }
            """
            variables = {"id": node_id, "after": cursor}
        data = client(query, variables)
        node = data.get("node")
        if not isinstance(node, Mapping) or node.get("id") != node_id:
            raise SyncError(
                "issue_not_found",
                operation="fetch_current_issue_labels",
                issue_number=issue_number,
            )
        labels_obj = node.get("labels")
        if not isinstance(labels_obj, Mapping):
            raise SyncError(
                "unexpected_issue_schema",
                operation="fetch_current_issue_labels",
                issue_number=issue_number,
            )
        nodes = labels_obj.get("nodes")
        if not isinstance(nodes, list):
            raise SyncError(
                "incomplete_label_page",
                operation="fetch_current_issue_labels",
                issue_number=issue_number,
            )
        for item in nodes:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                names.add(item["name"])
        page_info = labels_obj.get("pageInfo") or {}
        if page_info.get("hasNextPage"):
            end = page_info.get("endCursor")
            if not isinstance(end, str) or not end:
                raise SyncError(
                    "incomplete_label_pagination",
                    operation="fetch_current_issue_labels",
                    issue_number=issue_number,
                )
            cursor = end
            continue
        return frozenset(names)


def resolve_project(
    client: GraphQLClient,
    *,
    owner: str,
    number: int,
    issue_number: Optional[int] = None,
) -> ProjectRefs:
    query = """
    query($login: String!, $number: Int!) {
      user(login: $login) {
        projectV2(number: $number) {
          id
          field(name: "Status") {
            ... on ProjectV2SingleSelectField {
              id
              name
              options { id name }
            }
          }
        }
      }
    }
    """
    data = client(query, {"login": owner, "number": number})
    user = data.get("user")
    if not isinstance(user, Mapping) or not user.get("projectV2"):
        raise SyncError(
            "project_unavailable",
            operation="resolve_project",
            issue_number=issue_number,
        )
    project = user["projectV2"]
    project_id = project.get("id")
    field = project.get("field")
    if not isinstance(project_id, str) or not isinstance(field, Mapping):
        raise SyncError(
            "unexpected_project_schema",
            operation="resolve_project",
            issue_number=issue_number,
        )
    field_id = field.get("id")
    options = field.get("options")
    if not isinstance(field_id, str) or not isinstance(options, list):
        raise SyncError(
            "unexpected_status_field",
            operation="resolve_project",
            issue_number=issue_number,
        )
    option_ids: dict[str, str] = {}
    seen_names: set[str] = set()
    for opt in options:
        if not isinstance(opt, Mapping):
            continue
        name = opt.get("name")
        oid = opt.get("id")
        if isinstance(name, str) and isinstance(oid, str):
            if name in seen_names:
                raise SyncError(
                    "duplicate_status_option",
                    operation="resolve_project",
                    issue_number=issue_number,
                )
            seen_names.add(name)
            option_ids[name] = oid
    for required in ALLOWED_STATUS_NAMES:
        if required not in option_ids:
            raise SyncError(
                "missing_status_option",
                operation="resolve_project",
                issue_number=issue_number,
            )
    return ProjectRefs(
        project_id=project_id,
        status_field_id=field_id,
        status_option_ids=option_ids,
    )


def read_item_status(
    client: GraphQLClient,
    *,
    item_id: str,
    issue_number: int,
) -> Optional[str]:
    """Read current Project Status for an item. Returns None if unset/unknown."""
    query = """
    query($itemId: ID!) {
      node(id: $itemId) {
        ... on ProjectV2Item {
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue {
              name
            }
          }
        }
      }
    }
    """
    data = client(query, {"itemId": item_id})
    node = data.get("node")
    if not isinstance(node, Mapping):
        raise SyncError(
            "item_status_unavailable",
            operation="read_item_status",
            issue_number=issue_number,
        )
    field_value = node.get("fieldValueByName")
    if field_value is None:
        return None
    if not isinstance(field_value, Mapping):
        raise SyncError(
            "unexpected_status_value",
            operation="read_item_status",
            issue_number=issue_number,
        )
    name = field_value.get("name")
    if name is None:
        return None
    if not isinstance(name, str):
        raise SyncError(
            "unexpected_status_value",
            operation="read_item_status",
            issue_number=issue_number,
        )
    return name


def protection_action(
    current_status: Optional[str],
    labels: frozenset[str],
) -> Optional[str]:
    """Return protected_* action if Status must not be overwritten; else None."""
    if current_status == "Done":
        return "protected_done"
    if current_status == "Ready" and not (labels & EXPLICIT_LIFECYCLE_LABELS):
        return "protected_ready"
    return None


def find_project_item_id(
    client: GraphQLClient,
    *,
    project_id: str,
    content_id: str,
    issue_number: Optional[int] = None,
) -> Optional[str]:
    """Paginate Project items until the Issue content id is found."""
    cursor: Optional[str] = None
    while True:
        if cursor is None:
            page_query = """
            query($projectId: ID!) {
              node(id: $projectId) {
                ... on ProjectV2 {
                  items(first: 100) {
                    nodes {
                      id
                      content {
                        ... on Issue { id }
                        ... on DraftIssue { id }
                        ... on PullRequest { id }
                      }
                    }
                    pageInfo { hasNextPage endCursor }
                  }
                }
              }
            }
            """
            variables: dict[str, Any] = {"projectId": project_id}
        else:
            page_query = """
            query($projectId: ID!, $after: String!) {
              node(id: $projectId) {
                ... on ProjectV2 {
                  items(first: 100, after: $after) {
                    nodes {
                      id
                      content {
                        ... on Issue { id }
                        ... on DraftIssue { id }
                        ... on PullRequest { id }
                      }
                    }
                    pageInfo { hasNextPage endCursor }
                  }
                }
              }
            }
            """
            variables = {"projectId": project_id, "after": cursor}
        data = client(page_query, variables)
        node = data.get("node")
        if not isinstance(node, Mapping):
            raise SyncError(
                "project_items_unavailable",
                operation="find_project_item_id",
                issue_number=issue_number,
            )
        items = node.get("items")
        if not isinstance(items, Mapping):
            raise SyncError(
                "unexpected_items_schema",
                operation="find_project_item_id",
                issue_number=issue_number,
            )
        for item in items.get("nodes") or []:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if isinstance(content, Mapping) and content.get("id") == content_id:
                item_id = item.get("id")
                if isinstance(item_id, str):
                    return item_id
        page_info = items.get("pageInfo") or {}
        if page_info.get("hasNextPage") and isinstance(page_info.get("endCursor"), str):
            cursor = page_info["endCursor"]
            continue
        return None


def add_issue_to_project(
    client: GraphQLClient,
    *,
    project_id: str,
    content_id: str,
    issue_number: int,
) -> str:
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item { id }
      }
    }
    """
    data = client(mutation, {"projectId": project_id, "contentId": content_id})
    payload = data.get("addProjectV2ItemById")
    if not isinstance(payload, Mapping):
        raise SyncError(
            "add_item_failed",
            operation="add_issue_to_project",
            issue_number=issue_number,
        )
    item = payload.get("item")
    if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
        raise SyncError(
            "add_item_missing_id",
            operation="add_issue_to_project",
            issue_number=issue_number,
        )
    return item["id"]


def set_status(
    client: GraphQLClient,
    *,
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
    status_name: str,
    issue_number: int,
) -> None:
    assert_status_allowed(status_name)
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: { singleSelectOptionId: $optionId }
        }
      ) {
        projectV2Item { id }
      }
    }
    """
    try:
        data = client(
            mutation,
            {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "optionId": option_id,
            },
        )
    except SyncError as exc:
        raise SyncError(
            exc.category,
            operation="set_status",
            issue_number=issue_number,
            http_status=exc.http_status,
        ) from None
    if not isinstance(data.get("updateProjectV2ItemFieldValue"), Mapping):
        raise SyncError(
            "status_update_failed",
            operation="set_status",
            issue_number=issue_number,
        )


def ensure_item_and_status(
    client: GraphQLClient,
    *,
    refs: ProjectRefs,
    issue: IssueRef,
    desired_status: str,
    state: Optional[MutableMapping[str, Any]] = None,
) -> dict[str, Any]:
    """Idempotent add + conditional status update. Never overwrites Done; guards Ready."""
    assert_status_allowed(desired_status)
    option_id = refs.status_option_ids.get(desired_status)
    if not option_id:
        raise SyncError(
            "missing_status_option",
            operation="ensure_item_and_status",
            issue_number=issue.number,
        )

    item_id = find_project_item_id(
        client,
        project_id=refs.project_id,
        content_id=issue.node_id,
        issue_number=issue.number,
    )
    created = False
    if item_id is None:
        item_id = add_issue_to_project(
            client,
            project_id=refs.project_id,
            content_id=issue.node_id,
            issue_number=issue.number,
        )
        created = True
        if state is not None:
            state["added_item_id"] = item_id

    current_status = read_item_status(
        client, item_id=item_id, issue_number=issue.number
    )
    protected = protection_action(current_status, issue.labels)
    if protected is not None:
        result = {
            "action": protected,
            "issue_number": issue.number,
            "item_id": item_id,
            "created": created,
            "current_status": current_status,
            "desired_status": desired_status,
            "project_mutated": False,
            "status": current_status,
        }
        if state is not None:
            state["last"] = result
        return result

    if current_status == desired_status:
        result = {
            "action": "synced",
            "issue_number": issue.number,
            "item_id": item_id,
            "created": created,
            "status": desired_status,
            "project_mutated": False,
        }
        if state is not None:
            state["last"] = result
        return result

    try:
        set_status(
            client,
            project_id=refs.project_id,
            item_id=item_id,
            field_id=refs.status_field_id,
            option_id=option_id,
            status_name=desired_status,
            issue_number=issue.number,
        )
    except SyncError as exc:
        # F4: item may already exist; caller/retry must not treat this as success.
        raise SyncError(
            "partial_sync_status_failed" if created else exc.category,
            operation="ensure_item_and_status",
            issue_number=issue.number,
            http_status=exc.http_status,
        ) from None

    result = {
        "issue_number": issue.number,
        "item_id": item_id,
        "created": created,
        "status": desired_status,
        "action": "synced",
        "project_mutated": True,
        "previous_status": current_status,
    }
    if state is not None:
        state["last"] = result
    return result


def sync_from_event(
    event: Mapping[str, Any],
    *,
    project_client: GraphQLClient,
    issue_client: GraphQLClient,
    owner: str,
    number: int,
    refresh_labels: bool = True,
) -> dict[str, Any]:
    """Synchronize using live issue labels (unless refresh_labels=False for unit tests)."""
    parsed = parse_issue_event(event)
    if parsed is None:
        return {"action": "ignored", "reason": "not_a_pilot_label_event"}
    event_issue, trigger_label, action = parsed

    if refresh_labels:
        live_labels = fetch_current_issue_labels(
            issue_client,
            node_id=event_issue.node_id,
            issue_number=event_issue.number,
        )
    else:
        live_labels = event_issue.labels

    issue = IssueRef(
        node_id=event_issue.node_id,
        number=event_issue.number,
        labels=live_labels,
    )

    # Unrelated non-pilot labels never reach here (workflow + parse filters).
    # Explicit no-op for non-tracking issues that somehow still trigger.
    if tracking_disabled(live_labels):
        # F2: visible policy — do not mutate Project item/status.
        return {
            "action": "tracking_disabled",
            "issue_number": issue.number,
            "trigger_label": trigger_label,
            "event_action": action,
            "policy": TRACKING_DISABLED_MESSAGE,
            "project_mutated": False,
        }

    desired = desired_status_from_labels(live_labels)
    if desired is None:
        return {
            "action": "ignored",
            "reason": "no_desired_status",
            "issue_number": issue.number,
            "project_mutated": False,
        }

    refs = resolve_project(
        project_client,
        owner=owner,
        number=number,
        issue_number=issue.number,
    )
    return ensure_item_and_status(
        project_client,
        refs=refs,
        issue=issue,
        desired_status=desired,
    )


def load_event(path: str) -> Mapping[str, Any]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SyncError("malformed_event_file", operation="load_event")
    return data


def main(argv: list[str] | None = None) -> int:
    _ = list(sys.argv[1:] if argv is None else argv)
    owner = os.environ.get("LSG_PROJECT_OWNER", "nguyenthaibinh19")
    number_raw = os.environ.get("LSG_PROJECT_NUMBER", "1")
    try:
        number = int(number_raw)
    except ValueError as exc:
        raise SyncError("invalid_project_number", operation="main") from None
    project_token = os.environ.get("LSG_PROJECT_TOKEN", "")
    # Prefer dedicated read token for live labels; fall back to project token.
    issue_token = os.environ.get("GITHUB_TOKEN") or project_token
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SyncError("missing_event_path", operation="main")
    event = load_event(event_path)
    project_client = http_graphql_client(project_token, token_name="LSG_PROJECT_TOKEN")
    issue_client = http_graphql_client(issue_token, token_name="GITHUB_TOKEN")
    result = sync_from_event(
        event,
        project_client=project_client,
        issue_client=issue_client,
        owner=owner,
        number=number,
        refresh_labels=True,
    )
    # Audit line: numbers/status/policy only — never titles/bodies/tokens/raw HTTP.
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as exc:
        print(json.dumps(exc.as_dict(), sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None
