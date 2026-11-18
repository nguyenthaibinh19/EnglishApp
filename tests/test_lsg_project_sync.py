"""Offline / mocked GOV-0E-A1 R2 project sync tests. No live GitHub Project calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from lsg_project_sync.sync_project_item import (  # noqa: E402
    ALLOWED_STATUS_NAMES,
    TRACKING_DISABLED_MESSAGE,
    IssueRef,
    ProjectRefs,
    SyncError,
    assert_status_allowed,
    desired_status_from_labels,
    ensure_item_and_status,
    fetch_current_issue_labels,
    find_project_item_id,
    http_graphql_client,
    parse_issue_event,
    protection_action,
    resolve_project,
    sync_from_event,
    tracking_disabled,
)


def _issue_event(
    *,
    action: str,
    label: str,
    number: int,
    node_id: str,
    labels: list[str],
) -> dict[str, Any]:
    return {
        "action": action,
        "label": {"name": label},
        "issue": {
            "number": number,
            "node_id": node_id,
            "labels": [{"name": n} for n in labels],
        },
    }


class FakeClient:
    """Shared fake for project + issue GraphQL."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.project_id = "PVT_proj"
        self.status_field_id = "PVTSSF_status"
        self.options = {
            "Backlog": "opt_backlog",
            "Ready": "opt_ready",
            "In Progress": "opt_progress",
            "In Review": "opt_review",
            "Blocked": "opt_blocked",
            "Done": "opt_done",
        }
        self.items: dict[str, str] = {}  # content_id -> item_id
        self.status_by_item: dict[str, str] = {}
        self.live_labels: dict[str, frozenset[str]] = {}
        self.missing_status_option: str | None = None
        self.add_count = 0
        self.fail_status_once = False
        self.fail_status_always = False
        self.fail_http_status: int | None = None
        self.fail_graphql = False
        # Pagination: ordered content ids; page size 2 for tests.
        self.item_order: list[str] = []
        self.page_size = 100
        self.label_page_size = 100
        self.duplicate_status_name: str | None = None
        self.incomplete_label_pagination = False

    def set_live_labels(self, node_id: str, labels: set[str] | frozenset[str] | list[str]) -> None:
        self.live_labels[node_id] = frozenset(labels)

    def __call__(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((query, dict(variables)))
        if self.fail_http_status is not None:
            raise SyncError(
                "http_error",
                operation="graphql",
                http_status=self.fail_http_status,
            )
        if self.fail_graphql:
            raise SyncError("graphql_errors", operation="graphql")

        if "fieldValueByName(name: \"Status\")" in query or "fieldValueByName(name: \"Status\")" in query.replace(
            "\n", " "
        ):
            item_id = variables["itemId"]
            name = self.status_by_item.get(item_id)
            if name is None:
                return {"node": {"fieldValueByName": None}}
            return {"node": {"fieldValueByName": {"name": name}}}

        if "labels(first:" in query and "$id" in query:
            node_id = variables["id"]
            labels = sorted(self.live_labels.get(node_id, frozenset()))
            after = variables.get("after")
            start = 0
            if after:
                start = int(str(after).split("-")[1]) + 1
            page = labels[start : start + self.label_page_size]
            last = start + len(page) - 1
            has_next = (start + self.label_page_size) < len(labels)
            if self.incomplete_label_pagination and has_next:
                return {
                    "node": {
                        "id": node_id,
                        "number": 1,
                        "labels": {
                            "nodes": [{"name": n} for n in page],
                            "pageInfo": {"hasNextPage": True, "endCursor": None},
                        },
                    }
                }
            return {
                "node": {
                    "id": node_id,
                    "number": 1,
                    "labels": {
                        "nodes": [{"name": n} for n in page],
                        "pageInfo": {
                            "hasNextPage": has_next,
                            "endCursor": f"cursor-{last}" if page else None,
                        },
                    },
                }
            }

        if "projectV2(number: $number)" in query:
            options = [
                {"id": oid, "name": name}
                for name, oid in self.options.items()
                if name != self.missing_status_option
            ]
            if self.duplicate_status_name:
                options.append(
                    {
                        "id": "opt_dup",
                        "name": self.duplicate_status_name,
                    }
                )
            return {
                "user": {
                    "projectV2": {
                        "id": self.project_id,
                        "field": {
                            "id": self.status_field_id,
                            "name": "Status",
                            "options": options,
                        },
                    }
                }
            }

        if "items(first:" in query:
            order = self.item_order or list(self.items.keys())
            # Build pages from order
            after = variables.get("after")
            start = 0
            if after:
                # after is an index marker "cursor-N"
                start = int(str(after).split("-")[1]) + 1
            page_ids = order[start : start + self.page_size]
            nodes = []
            for content_id in page_ids:
                item_id = self.items[content_id]
                nodes.append({"id": item_id, "content": {"id": content_id}})
            last_index = start + len(page_ids) - 1
            has_next = (start + self.page_size) < len(order)
            return {
                "node": {
                    "items": {
                        "nodes": nodes,
                        "pageInfo": {
                            "hasNextPage": has_next,
                            "endCursor": f"cursor-{last_index}" if page_ids else None,
                        },
                    }
                }
            }

        if "addProjectV2ItemById" in query:
            content_id = variables["contentId"]
            if content_id in self.items:
                return {"addProjectV2ItemById": {"item": {"id": self.items[content_id]}}}
            self.add_count += 1
            item_id = f"PVTI_{self.add_count}"
            self.items[content_id] = item_id
            self.item_order.append(content_id)
            self.status_by_item[item_id] = "Backlog"
            return {"addProjectV2ItemById": {"item": {"id": item_id}}}

        if "updateProjectV2ItemFieldValue" in query:
            if self.fail_status_always or self.fail_status_once:
                self.fail_status_once = False
                raise SyncError(
                    "http_error",
                    operation="graphql",
                    http_status=502,
                )
            item_id = variables["itemId"]
            option_id = variables["optionId"]
            name = next(n for n, oid in self.options.items() if oid == option_id)
            if name not in ALLOWED_STATUS_NAMES:
                raise SyncError("unauthorized_status", operation="set_status")
            self.status_by_item[item_id] = name
            return {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": item_id}}}

        raise SyncError("unexpected_query", operation="fake_client")


def test_desired_status_mapping():
    assert desired_status_from_labels(frozenset()) is None
    assert desired_status_from_labels(frozenset({"bug"})) is None
    assert desired_status_from_labels(frozenset({"lsg:doing"})) is None
    assert desired_status_from_labels(frozenset({"lsg:tracked"})) == "Backlog"
    assert (
        desired_status_from_labels(frozenset({"lsg:tracked", "lsg:doing"})) == "In Progress"
    )
    assert (
        desired_status_from_labels(frozenset({"lsg:tracked", "lsg:review"})) == "In Review"
    )
    assert (
        desired_status_from_labels(frozenset({"lsg:tracked", "lsg:blocked"})) == "Blocked"
    )
    assert (
        desired_status_from_labels(
            frozenset({"lsg:tracked", "lsg:doing", "lsg:review", "lsg:blocked"})
        )
        == "Blocked"
    )


def test_assert_status_refuses_done():
    with pytest.raises(SyncError) as ei:
        assert_status_allowed("Done")
    assert ei.value.category == "unauthorized_status"
    with pytest.raises(SyncError):
        assert_status_allowed("Ready")
    assert_status_allowed("Backlog")
    assert_status_allowed("In Progress")


def test_parse_ignores_non_lsg_label():
    event = _issue_event(
        action="labeled",
        label="bug",
        number=3,
        node_id="I_1",
        labels=["bug", "lsg:tracked"],
    )
    assert parse_issue_event(event) is None


def test_parse_rejects_unknown_lsg_label():
    event = _issue_event(
        action="labeled",
        label="lsg:done",
        number=3,
        node_id="I_1",
        labels=["lsg:tracked", "lsg:done"],
    )
    with pytest.raises(SyncError) as ei:
        parse_issue_event(event)
    assert ei.value.category == "unsupported_lsg_label"


def test_new_tracked_issue_adds_and_sets_backlog():
    client = FakeClient()
    client.set_live_labels("I_new", {"lsg:tracked"})
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=10,
        node_id="I_new",
        labels=["lsg:tracked"],
    )
    result = sync_from_event(
        event,
        project_client=client,
        issue_client=client,
        owner="nguyenthaibinh19",
        number=1,
    )
    assert result["action"] == "synced"
    assert result["created"] is True
    assert result["status"] == "Backlog"
    assert client.add_count == 1


def test_in_progress_transition():
    client = FakeClient()
    client.items["I_1"] = "PVTI_existing"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_existing"] = "Backlog"
    client.set_live_labels("I_1", {"lsg:tracked", "lsg:doing"})
    event = _issue_event(
        action="labeled",
        label="lsg:doing",
        number=3,
        node_id="I_1",
        labels=["lsg:tracked", "lsg:doing"],
    )
    result = sync_from_event(
        event,
        project_client=client,
        issue_client=client,
        owner="nguyenthaibinh19",
        number=1,
    )
    assert result["created"] is False
    assert result["status"] == "In Progress"
    assert client.status_by_item["PVTI_existing"] == "In Progress"


def test_in_review_and_blocked_transitions():
    client = FakeClient()
    client.items["I_1"] = "PVTI_x"
    client.item_order = ["I_1"]
    for label, status in (("lsg:review", "In Review"), ("lsg:blocked", "Blocked")):
        client.set_live_labels("I_1", {"lsg:tracked", label})
        event = _issue_event(
            action="labeled",
            label=label,
            number=3,
            node_id="I_1",
            labels=["lsg:tracked", label],
        )
        result = sync_from_event(
            event,
            project_client=client,
            issue_client=client,
            owner="nguyenthaibinh19",
            number=1,
        )
        assert result["status"] == status


def test_duplicate_event_delivery_is_idempotent():
    client = FakeClient()
    client.set_live_labels("I_dup", {"lsg:tracked"})
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=10,
        node_id="I_dup",
        labels=["lsg:tracked"],
    )
    r1 = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    r2 = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert r1["item_id"] == r2["item_id"]
    assert r1["created"] is True
    assert r2["created"] is False
    assert client.add_count == 1


