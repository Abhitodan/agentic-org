"""Command-center API. Same services and state as the CLI.

Adds the live operations surface the web command center needs:
- `/api/state` aggregated snapshot (one round trip)
- `/api/stream` server-sent events for real-time push
- action endpoints (run, resume, approve, reject, revert) so an operator can
  act on a workflow, not just watch it

Long-running actions execute on worker threads with their own database
connection; progress is observable through the event store, never faked.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..context import build_context
from ..core.budget import Budget, BudgetTracker
from ..core.events import Event
from ..core.ids import new_id, utc_now
from ..core.store import NotFound
from ..docs.workspace import DOC_KINDS
from ..orchestrator.runner import PLAN_GATE, RELEASE_GATE
from ..workspace.git_ws import GitError, GitWorkspace

def _package_ui_candidates() -> list[Path]:
    """Resolve command-center dir for editable and non-editable installs."""
    here = Path(__file__).resolve()
    return [
        here.parents[3] / "apps" / "command-center",  # .../agentic-org/src/agentic_org/api
        here.parents[2].parent / "apps" / "command-center",
        Path.cwd() / "apps" / "command-center",
    ]


PACKAGE_UI = next(
    (p for p in _package_ui_candidates() if (p / "index.html").exists()),
    _package_ui_candidates()[0],
)

# node key, state reached, owning role, completion event type
PIPELINE = [
    ("intake", "INTAKE", "intake-agent", "intake.classified"),
    ("map_repository", "DISCOVERY", "repository-agent", "repository.mapped"),
    ("create_brain", "RESEARCHING", "repository-agent", "brain.updated"),
    ("draft_charter", "OPTIONS_READY", "product-manager-agent", "charter.drafted"),
    ("request_decision", "AWAITING_DECISION", "human", "approval.requested"),
    ("plan", "PLANNED", "planning-agent", "plan.created"),
    ("implement", "VALIDATING", "backend-agent", "implementation.succeeded"),
    ("merge", "REVIEWING", "release-agent", "merge.succeeded"),
    ("request_release", "AWAITING_APPROVAL", "human", "release.approval.requested"),
    ("release", "COMPLETED", "release-agent", "release.succeeded"),
]

DOCUMENTS = {
    k: v for k, v in DOC_KINDS.items() if k != "manifest"
}

_JOBS_LOCK = threading.Lock()
_CHAIN_CACHE: dict[str, Any] = {"checked_at": 0.0, "valid": True, "bad": None}
_CHAIN_TTL_SECONDS = 10.0


class ApprovalDecision(BaseModel):
    approve: bool
    decided_by: str = "human"
    reason: str = ""
    gate: str = PLAN_GATE


class RunRequest(BaseModel):
    budget_usd: float = 8.0
    max_iterations: int = 12
    started_by: str = "command-center"


class RevertRequest(BaseModel):
    checkpoint_id: str
    decided_by: str = "command-center"


class ProductCreateRequest(BaseModel):
    name: str
    shape: str = "mono"
    repo_path: str | None = None


class ComponentBody(BaseModel):
    id: str
    name: str | None = None
    kind: str = "other"
    path: str | None = None
    default_branch: str = "main"
    test_command: str | None = None
    order_hint: int = 100


class TopologyUpdateRequest(BaseModel):
    shape: str | None = None
    components: list[ComponentBody] | None = None


def _record_job(root: str | Path, job: dict[str, Any]) -> None:
    with _JOBS_LOCK:
        store = build_context(str(root)).store
        store.upsert_job(job)


def _update_job(root: str | Path, job_id: str, **fields: Any) -> None:
    with _JOBS_LOCK:
        store = build_context(str(root)).store
        store.update_job(job_id, **fields)


def _active_jobs(root: str | Path | None = None) -> list[dict[str, Any]]:
    with _JOBS_LOCK:
        store = build_context(str(root) if root else None).store
        return store.list_jobs(limit=12)


def _running_workflow_ids(root: str | Path | None = None) -> set[str]:
    with _JOBS_LOCK:
        store = build_context(str(root) if root else None).store
        return store.running_workflow_ids()


def _api_token() -> str:
    return os.environ.get("AGENTIC_ORG_API_TOKEN", "").strip()


def _request_authorized(request: Request) -> bool:
    """Accept Bearer or X-Agentic-Org-Token when AGENTIC_ORG_API_TOKEN is set."""
    token = _api_token()
    if not token:
        return True
    auth = request.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True
    return request.headers.get("X-Agentic-Org-Token", "") == token


def create_app() -> FastAPI:
    api = FastAPI(title="agentic-org command center", version="0.2.0")

    @api.middleware("http")
    async def optional_mutating_api_auth(request: Request, call_next):
        """When AGENTIC_ORG_API_TOKEN is set, require it for mutating /api/* calls.

        GET/HEAD/OPTIONS stay open so the local dashboard and SSE can observe
        state without custom EventSource headers. Unset token preserves the
        prior local-trust model (default bind is 127.0.0.1).
        """
        if (
            request.url.path.startswith("/api/")
            and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
            and not _request_authorized(request)
        ):
            return JSONResponse(
                {"detail": "unauthorized: set Authorization: Bearer <AGENTIC_ORG_API_TOKEN>"},
                status_code=401,
            )
        return await call_next(request)

    def ctx():
        return build_context(None)

    def ui_dir() -> Path:
        candidates = [
            *_package_ui_candidates(),
            ctx().root / "apps" / "command-center",
        ]
        for candidate in candidates:
            if (
                (candidate / "index.html").exists()
                and (candidate / "app.js").exists()
            ):
                return candidate
        raise HTTPException(404, "command-center UI assets not found")

    def chain_status(store_ctx) -> tuple[bool, str | None]:
        now = time.monotonic()
        if now - _CHAIN_CACHE["checked_at"] > _CHAIN_TTL_SECONDS:
            valid, bad = store_ctx.events.verify_chain()
            _CHAIN_CACHE.update({"checked_at": now, "valid": valid, "bad": bad})
        return _CHAIN_CACHE["valid"], _CHAIN_CACHE["bad"]

    # -- background workers -------------------------------------------------

    def _worker_run(root: str, project_name: str, feature_name: str,
                    objective: str, repo_path: str, workflow_id: str,
                    job_id: str) -> None:
        try:
            worker_ctx = build_context(root)
            worker_ctx.runner.start(project_name, feature_name, objective,
                                    repo_path, workflow_id)
            final = worker_ctx.store.get_workflow(workflow_id)
            _update_job(root, job_id, status="succeeded", finished_at=utc_now(),
                        result_state=final["state"])
        except Exception as exc:  # surfaced to the operator, never swallowed
            _update_job(root, job_id, status="failed", finished_at=utc_now(),
                        error=f"{type(exc).__name__}: {exc}")

    def _worker_resume(root: str, workflow_id: str, job_id: str) -> None:
        try:
            worker_ctx = build_context(root)
            worker_ctx.runner.resume(workflow_id)
            final = worker_ctx.store.get_workflow(workflow_id)
            _update_job(root, job_id, status="succeeded", finished_at=utc_now(),
                        result_state=final["state"])
        except Exception as exc:
            _update_job(root, job_id, status="failed", finished_at=utc_now(),
                        error=f"{type(exc).__name__}: {exc}")

    def _spawn(target, args, kind: str, workflow_id: str, label: str) -> dict[str, Any]:
        root = str(ctx().root)
        job = {
            "id": new_id("job"), "kind": kind, "workflow_id": workflow_id,
            "label": label, "status": "running", "started_at": utc_now(),
            "finished_at": None, "error": None, "result_state": None,
        }
        _record_job(root, job)
        thread = threading.Thread(
            target=target, args=(*args, job["id"]), daemon=True)
        thread.start()
        return job

    # -- snapshot -----------------------------------------------------------

    def pipeline_for(workflow_id: str, workflow_state: str,
                     events: list[dict[str, Any]], is_running: bool,
                     plan_granted: bool,
                     release_granted: bool) -> list[dict[str, Any]]:
        seen = {ev["event_type"] for ev in events}
        nodes: list[dict[str, Any]] = []
        first_open = True
        awaiting_states = {"AWAITING_DECISION", "AWAITING_APPROVAL"}
        for key, state, role, done_event in PIPELINE:
            done = done_event in seen
            status = "done" if done else "pending"
            if not done and first_open:
                first_open = False
                if workflow_state == "BLOCKED":
                    status = "blocked"
                elif is_running:
                    status = "active"
                elif workflow_state in awaiting_states:
                    status = "awaiting"
            if key == "request_decision" and done and not plan_granted \
                    and workflow_state == "AWAITING_DECISION":
                status = "awaiting"
            if key == "request_release" and done and not release_granted \
                    and workflow_state == "AWAITING_APPROVAL":
                status = "awaiting"
            nodes.append({"key": key, "state": state, "role": role,
                          "status": status, "gate": (
                              PLAN_GATE if key == "request_decision"
                              else RELEASE_GATE if key == "request_release"
                              else None)})
        return nodes

    def build_snapshot() -> dict[str, Any]:
        c = ctx()
        valid, bad = chain_status(c)
        projects = c.store.list_projects()
        project_by_id = {p["id"]: p for p in projects}
        features = c.store.list_features()
        feature_by_id = {f["id"]: f for f in features}
        running = _running_workflow_ids(c.root)

        workflows = []
        for workflow in c.store.list_workflows():
            budget, spent = c.store.load_budget(workflow)
            tracker = BudgetTracker(budget, spent)
            feature = feature_by_id.get(workflow["feature_id"], {})
            project = project_by_id.get(feature.get("project_id"), {})
            wf_events = c.events.list(workflow_id=workflow["id"], limit=200)
            plan_granted = c.store.approval_granted(workflow["id"], PLAN_GATE)
            release_granted = c.store.approval_granted(
                workflow["id"], RELEASE_GATE)
            is_running = workflow["id"] in running
            blocked_event = next(
                (ev for ev in wf_events if ev["event_type"] == "workflow.blocked"),
                None)
            workflows.append({
                "id": workflow["id"],
                "kind": workflow["kind"],
                "state": workflow["state"],
                "created_at": workflow["created_at"],
                "updated_at": workflow["updated_at"],
                "feature_id": workflow["feature_id"],
                "feature_name": feature.get("name"),
                "project_name": project.get("name"),
                "objective": feature.get("objective"),
                "repo_path": project.get("repo_path"),
                "budget": budget.model_dump(),
                "spent": spent.model_dump(),
                "remaining": tracker.remaining(),
                "approval_granted": plan_granted,
                "release_approval_granted": release_granted,
                "is_running": is_running,
                "blocked_reason": (blocked_event or {}).get("payload", {}).get("reason"),
                "pipeline": pipeline_for(
                    workflow["id"], workflow["state"], wf_events, is_running,
                    plan_granted, release_granted),
                "agent_runs": c.store.list_agent_runs(workflow["id"]),
                "checkpoints": c.store.list_checkpoints(workflow["id"]),
                "event_count": len(wf_events),
            })
        workflows.sort(key=lambda w: w["updated_at"], reverse=True)

        feature_rows = []
        for feature in features:
            project = project_by_id.get(feature["project_id"], {})
            related = [w for w in workflows if w["feature_id"] == feature["id"]]
            feature_rows.append({
                **feature,
                "project_name": project.get("name"),
                "repo_path": project.get("repo_path"),
                "workflow_count": len(related),
                "latest_workflow": related[0]["id"] if related else None,
                "latest_state": related[0]["state"] if related else feature["state"],
            })

        totals = c.events.totals()
        cost_rows = c.store.conn.execute(
            """SELECT w.id AS workflow_id, w.state, f.name AS feature,
                      COALESCE(SUM(e.tokens_in),0) AS tokens_in,
                      COALESCE(SUM(e.tokens_out),0) AS tokens_out,
                      COALESCE(SUM(e.cost_usd),0) AS cost_usd
               FROM workflows w
               JOIN features f ON f.id = w.feature_id
               LEFT JOIN events e ON e.workflow_id = w.id
               GROUP BY w.id ORDER BY w.created_at DESC"""
        ).fetchall()

        from ..products.topology import ensure_topology

        product_rows = []
        for project in projects:
            topo = ensure_topology(
                c.root, project["name"], repo_path=project.get("repo_path"),
            )
            product_rows.append({
                "id": project["id"],
                "name": project["name"],
                "repo_path": topo.primary_path or project.get("repo_path"),
                "created_at": project.get("created_at"),
                **topo.to_dict(),
            })

        return {
            "server_time": utc_now(),
            "system": {
                "root": str(c.root),
                "event_chain_valid": valid,
                "first_invalid_event": bad,
                "model_gateway_available": c.gateway.available(),
                "model_provider": c.gateway.provider,
                "model_base_url": c.gateway.base_url,
                "model_classes": {
                    name: spec.get("model")
                    for name, spec in c.gateway.config.get("classes", {}).items()
                },
            },
            "projects": projects,
            "products": product_rows,
            "features": feature_rows,
            "workflows": workflows,
            "approvals": c.store.list_approvals(),
            "pending_approvals": c.store.list_approvals("pending"),
            "events": c.events.list(limit=60),
            "agent_runs": c.store.list_agent_runs()[:20],
            "totals": totals,
            "costs": [dict(r) for r in cost_rows],
            "jobs": _active_jobs(c.root),
        }

    # -- UI -----------------------------------------------------------------

    # Operators must never see a stale console after an upgrade, so UI assets
    # are served uncached.
    NO_STORE = {"Cache-Control": "no-store, max-age=0"}

    @api.get("/")
    def dashboard():
        return FileResponse(ui_dir() / "index.html", headers=NO_STORE)

    @api.get("/assets/{filepath:path}")
    def asset(filepath: str):
        """Serve UI assets; allow only top-level files or vendor/*."""
        parts = Path(filepath).parts
        if (
            not parts
            or ".." in parts
            or any(p.startswith(".") for p in parts)
            or (len(parts) > 1 and parts[0] != "vendor")
            or len(parts) > 2
        ):
            raise HTTPException(400, "invalid asset path")
        path = (ui_dir() / Path(*parts)).resolve()
        try:
            path.relative_to(ui_dir().resolve())
        except ValueError as exc:
            raise HTTPException(400, "invalid asset path") from exc
        if not path.is_file():
            raise HTTPException(404, f"asset not found: {filepath}")
        return FileResponse(path, headers=NO_STORE)

    # -- read endpoints -----------------------------------------------------

    @api.get("/health")
    def health():
        c = ctx()
        ok, bad = c.events.verify_chain()
        return {"status": "ok", "root": str(c.root), "event_chain_valid": ok,
                "first_invalid_event": bad,
                "model_gateway_available": c.gateway.available(),
                "model_provider": c.gateway.provider}

    @api.get("/api/state")
    def state():
        return build_snapshot()

    @api.get("/api/stream")
    async def stream():
        async def generator():
            last_payload = None
            while True:
                snapshot = await asyncio.to_thread(build_snapshot)
                payload = json.dumps(snapshot, default=str)
                if payload != last_payload:
                    last_payload = payload
                    yield f"event: state\ndata: {payload}\n\n"
                else:
                    yield ": keepalive\n\n"
                await asyncio.sleep(1.5)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                     "X-Accel-Buffering": "no"},
        )

    @api.get("/projects")
    def projects():
        return ctx().store.list_projects()

    @api.get("/api/products")
    def list_products():
        c = ctx()
        from ..products.topology import ensure_topology
        rows = []
        for project in c.store.list_projects():
            topo = ensure_topology(
                c.root, project["name"], repo_path=project.get("repo_path"),
            )
            rows.append({
                "id": project["id"],
                "name": project["name"],
                "repo_path": topo.primary_path or project.get("repo_path"),
                **topo.to_dict(),
            })
        return rows

    @api.post("/api/products")
    def create_product(body: ProductCreateRequest):
        c = ctx()
        from ..docs.workspace import project_workspace
        from ..products.topology import (
            ensure_topology, sync_repo_path_from_topology,
        )
        if body.shape not in ("mono", "multi"):
            raise HTTPException(400, "shape must be mono or multi")
        try:
            c.store.get_project(body.name)
            raise HTTPException(409, f"product already exists: {body.name}")
        except NotFound:
            pass
        project = c.store.create_project(body.name, body.repo_path)
        project_workspace(
            c.root, body.name, repo_path=body.repo_path, shape=body.shape,
        )
        topo = ensure_topology(
            c.root, body.name, repo_path=body.repo_path, shape=body.shape,
        )
        sync_repo_path_from_topology(c.store, project["id"], topo)
        c.events.append(Event(
            event_type="product.created", project_id=project["id"],
            payload=topo.to_dict(),
        ))
        return {"id": project["id"], **topo.to_dict()}

    @api.get("/api/products/{name}")
    def get_product(name: str):
        c = ctx()
        from ..products.topology import ensure_topology
        try:
            project = c.store.get_project(name)
        except NotFound:
            raise HTTPException(404, f"product not found: {name}")
        topo = ensure_topology(
            c.root, name, repo_path=project.get("repo_path"),
        )
        return {"id": project["id"], **topo.to_dict()}

    @api.get("/api/products/{name}/suggestions")
    def product_suggestions(
        name: str,
        feature_id: str | None = None,
        workflow_id: str | None = None,
    ):
        """Autonomy A suggestion rail — never auto-approves."""
        c = ctx()
        from ..products.suggestions import build_suggestions
        from ..products.topology import ensure_topology
        try:
            project = c.store.get_project(name)
        except NotFound:
            raise HTTPException(404, f"product not found: {name}")
        topo = ensure_topology(
            c.root, name, repo_path=project.get("repo_path"),
        )
        wf_state = None
        if workflow_id:
            try:
                wf_state = c.store.get_workflow(workflow_id)["state"]
            except NotFound:
                wf_state = None
        return build_suggestions(
            topo,
            memory=c.memory,
            feature_id=feature_id,
            workflow_state=wf_state,
        )

    @api.put("/api/products/{name}/topology")
    def put_product_topology(name: str, body: TopologyUpdateRequest):
        c = ctx()
        from ..products.topology import (
            Component, ensure_topology, save_topology, sync_repo_path_from_topology,
        )
        try:
            project = c.store.get_project(name)
        except NotFound:
            raise HTTPException(404, f"product not found: {name}")
        topo = ensure_topology(
            c.root, name, repo_path=project.get("repo_path"),
        )
        if body.shape:
            if body.shape not in ("mono", "multi"):
                raise HTTPException(400, "shape must be mono or multi")
            topo.shape = body.shape
        if body.components is not None:
            topo.components = [
                Component(
                    id=comp.id,
                    name=comp.name or comp.id,
                    kind=comp.kind,
                    path=str(Path(comp.path).resolve()) if comp.path else None,
                    default_branch=comp.default_branch,
                    test_command=comp.test_command,
                    order_hint=comp.order_hint,
                )
                for comp in body.components
            ]
            if len(topo.components) > 1:
                topo.shape = "multi"
        save_topology(c.root, topo)
        sync_repo_path_from_topology(c.store, project["id"], topo)
        c.events.append(Event(
            event_type="product.topology_updated", project_id=project["id"],
            payload=topo.to_dict(),
        ))
        return {"id": project["id"], **topo.to_dict()}

    @api.get("/features")
    def features():
        return ctx().store.list_features()

    @api.get("/workflows")
    def workflows():
        return ctx().store.list_workflows()

    @api.get("/workflows/{workflow_id}")
    def workflow_detail(workflow_id: str):
        c = ctx()
        try:
            workflow = c.store.get_workflow(workflow_id)
        except NotFound:
            raise HTTPException(404, f"workflow not found: {workflow_id}")
        budget, spent = c.store.load_budget(workflow)
        tracker = BudgetTracker(budget, spent)
        return {
            "workflow": workflow,
            "agent_runs": c.store.list_agent_runs(workflow_id),
            "checkpoints": c.store.list_checkpoints(workflow_id),
            "events": c.events.list(workflow_id=workflow_id, limit=200),
            "budget": budget.model_dump(),
            "spent": spent.model_dump(),
            "remaining": tracker.remaining(),
            "totals": c.events.totals(workflow_id),
        }

    @api.get("/api/features/{feature_id}/document/{kind}")
    def feature_document(feature_id: str, kind: str):
        if kind not in DOCUMENTS:
            raise HTTPException(404, f"unknown document: {kind}")
        c = ctx()
        row = c.store.conn.execute(
            """SELECT f.name AS feature, p.name AS project FROM features f
               JOIN projects p ON p.id = f.project_id WHERE f.id = ?""",
            (feature_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"feature not found: {feature_id}")
        path = (c.root / "projects" / row["project"] / "features" / row["feature"]
                / DOCUMENTS[kind])
        if not path.exists():
            return {"kind": kind, "exists": False, "content": None,
                    "path": str(path)}
        return {"kind": kind, "exists": True, "path": str(path),
                "content": path.read_text(encoding="utf-8")}

    @api.get("/api/features/{feature_id}/documents")
    def feature_documents(feature_id: str):
        from ..docs.workspace import FeatureWorkspace
        c = ctx()
        row = c.store.conn.execute(
            """SELECT f.name AS feature, p.name AS project FROM features f
               JOIN projects p ON p.id = f.project_id WHERE f.id = ?""",
            (feature_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"feature not found: {feature_id}")
        ws = FeatureWorkspace(c.root, row["project"], row["feature"])
        if not ws.exists():
            return {"feature_id": feature_id, "documents": []}
        return {"feature_id": feature_id, "documents": ws.list_docs()}

    @api.get("/api/docs/search")
    def docs_search(q: str, mode: str = "hybrid",
                    project: str | None = None, feature: str | None = None,
                    limit: int = 8):
        c = ctx()
        return c.indexer.search(
            q, mode=mode, project=project, feature=feature, limit=limit,
        )

    @api.post("/api/features/{feature_id}/docs-index")
    def feature_docs_index(feature_id: str):
        c = ctx()
        row = c.store.conn.execute(
            """SELECT f.name AS feature, p.name AS project FROM features f
               JOIN projects p ON p.id = f.project_id WHERE f.id = ?""",
            (feature_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"feature not found: {feature_id}")
        report = c.indexer.index_feature(row["project"], row["feature"])
        c.events.append(Event(
            event_type="docs.indexed", feature_id=feature_id,
            payload=report.to_dict(),
        ))
        return report.to_dict()

    @api.get("/events")
    def events(workflow: str | None = None, event_type: str | None = None,
               limit: int = 100):
        return ctx().events.list(workflow_id=workflow, event_type=event_type,
                                 limit=limit)

    @api.get("/approvals")
    def approvals(status: str | None = None):
        return ctx().store.list_approvals(status)

    @api.get("/costs")
    def costs():
        c = ctx()
        rows = c.store.conn.execute(
            """SELECT w.id AS workflow_id, w.state, f.name AS feature,
                      COALESCE(SUM(e.tokens_in),0) AS tokens_in,
                      COALESCE(SUM(e.tokens_out),0) AS tokens_out,
                      COALESCE(SUM(e.cost_usd),0) AS cost_usd
               FROM workflows w
               JOIN features f ON f.id = w.feature_id
               LEFT JOIN events e ON e.workflow_id = w.id
               GROUP BY w.id ORDER BY w.created_at DESC"""
        ).fetchall()
        return {"by_workflow": [dict(r) for r in rows],
                "grand_total": c.events.totals()}

    @api.get("/audit/verify")
    def audit_verify():
        ok, bad = ctx().events.verify_chain()
        return {"chain_valid": ok, "first_invalid_event": bad}

    @api.get("/api/jobs")
    def jobs():
        return _active_jobs(ctx().root)

    # -- action endpoints ---------------------------------------------------

    @api.post("/workflows/{workflow_id}/approval")
    def decide(workflow_id: str, decision: ApprovalDecision):
        gate = (decision.gate or PLAN_GATE).strip()
        if gate not in (PLAN_GATE, RELEASE_GATE):
            raise HTTPException(
                400, f"gate must be '{PLAN_GATE}' or '{RELEASE_GATE}'")
        c = ctx()
        try:
            result = c.store.decide_approval(
                workflow_id, gate, decision.approve,
                decision.decided_by, decision.reason)
        except NotFound as exc:
            raise HTTPException(404, str(exc))
        c.events.append(Event(
            event_type="approval.granted" if decision.approve else "approval.rejected",
            workflow_id=workflow_id,
            payload={"gate": gate, "by": decision.decided_by,
                     "reason": decision.reason, "via": "command-center"}))
        return result

    @api.post("/api/features/{feature_id}/run")
    def run_feature(feature_id: str, request: RunRequest):
        c = ctx()
        from ..products.topology import (
            ensure_topology, sync_repo_path_from_topology,
        )
        row = c.store.conn.execute(
            """SELECT f.id, f.name AS feature, f.objective, p.id AS project_id,
                      p.name AS project, p.repo_path FROM features f
               JOIN projects p ON p.id = f.project_id WHERE f.id = ?""",
            (feature_id,)).fetchone()
        if not row:
            raise HTTPException(404, f"feature not found: {feature_id}")
        topo = ensure_topology(
            c.root, row["project"], repo_path=row["repo_path"],
        )
        sync_repo_path_from_topology(c.store, row["project_id"], topo)
        repo = topo.primary_path or row["repo_path"]
        if not repo:
            raise HTTPException(
                400,
                "product has no component path; configure topology "
                "(product-set-component / connect-repo) first",
            )
        budget = Budget(maximum_cost_usd=request.budget_usd,
                        maximum_iterations=request.max_iterations)
        workflow = c.store.create_workflow(feature_id, "existing-feature", budget)
        c.events.append(Event(
            event_type="command.issued", workflow_id=workflow["id"],
            feature_id=feature_id,
            payload={"action": "run", "by": request.started_by,
                     "budget_usd": request.budget_usd,
                     "via": "command-center",
                     "component_path": repo,
                     "shape": topo.shape}))
        job = _spawn(
            _worker_run,
            (str(c.root), row["project"], row["feature"], row["objective"],
             repo, workflow["id"]),
            "run", workflow["id"], f"run {row['project']}/{row['feature']}")
        return {"workflow_id": workflow["id"], "job": job}

    @api.post("/api/workflows/{workflow_id}/resume")
    def resume_workflow(workflow_id: str):
        c = ctx()
        try:
            workflow = c.store.get_workflow(workflow_id)
        except NotFound:
            raise HTTPException(404, f"workflow not found: {workflow_id}")
        if workflow_id in _running_workflow_ids(c.root):
            raise HTTPException(409, "workflow already has a running job")
        c.events.append(Event(
            event_type="command.issued", workflow_id=workflow_id,
            payload={"action": "resume", "via": "command-center"}))
        job = _spawn(_worker_resume, (str(c.root), workflow_id),
                     "resume", workflow_id, f"resume {workflow_id}")
        return {"workflow_id": workflow_id, "job": job}

    @api.post("/api/workflows/{workflow_id}/revert")
    def revert_workflow(workflow_id: str, request: RevertRequest):
        c = ctx()
        try:
            workflow = c.store.get_workflow(workflow_id)
        except NotFound:
            raise HTTPException(404, f"workflow not found: {workflow_id}")
        row = c.store.conn.execute(
            """SELECT p.repo_path FROM workflows w
               JOIN features f ON f.id = w.feature_id
               JOIN projects p ON p.id = f.project_id WHERE w.id = ?""",
            (workflow_id,)).fetchone()
        if not row or not row["repo_path"]:
            raise HTTPException(400, "no repository connected for this workflow")
        workspace = GitWorkspace(Path(row["repo_path"]))
        try:
            commit = workspace.restore_checkpoint(request.checkpoint_id)
        except GitError as exc:
            raise HTTPException(400, str(exc))
        c.events.append(Event(
            event_type="checkpoint.restored", workflow_id=workflow_id,
            feature_id=workflow["feature_id"],
            payload={"checkpoint_id": request.checkpoint_id, "commit": commit,
                     "by": request.decided_by, "via": "command-center"}))
        return {"workflow_id": workflow_id, "restored_to": commit,
                "checkpoint_id": request.checkpoint_id}

    return api
