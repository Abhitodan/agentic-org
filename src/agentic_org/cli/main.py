"""agentctl: vendor-neutral CLI for the agentic software organization.

The CLI and the web command center share the same backend services and
SQLite state; nothing here is a separate code path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from ..brain.feature_brain import FeatureBrain
from ..context import build_context
from ..core.budget import Budget
from ..core.store import NotFound
from ..orchestrator.runner import PLAN_GATE, RELEASE_GATE
from ..repo_intel.mapper import summarize_repo_map
from ..workspace.git_ws import GitError, GitWorkspace

app = typer.Typer(help="Agentic Software Organization control CLI",
                  no_args_is_help=True)

root_option = typer.Option(None, "--root", help="Framework root (defaults to cwd search)")


def _echo(data) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


@app.command()
def init(root: Optional[str] = root_option):
    """Initialize the .agent-org state directory and database."""
    ctx = build_context(root)
    from ..core.events import Event
    ctx.events.append(Event(event_type="platform.initialized",
                            payload={"root": str(ctx.root)}))
    typer.echo(f"initialized agentic-org state at {ctx.root / '.agent-org' / 'state'}")


@app.command("create-project")
def create_project(
    name: str,
    repo: Optional[str] = typer.Option(None, "--repo"),
    shape: str = typer.Option("mono", "--shape", help="mono or multi"),
    root: Optional[str] = root_option,
):
    """Create a product (project), optionally with repo path and topology shape."""
    ctx = build_context(root)
    from ..docs.workspace import project_workspace
    from ..products.topology import load_topology, sync_repo_path_from_topology

    if shape not in ("mono", "multi"):
        typer.echo("shape must be mono or multi", err=True)
        raise typer.Exit(1)
    project = ctx.store.create_project(name, repo)
    project_dir = project_workspace(ctx.root, name, repo_path=repo, shape=shape)
    topo = load_topology(ctx.root, name)
    if topo:
        sync_repo_path_from_topology(ctx.store, project["id"], topo)
    from ..core.events import Event
    ctx.events.append(Event(event_type="project.created", project_id=project["id"],
                            payload={"name": name, "repo": repo, "shape": shape,
                                     "path": str(project_dir)}))
    _echo({**project, "topology": topo.to_dict() if topo else None})


@app.command("connect-repo")
def connect_repo(
    project: str,
    repo_path: str,
    component: str = typer.Option("main", "--component", help="Component id"),
    kind: str = typer.Option("main", "--kind"),
    root: Optional[str] = root_option,
):
    """Connect a repository path to a product component (updates product.yaml)."""
    ctx = build_context(root)
    from ..products.topology import (
        Component, ensure_topology, save_topology, sync_repo_path_from_topology,
    )
    prj = ctx.store.get_project(project)
    resolved = str(Path(repo_path).resolve())
    topo = ensure_topology(ctx.root, project, repo_path=None, shape="mono")
    existing = topo.component(component)
    topo.upsert_component(Component(
        id=component,
        name=(existing.name if existing else component),
        kind=kind or (existing.kind if existing else "main"),
        path=resolved,
        default_branch=(existing.default_branch if existing else "main"),
        test_command=(existing.test_command if existing else None),
        order_hint=(existing.order_hint if existing else 10),
    ))
    save_topology(ctx.root, topo)
    sync_repo_path_from_topology(ctx.store, prj["id"], topo)
    from ..core.events import Event
    ctx.events.append(Event(event_type="project.repo_connected",
                            project_id=prj["id"],
                            payload={"repo": resolved, "component": component,
                                     "topology": topo.to_dict()}))
    _echo(topo.to_dict())


@app.command("product-init")
def product_init(
    name: str,
    shape: str = typer.Option("mono", "--shape"),
    repo: Optional[str] = typer.Option(None, "--repo"),
    root: Optional[str] = root_option,
):
    """Admin: create or refresh product topology (mono|multi). Creates DB row if needed."""
    ctx = build_context(root)
    from ..docs.workspace import project_workspace
    from ..products.topology import ensure_topology, load_topology, sync_repo_path_from_topology

    if shape not in ("mono", "multi"):
        typer.echo("shape must be mono or multi", err=True)
        raise typer.Exit(1)
    try:
        prj = ctx.store.get_project(name)
    except NotFound:
        prj = ctx.store.create_project(name, repo)
    project_workspace(ctx.root, name, repo_path=repo, shape=shape)
    topo = ensure_topology(ctx.root, name, repo_path=repo, shape=shape)
    sync_repo_path_from_topology(ctx.store, prj["id"], topo)
    from ..core.events import Event
    ctx.events.append(Event(
        event_type="product.topology_initialized", project_id=prj["id"],
        payload=topo.to_dict(),
    ))
    _echo(topo.to_dict())


@app.command("product-show")
def product_show(name: str, root: Optional[str] = root_option):
    """Show product topology (components and policies)."""
    ctx = build_context(root)
    from ..products.topology import ensure_topology, sync_repo_path_from_topology

    prj = ctx.store.get_project(name)
    topo = ensure_topology(ctx.root, name, repo_path=prj.get("repo_path"))
    if prj.get("repo_path") and not topo.primary_path:
        sync_repo_path_from_topology(ctx.store, prj["id"], topo)
    _echo(topo.to_dict())


@app.command("product-set-component")
def product_set_component(
    product: str,
    component_id: str = typer.Argument(..., help="Component id e.g. backend"),
    path: Optional[str] = typer.Option(None, "--path"),
    kind: str = typer.Option("other", "--kind"),
    name: Optional[str] = typer.Option(None, "--name"),
    test_command: Optional[str] = typer.Option(None, "--test-command"),
    order: int = typer.Option(100, "--order"),
    root: Optional[str] = root_option,
):
    """Admin: add or update a product component in product.yaml."""
    ctx = build_context(root)
    from ..products.topology import (
        Component, ensure_topology, save_topology, sync_repo_path_from_topology,
    )
    prj = ctx.store.get_project(product)
    topo = ensure_topology(ctx.root, product, repo_path=prj.get("repo_path"))
    prev = topo.component(component_id)
    resolved = str(Path(path).resolve()) if path else (prev.path if prev else None)
    topo.upsert_component(Component(
        id=component_id,
        name=name or (prev.name if prev else component_id),
        kind=kind or (prev.kind if prev else "other"),
        path=resolved,
        default_branch=(prev.default_branch if prev else "main"),
        test_command=test_command if test_command is not None else (
            prev.test_command if prev else None),
        order_hint=order if order is not None else (prev.order_hint if prev else 100),
    ))
    save_topology(ctx.root, topo)
    sync_repo_path_from_topology(ctx.store, prj["id"], topo)
    from ..core.events import Event
    ctx.events.append(Event(
        event_type="product.component_updated", project_id=prj["id"],
        payload={"component": component_id, "topology": topo.to_dict()},
    ))
    _echo(topo.to_dict())


@app.command("create-feature")
def create_feature(project: str, name: str,
                   objective: str = typer.Option(..., "--objective"),
                   root: Optional[str] = root_option):
    """Create a feature folder, brain, stub docs, and document manifest."""
    ctx = build_context(root)
    from ..docs.workspace import FeatureWorkspace, project_workspace
    prj = ctx.store.get_project(project)
    project_workspace(ctx.root, project, repo_path=prj.get("repo_path"))
    feature = ctx.store.create_feature(prj["id"], name, objective)
    ws = FeatureWorkspace(ctx.root, project, name)
    ws.create(feature["id"], objective)
    # Index immediately so search works before workflow runs.
    index_report = ctx.indexer.index_feature(project, name)
    from ..core.events import Event
    ctx.events.append(Event(event_type="feature.created", project_id=prj["id"],
                            feature_id=feature["id"],
                            payload={"name": name, "objective": objective,
                                     "docs_indexed": index_report.files_indexed}))
    _echo({**feature, "folder": str(ws.dir), "index": index_report.to_dict()})


@app.command("map-repository")
def map_repository(repo_path: str, out: Optional[str] = typer.Option(None, "--out"),
                   root: Optional[str] = root_option):
    """Deterministically map a repository via the repository-analysis skill (no LLM)."""
    ctx = build_context(root)
    from ..skills import SkillInvocationError, invoke_skill

    try:
        result = invoke_skill(
            ctx.root,
            "repository-analysis",
            args={"repo_path": repo_path, "out_dir": out},
            events=ctx.events,
            agent_role="repository-agent",
        )
    except SkillInvocationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if out:
        for path in result.get("artifacts") or []:
            typer.echo(f"saved {path}")
    typer.echo(result.get("summary") or summarize_repo_map(result.get("repo_map") or {}))


@app.command("skill-list")
def skill_list(root: Optional[str] = root_option,
               project: Optional[str] = typer.Option(None, "--project"),
               category: Optional[str] = typer.Option(
                   None, "--category", help="Only skills in this category"),
               persona: Optional[str] = typer.Option(
                   None, "--persona", help="Only skills bound to this agent role"),
               grouped: bool = typer.Option(
                   False, "--grouped", help="Group output by category")):
    """List installed skills (project overrides org)."""
    ctx = build_context(root)
    from ..skills import discover_skills

    manifests = [
        s for s in discover_skills(ctx.root, project).values()
        if (category is None or s.category == category)
        and (persona is None or persona in s.personas)
    ]
    if not grouped:
        _echo([s.to_dict() for s in manifests])
        return
    by_category: dict[str, list[dict]] = {}
    for manifest in sorted(manifests, key=lambda m: (m.category, m.name)):
        by_category.setdefault(manifest.category or "uncategorized", []).append(
            manifest.to_dict()
        )
    _echo(by_category)


@app.command("skill-show")
def skill_show(name: str, root: Optional[str] = root_option,
               project: Optional[str] = typer.Option(None, "--project")):
    """Show one skill manifest and readiness."""
    ctx = build_context(root)
    from ..skills import SkillNotFound, load_skill

    try:
        skill = load_skill(ctx.root, name, project)
    except SkillNotFound as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    data = skill.to_dict()
    data["body_preview"] = skill.body[:500]
    _echo(data)


@app.command("skill-run")
def skill_run(
    name: str,
    repo_path: Optional[str] = typer.Option(None, "--repo"),
    out: Optional[str] = typer.Option(None, "--out"),
    root: Optional[str] = root_option,
    project: Optional[str] = typer.Option(None, "--project"),
):
    """Run a skill entrypoint (Phase 0: repository-analysis supported)."""
    ctx = build_context(root)
    from ..skills import SkillInvocationError, invoke_skill

    args: dict = {}
    if repo_path:
        args["repo_path"] = repo_path
    if out:
        args["out_dir"] = out
    try:
        result = invoke_skill(
            ctx.root,
            name,
            args=args,
            events=ctx.events,
            project_name=project,
            agent_role="cli",
        )
    except SkillInvocationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    # Avoid dumping huge repo_map to terminal by default
    slim = {k: v for k, v in result.items() if k != "repo_map"}
    _echo(slim)


def _skill_eval_fixture(root: Path) -> Path:
    fixture = root / "examples" / "enrollment-sample"
    if fixture.is_dir():
        return fixture
    fixture = root / ".agent-org" / "state" / "skill-eval-fixture"
    (fixture / "pkg").mkdir(parents=True, exist_ok=True)
    (fixture / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (fixture / "tests").mkdir(exist_ok=True)
    (fixture / "tests" / "test_smoke.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    (fixture / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    req = fixture / "requirements.txt"
    if not req.is_file():
        req.write_text("requests>=2.0\n", encoding="utf-8")
    return fixture


@app.command("skill-install")
def skill_install(
    target: str = typer.Argument(
        ..., help="cursor | claude | codex | project"),
    copy: bool = typer.Option(
        False, "--copy", help="Force copy instead of symlink"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show paths without installing"),
    root: Optional[str] = root_option,
):
    """Install org skills into a coding-agent skills directory."""
    ctx = build_context(root)
    from .skill_install import install_skills

    normalized = target.strip().lower()
    if normalized not in {"cursor", "claude", "codex", "project"}:
        typer.echo(
            "target must be one of: cursor, claude, codex, project", err=True,
        )
        raise typer.Exit(1)
    try:
        plan = install_skills(
            ctx.root, normalized, copy=copy, dry_run=dry_run,  # type: ignore[arg-type]
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    _echo({
        "target": plan.target,
        "source": str(plan.source),
        "destination": str(plan.destination),
        "mode": plan.mode,
        "skill_count": plan.skill_count,
        "next": (
            f"Point your coding agent at {plan.destination} "
            "(symlink/copy preserves scripts + SKILL.md)."
        ),
    })


@app.command("skill-eval")
def skill_eval(
    name: str = typer.Argument("repository-analysis", help="Skill name to eval"),
    root: Optional[str] = root_option,
):
    """Run the built-in eval for a skill (offline fixtures)."""
    ctx = build_context(root)
    from ..skills import SkillInvocationError, invoke_skill

    from .skill_evals import SKILL_EVALS

    fixture = _skill_eval_fixture(ctx.root)
    spec = SKILL_EVALS.get(name)
    if spec is None:
        typer.echo(
            f"no eval registered for {name!r} yet; "
            f"registered: {', '.join(sorted(SKILL_EVALS))}",
            err=True,
        )
        raise typer.Exit(1)
    args = spec.build_args(fixture, ctx.root)
    expect_evidence = spec.expect_evidence

    try:
        result = invoke_skill(
            ctx.root,
            name,
            args=args,
            events=ctx.events,
            agent_role="skill-eval",
        )
    except SkillInvocationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    ok = result.get("evidence") == expect_evidence and spec.check(result)

    _echo({
        "skill": name,
        "category": spec.category,
        "passed": ok,
        "evidence": result.get("evidence"),
        "fixture": str(fixture),
        "ok": result.get("ok"),
    })
    if not ok:
        raise typer.Exit(1)


@app.command()
def run(project: str, feature: str,
        budget_usd: float = typer.Option(5.0, "--budget-usd"),
        max_iterations: int = typer.Option(12, "--max-iterations"),
        root: Optional[str] = root_option):
    """Start the Mode A feature workflow (runs until the human gate or a block)."""
    ctx = build_context(root)
    from ..products.topology import ensure_topology, sync_repo_path_from_topology
    prj = ctx.store.get_project(project)
    feat = ctx.store.get_feature(prj["id"], feature)
    topo = ensure_topology(ctx.root, project, repo_path=prj.get("repo_path"))
    sync_repo_path_from_topology(ctx.store, prj["id"], topo)
    prj = ctx.store.get_project(project)
    repo = topo.primary_path or prj.get("repo_path")
    if not repo:
        typer.echo(
            "product has no component path; use product-set-component or connect-repo",
            err=True,
        )
        raise typer.Exit(1)
    from ..retrieval.packer import ensure_feature_indexed
    index_report = ensure_feature_indexed(ctx.indexer, project, feature, force=True)
    budget = Budget(maximum_cost_usd=budget_usd, maximum_iterations=max_iterations)
    workflow = ctx.store.create_workflow(feat["id"], "existing-feature", budget)
    result = ctx.runner.start(project, feature, feat["objective"],
                              repo, workflow["id"])
    final = ctx.store.get_workflow(workflow["id"])
    _echo({
        "workflow_id": workflow["id"],
        "state": final["state"],
        "blocked_reason": result.get("blocked_reason"),
        "notes": result.get("notes", []),
        "docs_indexed_chunks": index_report,
        "next": ("approve with: agentctl approve " + workflow["id"]
                 if final["state"] == "AWAITING_DECISION" else None),
    })


@app.command()
def approve(workflow_id: str,
            gate: str = typer.Option(PLAN_GATE, "--gate",
                                     help="plan-approval or release-approval"),
            by: str = typer.Option("human", "--by"),
            reason: str = typer.Option("", "--reason"),
            root: Optional[str] = root_option):
    """Approve a pending human gate for a workflow."""
    ctx = build_context(root)
    decision = ctx.store.decide_approval(workflow_id, gate, True, by, reason)
    from ..core.events import Event
    ctx.events.append(Event(event_type="approval.granted", workflow_id=workflow_id,
                            payload={"gate": gate, "by": by, "reason": reason}))
    # Rebuild graph memory after significant decisions.
    ctx.memory.rebuild(ctx.store, ctx.events, ctx.root)
    _echo(decision)


@app.command()
def reject(workflow_id: str,
           gate: str = typer.Option(PLAN_GATE, "--gate"),
           by: str = typer.Option("human", "--by"),
           reason: str = typer.Option("", "--reason"),
           root: Optional[str] = root_option):
    """Reject a pending human gate; the workflow stays awaiting a decision."""
    ctx = build_context(root)
    decision = ctx.store.decide_approval(workflow_id, gate, False, by, reason)
    from ..core.events import Event
    ctx.events.append(Event(event_type="approval.rejected", workflow_id=workflow_id,
                            payload={"gate": gate, "by": by, "reason": reason}))
    _echo(decision)


@app.command()
def resume(workflow_id: str,
           clear_block: bool = typer.Option(
               False, "--clear-block",
               help="Clear a prior blocked_reason and retry (e.g. after fixing dirty tree)"),
           root: Optional[str] = root_option):
    """Resume a workflow past an approved human gate."""
    ctx = build_context(root)
    result = ctx.runner.resume(workflow_id, clear_block=clear_block)
    final = ctx.store.get_workflow(workflow_id)
    _echo({"workflow_id": workflow_id, "state": final["state"],
           "blocked_reason": result.get("blocked_reason") if result else None})


@app.command()
def status(root: Optional[str] = root_option):
    """Show projects, features, workflows, and pending approvals."""
    ctx = build_context(root)
    _echo({
        "root": str(ctx.root),
        "projects": ctx.store.list_projects(),
        "features": ctx.store.list_features(),
        "workflows": [
            {k: w[k] for k in ("id", "feature_id", "kind", "state", "updated_at")}
            for w in ctx.store.list_workflows()
        ],
        "pending_approvals": ctx.store.list_approvals("pending"),
        "model_gateway_available": ctx.gateway.available(),
        "model_provider": ctx.gateway.provider,
        "model_base_url": ctx.gateway.base_url,
    })


@app.command()
def audit(workflow: Optional[str] = typer.Option(None, "--workflow"),
          event_type: Optional[str] = typer.Option(None, "--type"),
          limit: int = typer.Option(50, "--limit"),
          root: Optional[str] = root_option):
    """List audit events (append-only, hash-chained)."""
    ctx = build_context(root)
    _echo(ctx.events.list(workflow_id=workflow, event_type=event_type, limit=limit))


@app.command()
def verify(root: Optional[str] = root_option):
    """Verify the integrity of the event hash chain."""
    ctx = build_context(root)
    ok, bad = ctx.events.verify_chain()
    _echo({"chain_valid": ok, "first_invalid_event": bad,
           "totals": ctx.events.totals()})
    if not ok:
        raise typer.Exit(1)


@app.command()
def budget(workflow_id: str, root: Optional[str] = root_option):
    """Show budget, spend, and remaining headroom for a workflow."""
    ctx = build_context(root)
    workflow = ctx.store.get_workflow(workflow_id)
    b, s = ctx.store.load_budget(workflow)
    from ..core.budget import BudgetTracker
    tracker = BudgetTracker(b, s)
    _echo({"budget": b.model_dump(), "spent": s.model_dump(),
           "remaining": tracker.remaining(),
           "requires_human_approval": tracker.requires_human_approval()})


@app.command()
def checkpoint(repo_path: str, kind: str = typer.Option("manual", "--kind"),
               note: str = typer.Option("", "--note"),
               root: Optional[str] = root_option):
    """Create a git checkpoint (commit + checkpoint tag) in a repository."""
    ws = GitWorkspace(Path(repo_path))
    try:
        checkpoint_id = ws.checkpoint(kind, note)
    except GitError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    _echo({"checkpoint_id": checkpoint_id, "commit": ws.current_commit()})


@app.command()
def revert(repo_path: str, checkpoint_id: str, root: Optional[str] = root_option):
    """Restore a repository working tree to a checkpoint (history preserved)."""
    ws = GitWorkspace(Path(repo_path))
    try:
        commit = ws.restore_checkpoint(checkpoint_id)
    except GitError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    _echo({"restored_to": commit, "checkpoint_id": checkpoint_id})


@app.command()
def inspect(workflow_id: str, root: Optional[str] = root_option):
    """Full picture of one workflow: state, runs, events, cost, checkpoints."""
    ctx = build_context(root)
    try:
        workflow = ctx.store.get_workflow(workflow_id)
    except NotFound as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    _echo({
        "workflow": workflow,
        "agent_runs": ctx.store.list_agent_runs(workflow_id),
        "checkpoints": ctx.store.list_checkpoints(workflow_id),
        "events": ctx.events.list(workflow_id=workflow_id, limit=100),
        "totals": ctx.events.totals(workflow_id),
    })


@app.command("memory-rebuild")
def memory_rebuild(root: Optional[str] = root_option):
    """Rebuild graph memory projection from events + operational tables."""
    ctx = build_context(root)
    counts = ctx.memory.rebuild(ctx.store, ctx.events, ctx.root)
    _echo({"rebuilt": True, **counts})


@app.command("memory-query")
def memory_query(query: str,
                 kind: Optional[str] = typer.Option(None, "--kind"),
                 root: Optional[str] = root_option):
    """Search graph memory nodes by label/props substring."""
    ctx = build_context(root)
    kinds = [kind] if kind else None
    hits = ctx.memory.search(query, kinds=kinds)
    _echo([{
        "node_id": h.node_id, "kind": h.kind, "label": h.label, "props": h.props,
    } for h in hits])


@app.command("docs-maintain")
def docs_maintain(project: str, feature: str, root: Optional[str] = root_option):
    """Ensure feature folder structure and stub managed documents."""
    ctx = build_context(root)
    from ..docs.workspace import FeatureWorkspace
    report = FeatureWorkspace(ctx.root, project, feature).maintain()
    from ..core.events import Event
    ctx.events.append(Event(
        event_type="docs.maintained",
        payload={"project": project, "feature": feature,
                 "created_stubs": report.get("created_stubs")},
    ))
    _echo(report)


@app.command("docs-list")
def docs_list(project: str, feature: str, root: Optional[str] = root_option):
    """List managed and discovered documents for a feature."""
    ctx = build_context(root)
    from ..docs.workspace import FeatureWorkspace
    _echo(FeatureWorkspace(ctx.root, project, feature).list_docs())


@app.command("docs-write")
def docs_write(project: str, feature: str, kind: str,
               file: Path = typer.Option(..., "--file", exists=True, readable=True),
               root: Optional[str] = root_option):
    """Write/update a feature document from a local file and re-index."""
    ctx = build_context(root)
    from ..docs.workspace import FeatureWorkspace
    content = Path(file).read_text(encoding="utf-8")
    ws = FeatureWorkspace(ctx.root, project, feature)
    path = ws.write_doc(kind, content, source="human", status="draft")
    index_report = ctx.indexer.index_feature(project, feature)
    from ..core.events import Event
    ctx.events.append(Event(
        event_type="docs.updated",
        payload={"project": project, "feature": feature, "kind": kind,
                 "path": str(path)},
    ))
    _echo({"path": str(path), "index": index_report.to_dict()})


@app.command("docs-index")
def docs_index(project: Optional[str] = typer.Option(None, "--project"),
               feature: Optional[str] = typer.Option(None, "--feature"),
               root: Optional[str] = root_option):
    """Build PageIndex trees + vector embeddings for feature docs."""
    ctx = build_context(root)
    if project and feature:
        report = ctx.indexer.index_feature(project, feature)
        _echo(report.to_dict())
    else:
        _echo({"indexed": ctx.indexer.index_all_features()})


@app.command("docs-search")
def docs_search(query: str,
                mode: str = typer.Option("hybrid", "--mode",
                                         help="vector|pageindex|hybrid"),
                project: Optional[str] = typer.Option(None, "--project"),
                feature: Optional[str] = typer.Option(None, "--feature"),
                llm: bool = typer.Option(False, "--llm",
                                         help="Use LLM tree reasoning for PageIndex"),
                root: Optional[str] = root_option):
    """Search feature documentation via vectors and/or PageIndex trees."""
    ctx = build_context(root)
    _echo(ctx.indexer.search(
        query, mode=mode, project=project, feature=feature, use_llm=llm,
    ))


@app.command()
def serve(host: str = typer.Option("127.0.0.1", "--host"),
          port: int = typer.Option(8787, "--port"),
          root: Optional[str] = root_option):
    """Serve the command-center API and dashboard."""
    import os
    import sys

    import uvicorn
    if root:
        os.environ["AGENTIC_ORG_ROOT"] = str(Path(root).resolve())
    bound_nonlocal = host not in {"127.0.0.1", "localhost", "::1"}
    token_set = bool(os.environ.get("AGENTIC_ORG_API_TOKEN", "").strip())
    if bound_nonlocal and not token_set:
        print(
            "ERROR: refusing to serve on non-loopback host without "
            "AGENTIC_ORG_API_TOKEN. Set the token or bind to 127.0.0.1.",
            file=sys.stderr,
        )
        raise typer.Exit(2)
    uvicorn.run("agentic_org.api.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    app()