def test_unknown_untracked_issue_ignored_as_tracking_disabled():
    client = FakeClient()
    client.set_live_labels("I_other", {"lsg:doing"})
    event = _issue_event(
        action="labeled",
        label="lsg:doing",
        number=99,
        node_id="I_other",
        labels=["lsg:doing"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "tracking_disabled"
    assert result["project_mutated"] is False
    assert client.add_count == 0


def test_missing_project_permissions_fail_closed():
    client = FakeClient()
    client.set_live_labels("I_1", {"lsg:tracked"})

    def boom(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        raise SyncError("http_error", operation="graphql", http_status=401)

    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    with pytest.raises(SyncError) as ei:
        sync_from_event(
            event,
            project_client=boom,
            issue_client=client,
            owner="nguyenthaibinh19",
            number=1,
        )
    assert ei.value.http_status == 401


def test_invalid_field_ids_fail_closed():
    client = FakeClient()
    client.missing_status_option = "In Progress"
    client.set_live_labels("I_1", {"lsg:tracked"})
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    with pytest.raises(SyncError) as ei:
        sync_from_event(
            event,
            project_client=client,
            issue_client=client,
            owner="nguyenthaibinh19",
            number=1,
        )
    assert ei.value.category == "missing_status_option"


def test_attempted_unauthorized_done_transition_refused():
    client = FakeClient()
    refs = ProjectRefs(
        project_id=client.project_id,
        status_field_id=client.status_field_id,
        status_option_ids=client.options,
    )
    issue = IssueRef(node_id="I_1", number=1, labels=frozenset({"lsg:tracked"}))
    with pytest.raises(SyncError):
        ensure_item_and_status(client, refs=refs, issue=issue, desired_status="Done")
    assert client.add_count == 0


def test_resolve_project_requires_user_project():
    def empty(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        return {"user": None}

    with pytest.raises(SyncError) as ei:
        resolve_project(empty, owner="nguyenthaibinh19", number=1)
    assert ei.value.category == "project_unavailable"


def test_event_fixture_roundtrip(tmp_path: Path):
    client = FakeClient()
    client.set_live_labels("I_3", {"lsg:tracked", "lsg:review"})
    event = _issue_event(
        action="labeled",
        label="lsg:review",
        number=3,
        node_id="I_3",
        labels=["lsg:tracked", "lsg:review"],
    )
    event["issue"]["title"] = '"); drop table issues;--'
    event["issue"]["body"] = "secret-token-should-not-leak"
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    result = sync_from_event(
        loaded, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["status"] == "In Review"
    for _query, variables in client.calls:
        blob = json.dumps(variables)
        assert "secret-token" not in blob
        assert "drop table" not in blob


# --- R2: F3 unlabeled recomputation ---


@pytest.mark.parametrize(
    "removed,remaining,expected",
    [
        ("lsg:doing", ["lsg:tracked"], "Backlog"),
        ("lsg:review", ["lsg:tracked", "lsg:doing"], "In Progress"),
        ("lsg:blocked", ["lsg:tracked", "lsg:review"], "In Review"),
        ("lsg:doing", ["lsg:tracked", "lsg:blocked"], "Blocked"),
    ],
)
def test_unlabeled_recomputes_status(removed: str, remaining: list[str], expected: str):
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "In Progress"
    client.set_live_labels("I_1", set(remaining))
    event = _issue_event(
        action="unlabeled",
        label=removed,
        number=7,
        node_id="I_1",
        labels=remaining,  # stale-ish payload; live labels win
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "synced"
    assert result["status"] == expected
    assert client.status_by_item["PVTI_1"] == expected


def test_unrelated_label_event_does_not_reach_sync_mutation():
    """Workflow filters non-lsg labels; parser returns None — no Project client calls."""
    client = FakeClient()
    event = _issue_event(
        action="unlabeled",
        label="documentation",
        number=7,
        node_id="I_1",
        labels=["lsg:tracked", "lsg:doing"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "ignored"
    assert client.calls == []


def test_priority_blocked_over_review_doing_backlog():
    labels = frozenset({"lsg:tracked", "lsg:doing", "lsg:review", "lsg:blocked"})
    assert desired_status_from_labels(labels) == "Blocked"
    assert tracking_disabled(frozenset({"lsg:doing"})) is True


# --- R2: F2 tracking removal policy ---


def test_removing_tracked_emits_policy_and_does_not_mutate():
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "In Review"
    client.set_live_labels("I_1", {"lsg:doing"})  # tracked removed; leftover lifecycle ignored
    event = _issue_event(
        action="unlabeled",
        label="lsg:tracked",
        number=42,
        node_id="I_1",
        labels=[],  # event payload
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "tracking_disabled"
    assert result["project_mutated"] is False
    assert result["issue_number"] == 42
    assert TRACKING_DISABLED_MESSAGE in result["policy"]
    assert client.status_by_item["PVTI_1"] == "In Review"  # unchanged
    assert client.add_count == 0
    # No add/update mutations
    assert all("addProjectV2ItemById" not in q for q, _ in client.calls)
    assert all("updateProjectV2ItemFieldValue" not in q for q, _ in client.calls)


# --- R2: F1 stale events / convergence ---


def test_stale_event_payload_uses_live_labels_for_final_status():
    """Event claims doing, but live labels are review-only → In Review."""
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.set_live_labels("I_1", {"lsg:tracked", "lsg:review"})
    event = _issue_event(
        action="labeled",
        label="lsg:doing",
        number=3,
        node_id="I_1",
        labels=["lsg:tracked", "lsg:doing"],  # stale
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["status"] == "In Review"
    assert client.status_by_item["PVTI_1"] == "In Review"


def test_overlapping_sequential_runs_converge_to_live_final_state():
    """
    Models Actions pending-run behavior under cancel-in-progress=false:
    earlier queued run still executes after a later label change, but refreshes labels.
    Does NOT claim wall-clock ordering across hosts — only final-state convergence.
    """
    client = FakeClient()
    client.items["I_9"] = "PVTI_9"
    client.item_order = ["I_9"]

    # Run A starts from stale "doing" event; live state already blocked.
    client.set_live_labels("I_9", {"lsg:tracked", "lsg:blocked"})
    event_a = _issue_event(
        action="labeled",
        label="lsg:doing",
        number=9,
        node_id="I_9",
        labels=["lsg:tracked", "lsg:doing"],
    )
    r_a = sync_from_event(
        event_a, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert r_a["status"] == "Blocked"

    # Run B also converges.
    event_b = _issue_event(
        action="labeled",
        label="lsg:blocked",
        number=9,
        node_id="I_9",
        labels=["lsg:tracked", "lsg:blocked"],
    )
    r_b = sync_from_event(
        event_b, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert r_b["status"] == "Blocked"
    assert client.status_by_item["PVTI_9"] == "Blocked"
    assert client.add_count == 0


def test_workflow_declares_per_issue_concurrency_without_cancel():
    text = (ROOT / ".github/workflows/lsg-project-sync.yml").read_text(encoding="utf-8")
    assert "concurrency:" in text
    assert "github.repository" in text
    assert "github.event.issue.number" in text
    assert "cancel-in-progress: false" in text
    assert "on:\n  issues:" in text.replace("\r\n", "\n")
    assert "pull_request_target:" not in text



# --- R2: F4 partial failure + pagination ---


def test_partial_failure_then_retry_updates_without_duplicate():
    client = FakeClient()
    client.set_live_labels("I_pf", {"lsg:tracked", "lsg:doing"})
    event = _issue_event(
        action="labeled",
        label="lsg:doing",
        number=5,
        node_id="I_pf",
        labels=["lsg:tracked", "lsg:doing"],
    )
    client.fail_status_once = True
    with pytest.raises(SyncError) as ei:
        sync_from_event(
            event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
        )
    assert ei.value.category == "partial_sync_status_failed"
    assert ei.value.issue_number == 5
    assert client.add_count == 1
    item_id = client.items["I_pf"]
    assert client.status_by_item[item_id] == "Backlog"  # workflow default; status update failed

    # Retry finds existing item, updates status, no second add.
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "synced"
    assert result["created"] is False
    assert result["status"] == "In Progress"
    assert client.add_count == 1
    assert client.status_by_item[item_id] == "In Progress"


def test_graphql_error_and_http_failure_sanitized():
    client = FakeClient()
    client.set_live_labels("I_1", {"lsg:tracked"})
    client.fail_http_status = 503
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    with pytest.raises(SyncError) as ei:
        sync_from_event(
            event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
        )
    msg = str(ei.value)
    assert "http_status=503" in msg
    assert "secret" not in msg.lower()
    d = ei.value.as_dict()
    assert set(d) <= {"action", "category", "operation", "issue_number", "http_status"}
    assert "body" not in d


def test_http_client_sanitizes_http_error(monkeypatch: pytest.MonkeyPatch):
    import io
    import urllib.error
    import urllib.request

    def fake_urlopen(req, timeout=30):  # noqa: ARG001
        raise urllib.error.HTTPError(
            url="https://api.github.com/graphql",
            code=500,
            msg="boom",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"secret":"should-not-leak"}'),
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = http_graphql_client("tok")
    with pytest.raises(SyncError) as ei:
        client("query { ok }", {})
    assert ei.value.category == "http_error"
    assert ei.value.http_status == 500
    assert "should-not-leak" not in str(ei.value)
    assert "should-not-leak" not in json.dumps(ei.value.as_dict())


def test_find_item_paginates_beyond_first_page():
    client = FakeClient()
    client.page_size = 2
    # 5 filler items then target
    for i in range(5):
        cid = f"I_fill_{i}"
        client.items[cid] = f"PVTI_fill_{i}"
        client.item_order.append(cid)
    client.items["I_target"] = "PVTI_target"
    client.item_order.append("I_target")
    found = find_project_item_id(
        client, project_id=client.project_id, content_id="I_target", issue_number=1
    )
    assert found == "PVTI_target"
    # More than one items query occurred
    item_queries = [q for q, _ in client.calls if "items(first:" in q]
    assert len(item_queries) >= 3


def test_fetch_current_issue_labels():
    client = FakeClient()
    client.set_live_labels("I_1", {"lsg:tracked", "lsg:doing", "bug"})
    labels = fetch_current_issue_labels(client, node_id="I_1", issue_number=1)
    assert labels == frozenset({"lsg:tracked", "lsg:doing", "bug"})


# --- R3: Done / Ready protection ---


def test_existing_done_with_tracked_remains_done():
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "Done"
    client.set_live_labels("I_1", {"lsg:tracked"})
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "protected_done"
    assert result["project_mutated"] is False
    assert client.status_by_item["PVTI_1"] == "Done"
    assert all("updateProjectV2ItemFieldValue" not in q for q, _ in client.calls)


def test_existing_done_with_review_event_remains_done():
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "Done"
    client.set_live_labels("I_1", {"lsg:tracked", "lsg:review"})
    event = _issue_event(
        action="labeled",
        label="lsg:review",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked", "lsg:review"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "protected_done"
    assert client.status_by_item["PVTI_1"] == "Done"


def test_removing_lifecycle_cannot_reopen_done():
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "Done"
    client.set_live_labels("I_1", {"lsg:tracked"})
    event = _issue_event(
        action="unlabeled",
        label="lsg:review",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "protected_done"
    assert result["desired_status"] == "Backlog"
    assert client.status_by_item["PVTI_1"] == "Done"


def test_existing_ready_tracking_only_remains_ready():
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "Ready"
    client.set_live_labels("I_1", {"lsg:tracked"})
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "protected_ready"
    assert client.status_by_item["PVTI_1"] == "Ready"


def test_existing_ready_plus_doing_transitions_to_in_progress():
    client = FakeClient()
    client.items["I_1"] = "PVTI_1"
    client.item_order = ["I_1"]
    client.status_by_item["PVTI_1"] = "Ready"
    client.set_live_labels("I_1", {"lsg:tracked", "lsg:doing"})
    event = _issue_event(
        action="labeled",
        label="lsg:doing",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked", "lsg:doing"],
    )
    result = sync_from_event(
        event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
    )
    assert result["action"] == "synced"
    assert result["status"] == "In Progress"
    assert client.status_by_item["PVTI_1"] == "In Progress"


def test_duplicate_status_option_names_fail_closed():
    client = FakeClient()
    client.duplicate_status_name = "Backlog"
    client.set_live_labels("I_1", {"lsg:tracked"})
    event = _issue_event(
        action="labeled",
        label="lsg:tracked",
        number=1,
        node_id="I_1",
        labels=["lsg:tracked"],
    )
    with pytest.raises(SyncError) as ei:
        sync_from_event(
            event, project_client=client, issue_client=client, owner="nguyenthaibinh19", number=1
        )
    assert ei.value.category == "duplicate_status_option"


def test_incomplete_label_pagination_fails_closed():
    client = FakeClient()
    # More labels than one page; next page cursor missing → fail closed
    many = {f"label-{i}" for i in range(5)} | {"lsg:tracked"}
    client.set_live_labels("I_1", many)
    client.label_page_size = 3
    client.incomplete_label_pagination = True
    with pytest.raises(SyncError) as ei:
        fetch_current_issue_labels(client, node_id="I_1", issue_number=1)
    assert ei.value.category == "incomplete_label_pagination"


def test_label_pagination_collects_all_pages():
    client = FakeClient()
    many = {f"label-{i}" for i in range(5)} | {"lsg:tracked", "lsg:doing"}
    client.set_live_labels("I_1", many)
    client.label_page_size = 3
    labels = fetch_current_issue_labels(client, node_id="I_1", issue_number=1)
    assert labels == frozenset(many)


def test_protection_action_matrix():
    assert protection_action("Done", frozenset({"lsg:tracked"})) == "protected_done"
    assert protection_action("Ready", frozenset({"lsg:tracked"})) == "protected_ready"
    assert protection_action("Ready", frozenset({"lsg:tracked", "lsg:doing"})) is None
    assert protection_action("In Progress", frozenset({"lsg:tracked"})) is None
