from pathlib import Path

from agentic_org.context import build_context
from agentic_org.core.budget import Budget


def test_graph_rebuild_and_impact(tmp_path: Path, git_repo: Path):
    root = tmp_path / "org"
    root.mkdir()
    ctx = build_context(str(root))
    project = ctx.store.create_project("demo", str(git_repo))
    feature = ctx.store.create_feature(project["id"], "search", "Add search")
    ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    counts = ctx.memory.rebuild(ctx.store, ctx.events, ctx.root)
    assert counts["nodes"] >= 3
    assert counts["edges"] >= 2
    hits = ctx.memory.search("search", kinds=["FEATURE"])
    assert hits and hits[0].label == "search"
    impact = ctx.memory.impact(feature["id"])
    assert impact["feature"]["label"] == "search"
    assert impact["projects"][0]["label"] == "demo"
    assert len(impact["workflows"]) == 1
