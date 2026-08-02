"""Command-center API surface: snapshot, pipeline projection, actions, assets."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_org.api.app import create_app
from agentic_org.context import build_context
from agentic_org.core.budget import Budget


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    root = tmp_path / "org"
    root.mkdir()
    monkeypatch.setenv("AGENTIC_ORG_ROOT", str(root))
    monkeypatch.chdir(root)
    return TestClient(create_app())


def test_snapshot_shape_when_empty(client):
    snap = client.get("/api/state").json()
    assert snap["projects"] == []
    assert snap["workflows"] == []
    assert snap["system"]["event_chain_valid"] is True
    assert "model_provider" in snap["system"]
    assert snap["jobs"] == []


def test_snapshot_projects_pipeline_and_costs(client, git_repo, no_model_key):
    ctx = build_context(None)
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(project["id"], "bulk-import", "Add bulk import")
    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    ctx.runner.start("demo", "bulk-import", feature["objective"],
                     str(git_repo), workflow["id"])

    snap = client.get("/api/state").json()
    assert len(snap["workflows"]) == 1
    wf = snap["workflows"][0]
    assert wf["state"] == "BLOCKED"
    assert wf["feature_name"] == "bulk-import"
    assert wf["project_name"] == "demo"

    nodes = {n["key"]: n["status"] for n in wf["pipeline"]}
    assert nodes["intake"] == "done"
    assert nodes["map_repository"] == "done"
    assert nodes["create_brain"] == "done"
    assert nodes["draft_charter"] == "blocked"
    assert nodes["plan"] == "pending"
    assert nodes["implement"] == "pending"
    assert nodes["merge"] == "pending"
    assert nodes["release"] == "pending"

    assert wf["checkpoints"], "workflow-start checkpoint must be projected"
    assert snap["costs"][0]["workflow_id"] == wf["id"]


def test_document_endpoint_reports_missing_without_fabricating(client, git_repo):
    ctx = build_context(None)
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(project["id"], "search", "Add search")

    doc = client.get(f"/api/features/{feature['id']}/document/charter").json()
    assert doc["exists"] is False
    assert doc["content"] is None

    unknown = client.get(f"/api/features/{feature['id']}/document/nope")
    assert unknown.status_code == 404


def test_run_action_validates_inputs(client, git_repo):
    missing = client.post("/api/features/feat_missing/run", json={})
    assert missing.status_code == 404

    ctx = build_context(None)
    project = ctx.store.create_project("no-repo", None)
    feature = ctx.store.create_feature(project["id"], "x", "objective")
    unconnected = client.post(f"/api/features/{feature['id']}/run", json={})
    assert unconnected.status_code == 400
    detail = unconnected.json()["detail"].lower()
    assert "path" in detail or "repository" in detail or "component" in detail


def test_resume_and_revert_guard_unknown_workflows(client):
    assert client.post("/api/workflows/wf_missing/resume").status_code == 404
    revert = client.post("/api/workflows/wf_missing/revert",
                         json={"checkpoint_id": "ckpt_x"})
    assert revert.status_code == 404


def test_ui_assets_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "Command Center" in page.text
    assert "starfield" not in page.text

    css = client.get("/assets/styles.css")
    assert css.status_code == 200
    assert "no-store" in css.headers["cache-control"]
    assert "--accent" in css.text
    assert client.get("/assets/app.js").status_code == 200
    assert "AgentTheater" in client.get("/assets/app.js").text or \
        "Agent theater" in client.get("/assets/app.js").text
    assert client.get("/assets/../secrets").status_code in (400, 404)


def test_approval_accepts_release_gate(client, git_repo):
    ctx = build_context(None)
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(project["id"], "ship", "Ship it")
    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    ctx.store.request_approval(workflow["id"], "release-approval", "release?")
    res = client.post(
        f"/workflows/{workflow['id']}/approval",
        json={"approve": True, "gate": "release-approval",
              "decided_by": "tester", "reason": "ok"},
    )
    assert res.status_code == 200
    assert ctx.store.approval_granted(workflow["id"], "release-approval")
    bad = client.post(
        f"/workflows/{workflow['id']}/approval",
        json={"approve": True, "gate": "not-a-gate"},
    )
    assert bad.status_code == 400
