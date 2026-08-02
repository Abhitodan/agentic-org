"""Product topology (mono/multi) and scoped vector clear."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_org.api.app import create_app
from agentic_org.context import build_context
from agentic_org.products.topology import (
    Component,
    ProductTopology,
    ensure_topology,
    load_topology,
    save_topology,
)
from agentic_org.retrieval.vectors import VectorStore


def test_mono_bootstrap_and_primary_path(tmp_path: Path):
    root = tmp_path / "org"
    (root / "projects" / "demo").mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    topo = ensure_topology(root, "demo", repo_path=str(repo), shape="mono")
    assert topo.shape == "mono"
    assert topo.primary_path == str(repo.resolve())
    assert (root / "projects" / "demo" / "product.yaml").exists()
    again = load_topology(root, "demo")
    assert again and again.components[0].id == "main"


def test_multi_upsert_components(tmp_path: Path):
    root = tmp_path / "org"
    (root / "projects" / "suite").mkdir(parents=True)
    topo = ProductTopology(name="suite", shape="multi", components=[])
    be = tmp_path / "be"
    fe = tmp_path / "fe"
    be.mkdir()
    fe.mkdir()
    topo.upsert_component(Component(
        id="sql", name="SQL", kind="sql", path=str(be), order_hint=10,
    ))
    topo.upsert_component(Component(
        id="frontend", name="UI", kind="frontend", path=str(fe), order_hint=30,
    ))
    save_topology(root, topo)
    loaded = load_topology(root, "suite")
    assert loaded.shape == "multi"
    assert loaded.primary_path == str(be.resolve())
    assert [c.id for c in loaded.components] == ["sql", "frontend"]


def test_vector_clear_scoped_by_project_and_feature(tmp_path: Path):
    store = VectorStore.from_path(tmp_path / "vectors.db")
    store.upsert_chunk(
        doc_path="a.md", node_id="p1:f1:n1", title="A", text="alpha import",
        project="p1", feature="f1",
    )
    store.upsert_chunk(
        doc_path="b.md", node_id="p2:f1:n1", title="B", text="alpha import",
        project="p2", feature="f1",
    )
    store.clear(project="p1", feature="f1")
    left = store.search("alpha", limit=10)
    assert len(left) == 1
    assert left[0].project == "p2"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    root = tmp_path / "org"
    root.mkdir()
    monkeypatch.setenv("AGENTIC_ORG_ROOT", str(root))
    monkeypatch.chdir(root)
    return TestClient(create_app())


def test_api_create_product_and_topology(client, tmp_path: Path):
    repo = tmp_path / "src"
    repo.mkdir()
    created = client.post("/api/products", json={
        "name": "billing", "shape": "multi", "repo_path": str(repo),
    })
    assert created.status_code == 200
    body = created.json()
    assert body["shape"] == "multi"
    assert body["runnable"] is True

    sql = tmp_path / "sql"
    sql.mkdir()
    updated = client.put("/api/products/billing/topology", json={
        "shape": "multi",
        "components": [
            {"id": "sql", "name": "SQL", "kind": "sql", "path": str(sql),
             "order_hint": 10},
            {"id": "backend", "name": "API", "kind": "backend",
             "path": str(repo), "order_hint": 20},
        ],
    })
    assert updated.status_code == 200
    assert len(updated.json()["components"]) == 2

    snap = client.get("/api/state").json()
    assert any(p["name"] == "billing" for p in snap["products"])
    listed = client.get("/api/products").json()
    assert any(p["name"] == "billing" for p in listed)


def test_run_blocked_without_component_path(client):
    ctx = build_context(None)
    project = ctx.store.create_project("empty-prod", None)
    from agentic_org.docs.workspace import project_workspace
    project_workspace(ctx.root, "empty-prod", shape="mono")
    # Clear path on main component
    topo = load_topology(ctx.root, "empty-prod")
    assert topo
    topo.components[0].path = None
    save_topology(ctx.root, topo)
    ctx.store.set_project_repo(project["id"], None)  # type: ignore[arg-type]
    feature = ctx.store.create_feature(project["id"], "f1", "do something")
    res = client.post(f"/api/features/{feature['id']}/run", json={})
    assert res.status_code == 400
    assert "component" in res.json()["detail"].lower() or "path" in res.json()["detail"].lower()
