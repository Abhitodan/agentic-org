"""End-to-end workflow test without a model key.

Validates the honesty guarantee: the pipeline performs all deterministic
work (intake, checkpoint, repository map, feature brain), then BLOCKS at
the charter step instead of fabricating LLM output.
"""

from pathlib import Path

from agentic_org.context import build_context
from agentic_org.core.budget import Budget


def _setup(tmp_path: Path, git_repo: Path):
    root = tmp_path / "org-root"
    root.mkdir()
    ctx = build_context(str(root))
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(project["id"], "bulk-import",
                                       "Add bulk member import")
    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    return ctx, project, feature, workflow


def test_workflow_blocks_honestly_without_model(tmp_path, git_repo, no_model_key):
    ctx, project, feature, workflow = _setup(tmp_path, git_repo)
    result = ctx.runner.start("demo", "bulk-import", feature["objective"],
                              str(git_repo), workflow["id"])

    final = ctx.store.get_workflow(workflow["id"])
    assert final["state"] == "BLOCKED"
    assert "model gateway unavailable" in (result.get("blocked_reason") or "")

    # Deterministic work actually happened and produced real artifacts.
    artifacts = ctx.root / "projects" / "demo" / "features" / "bulk-import" / "artifacts"
    assert (artifacts / "repo-map.json").exists()
    brain_md = artifacts.parent / "FEATURE_BRAIN.md"
    assert brain_md.exists()
    assert "Repository Map" in brain_md.read_text(encoding="utf-8")

    # Git checkpoint was created on the target repo at intake.
    checkpoints = ctx.store.list_checkpoints(workflow["id"])
    assert len(checkpoints) == 1
    assert checkpoints[0]["kind"] == "workflow-start"

    # Event trail is complete and the hash chain verifies.
    event_types = {ev["event_type"] for ev in ctx.events.list(workflow_id=workflow["id"])}
    assert {"workflow.transition", "intake.classified", "repository.mapped",
            "brain.updated", "workflow.blocked"} <= event_types
    ok, _ = ctx.events.verify_chain()
    assert ok

    # Blocked run consumed budget for real work but no model spend.
    _, spent = ctx.store.load_budget(final)
    assert spent.tool_calls == 3
    assert spent.cost_usd == 0.0


def test_transitions_recorded_in_order(tmp_path, git_repo, no_model_key):
    ctx, project, feature, workflow = _setup(tmp_path, git_repo)
    ctx.runner.start("demo", "bulk-import", feature["objective"],
                     str(git_repo), workflow["id"])
    transitions = [
        ev["payload"] for ev in reversed(
            ctx.events.list(workflow_id=workflow["id"],
                            event_type="workflow.transition"))
    ]
    states = [(t["from"], t["to"]) for t in transitions]
    assert states == [
        ("DRAFT", "INTAKE"),
        ("INTAKE", "DISCOVERY"),
        ("DISCOVERY", "RESEARCHING"),
        ("RESEARCHING", "BLOCKED"),
    ]
