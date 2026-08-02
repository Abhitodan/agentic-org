"""Feature docs lifecycle, PageIndex trees, and vector search."""

from __future__ import annotations

from pathlib import Path

from agentic_org.context import build_context
from agentic_org.docs.workspace import FeatureWorkspace, project_workspace
from agentic_org.retrieval.pageindex import build_page_tree, retrieve_from_tree
from agentic_org.retrieval.vectors import sparse_cosine, sparse_embed


def test_sparse_embed_deterministic_and_similar():
    a = sparse_embed("bulk member import CSV validation")
    b = sparse_embed("import members from CSV file validation")
    c = sparse_embed("unrelated quantum optics lecture notes")
    assert a == sparse_embed("bulk member import CSV validation")
    assert sparse_cosine(a, b) > sparse_cosine(a, c)


def test_pageindex_tree_and_structural_retrieve():
    md = """# Charter

## Problem

Users cannot import members in bulk.

## Acceptance Criteria

- CSV upload works
- Invalid rows are reported
"""
    tree = build_page_tree(md, doc_id="charter")
    assert tree.children
    assert tree.children[0].title == "Charter"
    section_titles = [c.title for c in tree.children[0].children]
    assert "Problem" in section_titles
    assert "Acceptance Criteria" in section_titles
    hits = retrieve_from_tree(tree, "CSV upload acceptance", limit=3)
    assert hits
    assert any("Acceptance" in h["title"] or "CSV" in h["text"] for h in hits)


def test_feature_workspace_create_maintain_index_search(tmp_path: Path):
    root = tmp_path / "org"
    root.mkdir()
    # Seed templates dir expected by workspace
    tmpl = root / ".agent-org" / "templates"
    tmpl.mkdir(parents=True)
    (tmpl / "feature-charter.md").write_text(
        "# Feature Charter\n\n## Problem\n\n_TBD_\n", encoding="utf-8",
    )
    (tmpl / "sprint-plan.md").write_text(
        "# Implementation Plan\n\n## Epics\n\n_TBD_\n", encoding="utf-8",
    )

    ctx = build_context(str(root))
    project_workspace(ctx.root, "demo")
    project = ctx.store.create_project("demo", None)
    feature = ctx.store.create_feature(project["id"], "import", "Bulk import")
    ws = FeatureWorkspace(ctx.root, "demo", "import")
    ws.create(feature["id"], "Bulk import")

    assert (ws.dir / "charter.md").exists()
    assert (ws.dir / "implementation-plan.md").exists()
    assert (ws.dir / "documents.json").exists()
    assert (ws.dir / "docs").is_dir()

    ws.write_doc(
        "charter",
        "# Feature Charter\n\n## Problem\n\nNeed bulk CSV import for members.\n\n"
        "## Acceptance Criteria\n\n- CSV parsed\n",
        source="human",
        status="draft",
    )
    maintained = ws.maintain()
    assert "documents" in maintained

    report = ctx.indexer.index_feature("demo", "import")
    assert report.files_indexed >= 3
    assert report.pageindex_trees >= 3
    assert report.vector_chunks >= 1
    assert list((ws.dir / "artifacts" / "pageindex").glob("*.tree.json"))

    hybrid = ctx.indexer.search(
        "CSV import members", mode="hybrid", project="demo", feature="import",
    )
    assert hybrid["hits"]
    vector = ctx.indexer.search(
        "CSV import", mode="vector", project="demo", feature="import",
    )
    assert vector["hits"]
    page = ctx.indexer.search(
        "Acceptance Criteria", mode="pageindex", project="demo", feature="import",
    )
    assert page["hits"]
