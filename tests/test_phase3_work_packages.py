"""Phase 3: work packages, multi-repo execute, suggestions, checklist."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agentic_org.context import build_context
from agentic_org.core.budget import Budget
from agentic_org.core.state_machine import WorkflowState
from agentic_org.products.execute import execute_work_packages, resolve_test_command
from agentic_org.products.suggestions import build_suggestions
from agentic_org.products.topology import Component, ProductTopology, save_topology
from agentic_org.products.work_packages import (
    WorkPackage,
    WorkPackagePlan,
    cross_component_checklist,
    save_plan,
    seed_from_topology,
    validate_plan,
)


def _git_repo(path: Path, files: dict[str, str]) -> None:
    path.mkdir(parents=True)
    for rel, content in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "p3@a.org"],
        ["git", "config", "user.name", "P3"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", "seed"],
    ):
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)


def test_work_package_schema_validation(tmp_path: Path):
    topo = ProductTopology(
        name="p",
        shape="multi",
        components=[
            Component(id="sql", name="SQL", kind="sql", path=str(tmp_path / "sql"),
                      order_hint=10, test_command="pytest -q"),
            Component(id="backend", name="API", kind="backend",
                      path=str(tmp_path / "be"), order_hint=20),
        ],
    )
    plan = seed_from_topology(topo, "ship feature")
    assert len(plan.packages) == 2
    assert validate_plan(plan, topo) == []
    bad = WorkPackagePlan(packages=[
        WorkPackage(id="x", component_id="missing"),
    ])
    assert validate_plan(bad, topo)


def test_resolve_test_command_honors_component():
    topo = ProductTopology(
        name="p",
        components=[
            Component(id="be", name="BE", kind="backend", path="/x",
                      test_command="python -m pytest -q"),
        ],
    )
    pkg = WorkPackage(id="wp-be", component_id="be")
    cmd = resolve_test_command(pkg, topo)
    assert cmd[:3] == ["python", "-m", "pytest"]


def test_multi_repo_execute_sql_then_backend(tmp_path: Path):
    sql = tmp_path / "sql"
    be = tmp_path / "backend"
    _git_repo(sql, {
        "schema.py": "VERSION = 0\n",
        "test_schema.py": (
            "from schema import VERSION\n\ndef test_v():\n    assert VERSION == 1\n"
        ),
    })
    _git_repo(be, {
        "api.py": "def ping():\n    return 'no'\n",
        "test_api.py": (
            "from api import ping\n\ndef test_ping():\n    assert ping() == 'ok'\n"
        ),
    })
    org = tmp_path / "org"
    org.mkdir()
    ctx = build_context(str(org))
    project = ctx.store.create_project("demo", str(be))
    topo = ProductTopology(
        name="demo",
        shape="multi",
        components=[
            Component(id="sql", name="SQL", kind="sql", path=str(sql),
                      order_hint=10,
                      test_command=f"{sys.executable} -m pytest -q --tb=line"),
            Component(id="backend", name="API", kind="backend", path=str(be),
                      order_hint=20,
                      test_command=f"{sys.executable} -m pytest -q --tb=line"),
        ],
        policies={"suggest_only": True,
                  "component_order_default": ["sql", "backend"]},
    )
    save_topology(org, topo)
    feature = ctx.store.create_feature(project["id"], "f1", "multi ship")
    feature_dir = org / "projects" / "demo" / "features" / "f1"
    artifacts = feature_dir / "artifacts"
    artifacts.mkdir(parents=True)
    plan = WorkPackagePlan(packages=[
        WorkPackage(
            id="wp-sql", component_id="sql", order=10,
            actions_file="wp_sql_actions.json",
            test_command=f"{sys.executable} -m pytest -q --tb=line",
        ),
        WorkPackage(
            id="wp-backend", component_id="backend", order=20,
            actions_file="wp_backend_actions.json",
            test_command=f"{sys.executable} -m pytest -q --tb=line",
        ),
    ])
    (artifacts / "wp_sql_actions.json").write_text(json.dumps([{
        "op": "write", "path": "schema.py", "content": "VERSION = 1\n",
    }]), encoding="utf-8")
    (artifacts / "wp_backend_actions.json").write_text(json.dumps([{
        "op": "write", "path": "api.py",
        "content": "def ping():\n    return 'ok'\n",
    }]), encoding="utf-8")
    save_plan(feature_dir, plan)

    multi = execute_work_packages(
        topology=topo,
        plan=plan,
        feature_dir=feature_dir,
        worktrees_root=org / ".agent-org" / "worktrees" / "demo",
        org_root=org,
        objective="multi ship",
    )
    assert multi.ok, multi.reason
    assert all(p.ok for p in multi.packages)
    reloaded = json.loads(
        (artifacts / "work_packages.json").read_text(encoding="utf-8")
    )
    assert all(p["status"] == "done" for p in reloaded["packages"])
    checklist = cross_component_checklist(
        WorkPackagePlan.from_dict(reloaded), topo,
    )
    assert checklist["ok"]


def test_suggestions_never_auto_approve(tmp_path: Path):
    topo = ProductTopology(
        name="demo",
        shape="multi",
        components=[
            Component(id="sql", name="SQL", kind="sql", path="/s", order_hint=10),
            Component(id="backend", name="BE", kind="backend", path="/b",
                      order_hint=20),
        ],
        policies={
            "suggest_only": True,
            "component_order_default": ["sql", "backend"],
        },
    )
    sug = build_suggestions(topo, workflow_state="PLANNED")
    assert sug["suggest_only"] is True
    assert sug["never_auto_approve"] is True
    assert sug["suggested_component_order"] == ["sql", "backend"]
    assert sug["next_agent"] == "backend-agent"


def test_api_suggestions_endpoint(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient

    from agentic_org.api.app import create_app

    org = tmp_path / "org"
    org.mkdir()
    ctx = build_context(str(org))
    ctx.store.create_project("demo", str(tmp_path / "repo"))
    (tmp_path / "repo").mkdir()
    save_topology(org, ProductTopology(
        name="demo",
        shape="multi",
        components=[
            Component(id="sql", name="SQL", kind="sql",
                      path=str(tmp_path / "repo"), order_hint=10),
            Component(id="backend", name="BE", kind="backend",
                      path=str(tmp_path / "repo"), order_hint=20),
        ],
    ))
    monkeypatch.setenv("AGENTIC_ORG_ROOT", str(org))
    client = TestClient(create_app())
    res = client.get("/api/products/demo/suggestions")
    assert res.status_code == 200
    body = res.json()
    assert body["never_auto_approve"] is True
    assert "sql" in body["suggested_component_order"]
