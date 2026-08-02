"""Reuse substantial charter/plan when the model gateway is unavailable."""

from __future__ import annotations

from pathlib import Path

from agentic_org.context import build_context
from agentic_org.core.budget import Budget
from agentic_org.docs.workspace import FeatureWorkspace
from agentic_org.orchestrator.runner import PLAN_GATE


CHARTER = """# Feature Charter: Bulk Member Import

## Problem
Manual enrollment is slow for large datasets.

## Users
- Administrators

## Outcome
Import 10k rows under 5 minutes.

## Scope
CSV upload and validation.

## Exclusions
Billing changes.

## Acceptance criteria
- Invalid rows rejected with line numbers
- Partial success allowed

## Risks
PII in logs.

## Architecture options
### Option C: Hybrid
Sync validate first 200 rows; async remainder.
"""

PLAN = """# Implementation Plan: Bulk Member Import

**Goal:** Automate large volume member imports for Administrators.

## Epics
1. CSV ingest and validation
2. Async import worker
3. Retry and audit

## Stories
- Accept text/csv uploads
- Reject files over 25MB with HTTP 413
- Required columns member_id group_id effective_date

## Test expectations
- pytest tests/test_importer.py -q

## Rollback notes
- Feature flag bulk_member_import_v1 off by default
"""


def test_reuses_charter_when_model_unavailable(tmp_path: Path, git_repo: Path, no_model_key):
    root = tmp_path / "org"
    root.mkdir()
    ctx = build_context(str(root))
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(
        project["id"], "bulk-import", "Add bulk member import",
    )
    ws = FeatureWorkspace(ctx.root, "demo", "bulk-import")
    ws.create(feature["id"], feature["objective"])
    ws.write_doc("charter", CHARTER, source="human", status="draft")

    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    result = ctx.runner.start(
        "demo", "bulk-import", feature["objective"], str(git_repo), workflow["id"],
    )
    final = ctx.store.get_workflow(workflow["id"])
    assert final["state"] == "AWAITING_DECISION"
    assert not result.get("blocked_reason")
    events = {e["event_type"] for e in ctx.events.list(workflow_id=workflow["id"])}
    assert "charter.reused" in events
    assert "approval.requested" in events


def test_reuses_plan_after_approval(tmp_path: Path, git_repo: Path, no_model_key):
    root = tmp_path / "org"
    root.mkdir()
    ctx = build_context(str(root))
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(
        project["id"], "bulk-import", "Add bulk member import",
    )
    ws = FeatureWorkspace(ctx.root, "demo", "bulk-import")
    ws.create(feature["id"], feature["objective"])
    ws.write_doc("charter", CHARTER, source="human", status="draft")
    ws.write_doc("plan", PLAN, source="human", status="draft")

    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    ctx.runner.start(
        "demo", "bulk-import", feature["objective"], str(git_repo), workflow["id"],
    )
    ctx.store.decide_approval(workflow["id"], PLAN_GATE, True, "tester", "ok")
    resumed = ctx.runner.resume(workflow["id"])
    final = ctx.store.get_workflow(workflow["id"])
    # Implement still needs model/actions — may block later, but plan reused.
    events = {e["event_type"] for e in ctx.events.list(workflow_id=workflow["id"])}
    assert "plan.reused" in events
    assert final["state"] in {"PLANNED", "IMPLEMENTING", "BLOCKED", "MERGING"}
    assert resumed.get("blocked_reason") is None or "model" in (
        resumed.get("blocked_reason") or ""
    ).lower() or "action" in (resumed.get("blocked_reason") or "").lower()
