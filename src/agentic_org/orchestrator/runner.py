"""LangGraph-checkpointed feature workflow (Mode A vertical slice).

Pipeline is loaded from `.agent-org/workflows/existing-feature.yaml` and must
match the registered nodes below:

    intake -> map_repository -> create_brain -> draft_charter
           -> request_decision -> [PLAN GATE] -> plan -> implement
           -> merge -> request_release -> [RELEASE GATE] -> release -> END

Guarantees enforced here:
- Workflow YAML with implemented: false cannot be started.
- Every node transition goes through the deterministic state machine and is
  written to the append-only event store.
- Every node charges the workflow budget; exceeding it blocks the workflow.
- LLM steps never fake output: if no model is configured the workflow moves
  to BLOCKED with an auditable reason.
- Implementation success requires tests exiting 0 in an isolated worktree.
- The graph is checkpointed to SQLite, so a run can be resumed after the
  human approval gate (or a crash) with the same thread id.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from ..atl.lock import atl_enabled, evaluate_atl
from ..atl.seal import OracleSeal
from ..brain.feature_brain import FeatureBrain
from ..coding.implementer import Implementer, default_test_command
from ..core.budget import BudgetExceeded, BudgetTracker
from ..core.events import Event, EventStore
from ..core.ids import new_id
from ..core.state_machine import WorkflowState, validate_transition
from ..core.store import Store
from ..coding.grounding import missing_grounded_paths
from ..gateway.model_gateway import ModelGateway, ModelUnavailable
from ..mcp.builtin import (
    SERVER_NAME as MCP_LOCAL_ORG,
    TOOL_REPO_SUMMARY,
    repo_summary_executor,
)
from ..mcp.gateway import McpDenied, McpGateway
from ..products.execute import execute_work_packages
from ..products.topology import ensure_topology
from ..products.work_packages import (
    cross_component_checklist,
    load_plan as load_work_packages,
    save_plan as save_work_packages,
    seed_from_topology,
    validate_plan as validate_work_packages,
    work_packages_path,
)
from ..release.merge import merge_agent_branch
from ..release.release import create_release
from ..repo_intel.mapper import build_repo_map, save_repo_map
from ..workspace.git_ws import GitError, GitWorkspace
from .workflow_def import WorkflowDef, require_implemented

PLAN_GATE = "plan-approval"
RELEASE_GATE = "release-approval"

# Nodes the Mode A runner can execute. Must stay aligned with
# `.agent-org/workflows/existing-feature.yaml`.
MODE_A_NODES = [
    "intake",
    "map_repository",
    "create_brain",
    "draft_charter",
    "request_decision",
    "plan",
    "implement",
    "merge",
    "request_release",
    "release",
]


class RunState(TypedDict, total=False):
    workflow_id: str
    project_name: str
    feature_name: str
    repo_path: str
    objective: str
    blocked_reason: str | None
    notes: list[str]
    worktree_path: str | None
    agent_branch: str | None
    task_id: str | None
    release_version: str | None


class WorkflowRunner:
    def __init__(
        self,
        root: Path,
        store: Store,
        events: EventStore,
        gateway: ModelGateway,
        workflow_kind: str = "existing-feature",
        mcp: McpGateway | None = None,
        indexer: Any | None = None,
    ):
        self.root = root
        self.store = store
        self.events = events
        self.gateway = gateway
        self.mcp = mcp
        self.indexer = indexer
        self.workflow_kind = workflow_kind
        self.workflow_def: WorkflowDef = require_implemented(root, workflow_kind)
        self.workflow_def.require_nodes(set(MODE_A_NODES))
        self.checkpoint_db = root / ".agent-org" / "state" / "langgraph.db"
        self.checkpoint_db.parent.mkdir(parents=True, exist_ok=True)

    def _pack_context(
        self,
        state: RunState,
        query: str,
        fallback: str,
        *,
        budget_words: int = 800,
    ) -> str:
        """B1 SparseOnly pack when an index exists; else truncate fallback."""
        from ..retrieval.indexer import DocumentIndexer
        from ..retrieval.packer import pack_feature_context
        from ..retrieval.vectors import VectorStore

        indexer = self.indexer
        if indexer is None:
            vectors = VectorStore.from_path(
                self.root / ".agent-org" / "state" / "vectors.db",
            )
            indexer = DocumentIndexer(self.root, vectors, gateway=self.gateway)
        # Hybrid: synthetic corpus favored sparse; real bulk-import favored
        # PageIndex (B2 fact_hit=1.0 vs B1≈0.7). Merge both under budget.
        return pack_feature_context(
            indexer,
            query,
            project=state["project_name"],
            feature=state["feature_name"],
            budget_words=budget_words,
            mode="hybrid",
            fallback=fallback,
            auto_index=True,
        )

    # -- helpers ------------------------------------------------------------

    def _ctx(self, state: RunState) -> dict[str, Any]:
        workflow = self.store.get_workflow(state["workflow_id"])
        feature = self.store.conn.execute(
            "SELECT * FROM features WHERE id = ?", (workflow["feature_id"],)
        ).fetchone()
        return {"workflow": workflow, "feature": dict(feature)}

    def _transition(self, state: RunState, target: WorkflowState,
                    approval_granted: bool = False, reason: str = "") -> None:
        workflow = self.store.get_workflow(state["workflow_id"])
        current = WorkflowState(workflow["state"])
        validate_transition(current, target, approval_granted=approval_granted)
        self.store.set_workflow_state(workflow["id"], target.value)
        self.events.append(Event(
            event_type="workflow.transition",
            workflow_id=workflow["id"],
            feature_id=workflow["feature_id"],
            payload={"from": current.value, "to": target.value, "reason": reason},
        ))

    def _charge(self, state: RunState, **kwargs: Any) -> bool:
        """Charge the budget. On exhaustion, block the workflow and return False."""
        workflow = self.store.get_workflow(state["workflow_id"])
        budget, spent = self.store.load_budget(workflow)
        tracker = BudgetTracker(budget, spent)
        try:
            tracker.charge(**kwargs)
            self.store.save_spent(workflow["id"], tracker.spent)
            return True
        except BudgetExceeded as exc:
            self.store.save_spent(workflow["id"], tracker.spent)
            self._block(state, f"budget exhausted: {exc}")
            self.events.append(Event(
                event_type="budget.exceeded", workflow_id=workflow["id"],
                status="blocked",
                payload={"dimension": exc.dimension, "limit": exc.limit,
                         "attempted": exc.attempted},
            ))
            return False

    def _block(self, state: RunState, reason: str) -> None:
        workflow = self.store.get_workflow(state["workflow_id"])
        current = WorkflowState(workflow["state"])
        if current != WorkflowState.BLOCKED:
            validate_transition(current, WorkflowState.BLOCKED)
            self.store.set_workflow_state(workflow["id"], WorkflowState.BLOCKED.value)
            self.events.append(Event(
                event_type="workflow.transition", workflow_id=workflow["id"],
                feature_id=workflow["feature_id"],
                payload={"from": current.value, "to": WorkflowState.BLOCKED.value,
                         "reason": reason},
            ))
        state["blocked_reason"] = reason
        self.events.append(Event(
            event_type="workflow.blocked", workflow_id=workflow["id"],
            feature_id=workflow["feature_id"], status="blocked",
            payload={"reason": reason},
        ))

    def _feature_dir(self, state: RunState) -> Path:
        return (self.root / "projects" / state["project_name"] /
                "features" / state["feature_name"])

    def _implementation_writes_count(self, workflow_id: str) -> int:
        """Sum actions_applied from successful implementation events."""
        total = 0
        for ev in self.events.list(workflow_id=workflow_id, event_type="implementation.succeeded"):
            payload = ev.get("payload") or {}
            try:
                total += int(payload.get("actions_applied") or 0)
            except (TypeError, ValueError):
                continue
        return total

    def _gate_digests(self, workflow_id: str) -> dict[str, str]:
        """Latest approval.granted event_hash per gate (plan / release)."""
        digests: dict[str, str] = {}
        for ev in self.events.list(workflow_id=workflow_id, event_type="approval.granted", limit=50):
            payload = ev.get("payload") or {}
            gate = str(payload.get("gate") or "")
            if gate in ("plan-approval", "release-approval") and gate not in digests:
                digests[gate] = str(ev.get("event_hash") or ev.get("event_id") or "")
        # Also accept store-backed approvals if events lack hashes (older runs)
        for gate in ("plan-approval", "release-approval"):
            if gate not in digests and self.store.approval_granted(workflow_id, gate):
                rows = self.store.list_approvals()
                for row in rows:
                    if row.get("workflow_id") == workflow_id and row.get("gate") == gate \
                            and row.get("status") == "approved":
                        digests[gate] = str(row.get("id") or "")
                        break
        return digests

    def _record_grounding(
        self,
        state: RunState,
        *,
        kind: str,
        text: str,
        artifact_name: str,
    ) -> list[str]:
        """Check cited paths against the target repo; write report + event."""
        repo = Path(state["repo_path"])
        known: list[str] = []
        map_json = self._feature_dir(state) / "artifacts" / "repo-map.json"
        if map_json.exists():
            try:
                data = json.loads(map_json.read_text(encoding="utf-8"))
                raw_files = data.get("files") or []
                known = []
                for item in raw_files:
                    if isinstance(item, str):
                        known.append(item)
                    elif isinstance(item, dict) and item.get("path"):
                        known.append(str(item["path"]))
                known.extend(str(p) for p in (data.get("tests") or []))
            except (OSError, json.JSONDecodeError, TypeError):
                known = []
        missing = missing_grounded_paths(text, repo, known_files=known)
        report = {
            "kind": kind,
            "cited_missing": missing,
            "missing_count": len(missing),
            "ok": len(missing) == 0,
        }
        artifacts = self._feature_dir(state) / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / artifact_name).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        self.events.append(Event(
            event_type=f"{kind}.grounding",
            workflow_id=state["workflow_id"],
            status="ok" if report["ok"] else "warning",
            payload=report,
        ))
        if missing:
            state.setdefault("notes", []).append(
                f"{kind} ungrounded paths ({len(missing)}): {', '.join(missing[:8])}"
            )
            if os.environ.get("AGENTIC_ORG_STRICT_GROUNDING", "").strip() == "1":
                self._block(
                    state,
                    f"{kind} cites missing paths: {', '.join(missing[:12])}",
                )
        return missing

    # -- nodes ----------------------------------------------------------------

    def node_intake(self, state: RunState) -> RunState:
        started = time.monotonic()
        self._transition(state, WorkflowState.INTAKE, reason="request accepted")
        run = self.store.start_agent_run(
            state["workflow_id"], "intake-agent",
            f"classify and charter request: {state['objective']}")
        classification = {
            "type": "feature",
            "project": state["project_name"],
            "feature": state["feature_name"],
            "repo_path": state["repo_path"],
            "workflow_kind": self.workflow_kind,
        }
        git_ref = None
        ws = GitWorkspace(Path(state["repo_path"]))
        if ws.is_repo():
            try:
                checkpoint_id = ws.checkpoint("workflow-start",
                                              f"wf {state['workflow_id']}")
                git_ref = checkpoint_id
                self.store.record_checkpoint(
                    state["workflow_id"], checkpoint_id, "workflow-start",
                    ws.current_commit(), "automatic checkpoint at intake")
            except GitError as exc:
                classification["checkpoint_warning"] = str(exc)
        if not self._charge(state, tool_calls=1, iterations=1):
            return state
        self.store.finish_agent_run(run["id"], "succeeded")
        self.events.append(Event(
            event_type="intake.classified", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="intake-agent",
            duration_ms=int((time.monotonic() - started) * 1000),
            payload={"classification": classification, "git_checkpoint": git_ref},
        ))
        return state

    def node_map_repository(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        started = time.monotonic()
        self._transition(state, WorkflowState.DISCOVERY, reason="repository mapping")
        run = self.store.start_agent_run(
            state["workflow_id"], "repository-agent",
            f"deterministically map {state['repo_path']}")
        try:
            repo_map = build_repo_map(Path(state["repo_path"]))
        except FileNotFoundError as exc:
            self.store.finish_agent_run(run["id"], "failed")
            self._block(state, str(exc))
            return state
        artifacts = self._feature_dir(state) / "artifacts"
        json_path, md_path = save_repo_map(repo_map, artifacts)
        mcp_summary = None
        if self.mcp is not None:
            try:
                mcp_result = self.mcp.call(
                    MCP_LOCAL_ORG,
                    TOOL_REPO_SUMMARY,
                    {"repo_path": state["repo_path"]},
                    role="repository-agent",
                    workflow_state=WorkflowState.DISCOVERY.value,
                    workflow_id=state["workflow_id"],
                    executor=repo_summary_executor,
                )
                mcp_summary = mcp_result.output
            except McpDenied as exc:
                mcp_summary = {"ok": False, "denied": str(exc)}
        if not self._charge(state, tool_calls=1, iterations=1):
            return state
        self.store.finish_agent_run(run["id"], "succeeded")
        self.events.append(Event(
            event_type="repository.mapped", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="repository-agent",
            duration_ms=int((time.monotonic() - started) * 1000),
            payload={
                "files": repo_map["file_count"],
                "languages": repo_map["languages"],
                "tests": len(repo_map["tests"]),
                "artifacts": [str(json_path), str(md_path)],
                "mcp_repo_summary": mcp_summary,
            },
        ))
        state.setdefault("notes", []).append(f"repo mapped: {repo_map['file_count']} files")
        return state

    def node_create_brain(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        self._transition(state, WorkflowState.RESEARCHING, reason="brain construction")
        ctx = self._ctx(state)
        brain = FeatureBrain(self.root, state["project_name"], state["feature_name"])
        if not brain.exists():
            brain.create(ctx["feature"]["id"], state["objective"])
        artifacts = self._feature_dir(state) / "artifacts"
        map_md = artifacts / "repo-map.md"
        if map_md.exists():
            brain.update_section("Current State", map_md.read_text(encoding="utf-8"))
        brain.append_to_section(
            "Agent Sessions", f"workflow {state['workflow_id']}: brain initialized")
        if not self._charge(state, tool_calls=1, iterations=1):
            return state
        self.events.append(Event(
            event_type="brain.updated", workflow_id=state["workflow_id"],
            feature_id=ctx["feature"]["id"], agent_role="repository-agent",
            payload={"sections": ["Current State", "Agent Sessions"],
                     "path": str(brain.brain_md)},
        ))
        self._ensure_docs_indexed(state, force=True)
        return state

    def _ensure_docs_indexed(self, state: RunState, *, force: bool = False) -> None:
        from ..retrieval.indexer import DocumentIndexer
        from ..retrieval.packer import ensure_feature_indexed
        from ..retrieval.vectors import VectorStore

        indexer = self.indexer
        if indexer is None:
            vectors = VectorStore.from_path(
                self.root / ".agent-org" / "state" / "vectors.db",
            )
            indexer = DocumentIndexer(self.root, vectors, gateway=self.gateway)
            self.indexer = indexer
        ensure_feature_indexed(
            indexer, state["project_name"], state["feature_name"], force=force,
        )

    def _usable_managed_doc(self, path: Path, *, min_words: int = 60) -> str | None:
        """Return doc text if substantial enough to reuse when the model is down."""
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        if len(text.split()) < min_words:
            return None
        low = text.lower()
        if "_tbd_" in low or low.count("not yet recorded") >= 3:
            return None
        return text

    def node_draft_charter(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        run = self.store.start_agent_run(
            state["workflow_id"], "product-manager-agent",
            "draft feature charter with architecture options")
        artifacts = self._feature_dir(state) / "artifacts"
        map_md = artifacts / "repo-map.md"
        repo_summary = map_md.read_text(encoding="utf-8") if map_md.exists() else ""
        packed_map = self._pack_context(
            state, state["objective"], repo_summary, budget_words=900,
        )
        charter_path = self._feature_dir(state) / "charter.md"
        try:
            result = self.gateway.complete(
                "standard",
                system=("You are the Product Manager agent of an agentic software "
                        "organization. Produce a concise feature charter: problem, "
                        "users, measurable outcome, scope, exclusions, acceptance "
                        "criteria, risks, and 2-3 architecture options with "
                        "trade-offs. Ground every claim in the provided repository "
                        "map; never invent files."),
                user=(f"Objective: {state['objective']}\n\n"
                      f"Repository map:\n{packed_map}"),
            )
        except ModelUnavailable as exc:
            existing = self._usable_managed_doc(charter_path)
            if existing is None:
                self.store.finish_agent_run(run["id"], "blocked")
                self._block(state, f"model gateway unavailable: {exc}")
                return state
            if not self._charge(state, tool_calls=1, iterations=1):
                return state
            self._ensure_docs_indexed(state, force=True)
            self._record_grounding(
                state, kind="charter", text=existing,
                artifact_name="charter_grounding.json",
            )
            if state.get("blocked_reason"):
                self.store.finish_agent_run(run["id"], "blocked")
                return state
            self.store.finish_agent_run(run["id"], "succeeded")
            self._transition(state, WorkflowState.OPTIONS_READY,
                             reason="reused existing charter (model unavailable)")
            self.events.append(Event(
                event_type="charter.reused", workflow_id=state["workflow_id"],
                agent_run_id=run["id"], agent_role="product-manager-agent",
                payload={
                    "path": str(charter_path),
                    "reason": "model_unavailable",
                    "detail": str(exc)[:300],
                },
            ))
            return state
        if not self._charge(state, tool_calls=1, iterations=1,
                            input_tokens=result.tokens_in,
                            output_tokens=result.tokens_out,
                            cost_usd=result.cost_usd,
                            expensive_model_calls=1 if result.is_expensive else 0):
            return state
        from ..docs.workspace import FeatureWorkspace
        ws = FeatureWorkspace(
            self.root, state["project_name"], state["feature_name"],
        )
        charter_path = ws.write_doc(
            "charter", result.text, source="workflow", status="draft",
            title="Feature Charter",
        )
        self._ensure_docs_indexed(state, force=True)
        self._record_grounding(
            state, kind="charter", text=result.text,
            artifact_name="charter_grounding.json",
        )
        if state.get("blocked_reason"):
            self.store.finish_agent_run(run["id"], "blocked")
            return state
        self.store.finish_agent_run(run["id"], "succeeded", result.tokens_in,
                                    result.tokens_out, result.cost_usd)
        self._transition(state, WorkflowState.OPTIONS_READY,
                         reason="charter and options drafted")
        self.events.append(Event(
            event_type="charter.drafted", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="product-manager-agent",
            tokens_in=result.tokens_in, tokens_out=result.tokens_out,
            cost_usd=result.cost_usd, duration_ms=result.duration_ms,
            payload={"model": result.model, "path": str(charter_path)},
        ))
        return state

    def node_request_decision(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        self._transition(state, WorkflowState.AWAITING_DECISION,
                         reason="human decision required on charter")
        approval = self.store.request_approval(
            state["workflow_id"], PLAN_GATE,
            "Approve the feature charter and selected architecture option "
            "before planning begins.")
        self.events.append(Event(
            event_type="approval.requested", workflow_id=state["workflow_id"],
            payload={"gate": PLAN_GATE, "approval_id": approval["id"]},
        ))
        return state

    def node_plan(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        if not self.store.approval_granted(state["workflow_id"], PLAN_GATE):
            self._block(state, f"human gate '{PLAN_GATE}' not approved")
            return state
        self._transition(state, WorkflowState.APPROVED, approval_granted=True,
                         reason="charter approved by human")
        run = self.store.start_agent_run(
            state["workflow_id"], "planning-agent",
            "decompose approved charter into implementation plan")
        charter_path = self._feature_dir(state) / "charter.md"
        charter = charter_path.read_text(encoding="utf-8") if charter_path.exists() else ""
        packed_charter = self._pack_context(
            state,
            f"{state['objective']}\n{charter[:500]}",
            charter,
            budget_words=1200,
        )
        plan_path = self._feature_dir(state) / "implementation-plan.md"
        try:
            result = self.gateway.complete(
                "standard",
                system=("You are the Planning agent. Decompose the approved charter "
                        "into an ordered implementation plan: epics, stories with "
                        "acceptance criteria, dependencies, parallelizable work, "
                        "test expectations, and rollback notes. Be concrete and "
                        "reference only files that exist in the charter context."),
                user=f"Approved charter:\n{packed_charter}",
            )
        except ModelUnavailable as exc:
            existing = self._usable_managed_doc(plan_path)
            if existing is None:
                self.store.finish_agent_run(run["id"], "blocked")
                self._block(state, f"model gateway unavailable: {exc}")
                return state
            if not self._charge(state, tool_calls=1, iterations=1):
                return state
            self._record_grounding(
                state, kind="plan", text=existing,
                artifact_name="plan_grounding.json",
            )
            if state.get("blocked_reason"):
                self.store.finish_agent_run(run["id"], "blocked")
                return state
            self._seed_work_packages(state)
            self.store.finish_agent_run(run["id"], "succeeded")
            self._transition(
                state, WorkflowState.PLANNED,
                reason="reused existing plan (model unavailable)",
            )
            brain = FeatureBrain(self.root, state["project_name"], state["feature_name"])
            brain.append_to_section(
                "Decisions",
                f"charter approved; reused implementation plan at {plan_path.name}",
            )
            self.events.append(Event(
                event_type="plan.reused", workflow_id=state["workflow_id"],
                agent_run_id=run["id"], agent_role="planning-agent",
                payload={
                    "path": str(plan_path),
                    "reason": "model_unavailable",
                    "detail": str(exc)[:300],
                },
            ))
            return state
        if not self._charge(state, tool_calls=1, iterations=1,
                            input_tokens=result.tokens_in,
                            output_tokens=result.tokens_out,
                            cost_usd=result.cost_usd):
            return state
        from ..docs.workspace import FeatureWorkspace
        ws = FeatureWorkspace(
            self.root, state["project_name"], state["feature_name"],
        )
        plan_path = ws.write_doc(
            "plan", result.text, source="workflow", status="draft",
            title="Implementation Plan",
        )
        self._record_grounding(
            state, kind="plan", text=result.text,
            artifact_name="plan_grounding.json",
        )
        if state.get("blocked_reason"):
            self.store.finish_agent_run(run["id"], "blocked")
            return state
        self._seed_work_packages(state)
        self.store.finish_agent_run(run["id"], "succeeded", result.tokens_in,
                                    result.tokens_out, result.cost_usd)
        self._transition(state, WorkflowState.PLANNED, reason="implementation plan ready")
        brain = FeatureBrain(self.root, state["project_name"], state["feature_name"])
        brain.append_to_section(
            "Decisions", f"charter approved; implementation plan at {plan_path.name}")
        self.events.append(Event(
            event_type="plan.created", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="planning-agent",
            tokens_in=result.tokens_in, tokens_out=result.tokens_out,
            cost_usd=result.cost_usd, duration_ms=result.duration_ms,
            payload={"model": result.model, "path": str(plan_path)},
        ))
        return state

    def _seed_work_packages(self, state: RunState) -> None:
        topo = ensure_topology(
            self.root, state["project_name"], repo_path=state["repo_path"],
        )
        feature_dir = self._feature_dir(state)
        if work_packages_path(feature_dir).exists():
            return
        wp_plan = seed_from_topology(topo, state["objective"])
        errs = validate_work_packages(wp_plan, topo)
        if not errs and wp_plan.packages:
            save_work_packages(feature_dir, wp_plan)
            self.events.append(Event(
                event_type="work_packages.seeded",
                workflow_id=state["workflow_id"],
                payload={
                    "path": str(work_packages_path(feature_dir)),
                    "count": len(wp_plan.packages),
                    "suggest_only": True,
                },
            ))

    def node_implement(self, state: RunState) -> RunState:
        """Create a worktree, apply actions, succeed only if tests pass.

        When work_packages.json is present, execute each package against its
        component path and honor per-component test_command.
        """
        if state.get("blocked_reason"):
            return state
        self._transition(state, WorkflowState.SPRINT_READY, reason="enter implementation")
        self._transition(state, WorkflowState.IMPLEMENTING, reason="coding in worktree")
        run = self.store.start_agent_run(
            state["workflow_id"], "backend-agent",
            "implement plan in isolated worktree; gate on tests")
        feature_dir = self._feature_dir(state)
        actions_path = feature_dir / "artifacts" / "implementation_actions.json"
        plan_path = feature_dir / "implementation-plan.md"
        plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
        worktrees = self.root / ".agent-org" / "worktrees" / state["workflow_id"]
        topo = ensure_topology(
            self.root, state["project_name"], repo_path=state["repo_path"],
        )
        wp_plan = load_work_packages(feature_dir)

        # Multi-component path
        if wp_plan and wp_plan.packages and (
            topo.shape == "multi" or len(wp_plan.packages) > 1
        ):
            shared = None
            if actions_path.exists():
                try:
                    shared = json.loads(actions_path.read_text(encoding="utf-8"))
                    if not isinstance(shared, list):
                        shared = None
                except (OSError, json.JSONDecodeError):
                    shared = None
            multi = execute_work_packages(
                topology=topo,
                plan=wp_plan,
                feature_dir=feature_dir,
                worktrees_root=worktrees,
                org_root=self.root,
                objective=state["objective"],
                plan_text=plan_text,
                gateway=self.gateway,
                shared_actions=shared,
            )
            if not self._charge(state, tool_calls=max(1, len(multi.packages)),
                                iterations=1):
                return state
            payload = {
                "ok": multi.ok,
                "reason": multi.reason,
                "packages": [
                    {
                        "package_id": p.package_id,
                        "component_id": p.component_id,
                        "ok": p.ok,
                        "reason": p.reason,
                        "task_id": p.task_id,
                        "actions_applied": p.actions_applied,
                    }
                    for p in multi.packages
                ],
            }
            if not multi.ok:
                self.store.finish_agent_run(run["id"], "failed")
                self.events.append(Event(
                    event_type="implementation.failed",
                    workflow_id=state["workflow_id"],
                    agent_run_id=run["id"], agent_role="backend-agent",
                    status="failed", payload=payload,
                ))
                self._block(state, multi.reason)
                return state
            state["task_id"] = multi.primary_task_id
            state["agent_branch"] = multi.primary_branch
            state["worktree_path"] = multi.primary_worktree
            if multi.primary_repo:
                state["repo_path"] = multi.primary_repo
            self._transition(state, WorkflowState.INTEGRATING,
                             reason="work packages passed tests")
            self._transition(state, WorkflowState.VALIDATING,
                             reason="per-component tests exited 0")
            self.store.finish_agent_run(run["id"], "succeeded")
            self.events.append(Event(
                event_type="implementation.succeeded",
                workflow_id=state["workflow_id"],
                agent_run_id=run["id"], agent_role="backend-agent",
                payload=payload,
            ))
            state.setdefault("notes", []).append(
                f"implemented {len(multi.packages)} work packages"
            )
            return state

        # Mono / single-repo path (honor primary component test_command)
        task_id = new_id("task")
        implementer = Implementer(
            Path(state["repo_path"]), worktrees, org_root=self.root,
        )
        actions = None
        if actions_path.exists():
            try:
                actions = implementer.load_actions_file(actions_path)
            except (OSError, ValueError) as exc:
                self.store.finish_agent_run(run["id"], "failed")
                self._block(state, f"invalid implementation_actions.json: {exc}")
                return state

        test_cmd = default_test_command()
        primary = next(
            (c for c in sorted(topo.components, key=lambda x: (x.order_hint, x.id))
             if c.path),
            None,
        )
        if primary and primary.test_command:
            test_cmd = primary.test_command.split()

        result = implementer.run(
            task_id,
            actions,
            gateway=self.gateway if actions is None else None,
            objective=state["objective"],
            plan_text=plan_text,
            test_command=test_cmd,
        )
        state["task_id"] = task_id
        state["agent_branch"] = f"agent/{task_id}"
        state["worktree_path"] = str(result.worktree) if result.worktree else None
        if not self._charge(state, tool_calls=1, iterations=1):
            return state

        payload = {
            "task_id": task_id,
            "ok": result.ok,
            "reason": result.reason,
            "actions_applied": result.actions_applied,
            "worktree": str(result.worktree) if result.worktree else None,
            "notes": result.notes,
            "test_command": test_cmd,
            "test": None if result.test is None else {
                "ok": result.test.ok,
                "exit_code": result.test.exit_code,
                "command": result.test.command,
                "stdout_tail": result.test.stdout[-2000:],
                "stderr_tail": result.test.stderr[-2000:],
                "duration_ms": result.test.duration_ms,
            },
        }
        if not result.ok:
            self.store.finish_agent_run(run["id"], "failed")
            self.events.append(Event(
                event_type="implementation.failed", workflow_id=state["workflow_id"],
                agent_run_id=run["id"], agent_role="backend-agent", status="failed",
                payload=payload,
            ))
            self._block(state, result.reason)
            return state

        if wp_plan and wp_plan.packages:
            for pkg in wp_plan.packages:
                pkg.status = "done"
            save_work_packages(feature_dir, wp_plan)

        self._transition(state, WorkflowState.INTEGRATING,
                         reason="tests passed; recording worktree result")
        self._transition(state, WorkflowState.VALIDATING,
                         reason="validation evidenced by pytest exit 0")
        self.store.finish_agent_run(run["id"], "succeeded")
        self.events.append(Event(
            event_type="implementation.succeeded", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="backend-agent",
            payload=payload,
        ))
        ctx = self._ctx(state)
        brain = FeatureBrain(self.root, state["project_name"], state["feature_name"])
        if not brain.exists():
            brain.create(ctx["feature"]["id"], state["objective"])
        brain.append_to_section(
            "Tests",
            f"worktree {task_id}: tests passed "
            f"({result.test.duration_ms if result.test else '?'} ms)",
        )
        state.setdefault("notes", []).append(f"implemented in worktree {task_id}")
        return state

    def node_merge(self, state: RunState) -> RunState:
        """Merge agent branch into protected checkout; rollback if tests fail."""
        if state.get("blocked_reason"):
            return state
        run = self.store.start_agent_run(
            state["workflow_id"], "release-agent",
            "merge agent branch with post-merge test gate")
        worktree = state.get("worktree_path")
        branch = state.get("agent_branch")
        if not worktree or not branch:
            self.store.finish_agent_run(run["id"], "failed")
            self._block(state, "merge requires worktree_path and agent_branch")
            return state
        topo = ensure_topology(
            self.root, state["project_name"], repo_path=state["repo_path"],
        )
        merge_cmd = default_test_command()
        primary = next(
            (c for c in sorted(topo.components, key=lambda x: (x.order_hint, x.id))
             if c.path == state["repo_path"] or c.path),
            None,
        )
        if primary and primary.test_command:
            merge_cmd = primary.test_command.split()
        result = merge_agent_branch(
            Path(state["repo_path"]),
            Path(worktree),
            branch,
            org_root=self.root,
            test_command=merge_cmd,
            message=f"merge {branch} for {state['feature_name']}",
        )
        if not self._charge(state, tool_calls=1, iterations=1):
            return state
        payload = {
            "ok": result.ok,
            "branch": result.branch,
            "merge_commit": result.merge_commit,
            "checkpoint_id": result.checkpoint_id,
            "reason": result.reason,
            "notes": result.notes,
        }
        if not result.ok:
            self.store.finish_agent_run(run["id"], "failed")
            self.events.append(Event(
                event_type="merge.failed", workflow_id=state["workflow_id"],
                agent_run_id=run["id"], agent_role="release-agent", status="failed",
                payload=payload,
            ))
            self._block(state, result.reason)
            return state
        self._transition(state, WorkflowState.REVIEWING,
                         reason="merged to protected branch; tests green")
        self.store.finish_agent_run(run["id"], "succeeded")
        self.events.append(Event(
            event_type="merge.succeeded", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="release-agent",
            payload=payload,
        ))
        if result.checkpoint_id:
            self.store.record_checkpoint(
                state["workflow_id"], result.checkpoint_id, "pre-merge",
                result.merge_commit, "checkpoint before auto-merge")
        return state

    def node_request_release(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        feature_dir = self._feature_dir(state)
        topo = ensure_topology(
            self.root, state["project_name"], repo_path=state["repo_path"],
        )
        wp_plan = load_work_packages(feature_dir)
        if wp_plan and wp_plan.packages:
            checklist = cross_component_checklist(wp_plan, topo)
            artifacts = feature_dir / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "cross_component_checklist.json").write_text(
                json.dumps(checklist, indent=2), encoding="utf-8",
            )
            self.events.append(Event(
                event_type="cross_component.validated",
                workflow_id=state["workflow_id"],
                status="ok" if checklist["ok"] else "failed",
                payload=checklist,
            ))
            if not checklist["ok"]:
                self._block(
                    state,
                    "cross-component validation failed: "
                    + checklist.get("summary", "incomplete packages"),
                )
                return state
        self._transition(state, WorkflowState.AWAITING_APPROVAL,
                         reason="human release approval required")
        approval = self.store.request_approval(
            state["workflow_id"], RELEASE_GATE,
            "Approve release tag creation after merge.")
        self.events.append(Event(
            event_type="release.approval.requested",
            workflow_id=state["workflow_id"],
            payload={"gate": RELEASE_GATE, "approval_id": approval["id"]},
        ))
        return state

    def node_release(self, state: RunState) -> RunState:
        if state.get("blocked_reason"):
            return state
        if not self.store.approval_granted(state["workflow_id"], RELEASE_GATE):
            self._block(state, f"human gate '{RELEASE_GATE}' not approved")
            return state
        self._transition(
            state, WorkflowState.READY_FOR_RELEASE,
            approval_granted=True, reason="release approved",
        )
        self._transition(state, WorkflowState.RELEASING, reason="creating release tag")
        run = self.store.start_agent_run(
            state["workflow_id"], "release-agent", "tag release after checks")
        version = state.get("release_version") or f"0.1.{state['workflow_id'][-6:]}"
        notes_path = self._feature_dir(state) / "implementation-plan.md"
        notes = ""
        if notes_path.exists():
            notes = notes_path.read_text(encoding="utf-8")[:2000]

        feature_dir = self._feature_dir(state)
        artifacts = feature_dir / "artifacts"
        charter_path = feature_dir / "charter.md"
        charter_text = charter_path.read_text(encoding="utf-8") if charter_path.exists() else ""
        writes = self._implementation_writes_count(state["workflow_id"])
        gates = self._gate_digests(state["workflow_id"])

        # Acceptance-Trace Lock: refuse COMPLETED unless every AC-# is coupled
        # to a named passing fresh seal (suite green alone is not enough).
        atl_payload: dict[str, Any] = {"enabled": atl_enabled()}
        if atl_enabled():
            provided_seal = None
            seal_path = artifacts / "oracle_seal.json"
            if seal_path.exists():
                try:
                    provided_seal = OracleSeal.from_dict(
                        json.loads(seal_path.read_text(encoding="utf-8"))
                    )
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    provided_seal = None
            decision = evaluate_atl(
                repo=Path(state["repo_path"]),
                charter_text=charter_text,
                feature_artifacts=artifacts,
                workflow_id=state["workflow_id"],
                writes_count=writes,
                gate_digests=gates,
                seal=provided_seal,
                mint_if_missing=True,
                org_root=self.root,
            )
            atl_payload = {
                "enabled": True,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "forge_class": decision.forge_class,
                "writes_count": writes,
                "gates": list(gates.keys()),
            }
            self.events.append(Event(
                event_type="atl.evaluated",
                workflow_id=state["workflow_id"],
                agent_run_id=run["id"],
                agent_role="release-agent",
                status="ok" if decision.allowed else "blocked",
                payload=atl_payload,
            ))
            if not decision.allowed:
                self.store.finish_agent_run(run["id"], "failed")
                self.events.append(Event(
                    event_type="release.failed", workflow_id=state["workflow_id"],
                    agent_run_id=run["id"], agent_role="release-agent", status="failed",
                    payload={"ok": False, "reason": f"ATL refused COMPLETED: {decision.reason}",
                             "atl": atl_payload},
                ))
                self._block(state, f"ATL refused COMPLETED: {decision.reason}")
                return state

        # Tests already evidenced by ATL seal when enabled; otherwise run suite.
        result = create_release(
            Path(state["repo_path"]),
            version,
            org_root=self.root,
            release_notes=notes or f"Release for {state['feature_name']}",
            run_tests=not atl_enabled(),
        )
        if not self._charge(state, tool_calls=1, iterations=1):
            return state
        payload = {
            "ok": result.ok,
            "version": result.version,
            "tag": result.tag,
            "commit": result.commit,
            "checks": result.checks,
            "reason": result.reason,
            "atl": atl_payload,
        }
        if not result.ok:
            self.store.finish_agent_run(run["id"], "failed")
            self.events.append(Event(
                event_type="release.failed", workflow_id=state["workflow_id"],
                agent_run_id=run["id"], agent_role="release-agent", status="failed",
                payload=payload,
            ))
            self._block(state, result.reason)
            return state
        self._transition(state, WorkflowState.OBSERVING, reason="release tagged")
        self._transition(
            state, WorkflowState.COMPLETED,
            reason="release complete; acceptance trace verified" if atl_enabled()
            else "release complete",
        )
        self.store.finish_agent_run(run["id"], "succeeded")
        self.events.append(Event(
            event_type="release.succeeded", workflow_id=state["workflow_id"],
            agent_run_id=run["id"], agent_role="release-agent",
            payload=payload,
        ))
        return state

    # -- graph ------------------------------------------------------------

    def _node_handlers(self) -> dict[str, Callable[[RunState], RunState]]:
        return {
            "intake": self.node_intake,
            "map_repository": self.node_map_repository,
            "create_brain": self.node_create_brain,
            "draft_charter": self.node_draft_charter,
            "request_decision": self.node_request_decision,
            "plan": self.node_plan,
            "implement": self.node_implement,
            "merge": self.node_merge,
            "request_release": self.node_request_release,
            "release": self.node_release,
        }

    def build_graph(self, checkpointer: SqliteSaver):
        handlers = self._node_handlers()
        nodes = self.workflow_def.nodes
        if nodes != MODE_A_NODES:
            raise RuntimeError(
                f"unsupported Mode A node list: {nodes}; expected {MODE_A_NODES}"
            )
        graph = StateGraph(RunState)
        for name in nodes:
            graph.add_node(name, handlers[name])

        graph.set_entry_point("intake")
        graph.add_edge("intake", "map_repository")
        graph.add_edge("map_repository", "create_brain")
        graph.add_edge("create_brain", "draft_charter")

        def after_charter(state: RunState) -> str:
            return "end" if state.get("blocked_reason") else "request_decision"

        def after_plan(state: RunState) -> str:
            return "end" if state.get("blocked_reason") else "implement"

        def after_implement(state: RunState) -> str:
            return "end" if state.get("blocked_reason") else "merge"

        def after_merge(state: RunState) -> str:
            return "end" if state.get("blocked_reason") else "request_release"

        graph.add_conditional_edges(
            "draft_charter", after_charter,
            {"end": END, "request_decision": "request_decision"})
        graph.add_edge("request_decision", "plan")
        graph.add_conditional_edges(
            "plan", after_plan, {"end": END, "implement": "implement"})
        graph.add_conditional_edges(
            "implement", after_implement, {"end": END, "merge": "merge"})
        graph.add_conditional_edges(
            "merge", after_merge,
            {"end": END, "request_release": "request_release"})
        graph.add_edge("request_release", "release")
        graph.add_edge("release", END)
        return graph.compile(
            checkpointer=checkpointer,
            interrupt_before=["plan", "release"],
        )

    def start(self, project_name: str, feature_name: str, objective: str,
              repo_path: str, workflow_id: str) -> RunState:
        initial: RunState = {
            "workflow_id": workflow_id,
            "project_name": project_name,
            "feature_name": feature_name,
            "repo_path": repo_path,
            "objective": objective,
            "blocked_reason": None,
            "notes": [],
        }
        with SqliteSaver.from_conn_string(str(self.checkpoint_db)) as saver:
            app = self.build_graph(saver)
            config = {"configurable": {"thread_id": workflow_id}}
            return app.invoke(initial, config)

    def resume(self, workflow_id: str, *, clear_block: bool = False) -> RunState:
        """Resume a workflow past the human gate (after approval is recorded).

        clear_block: drop a prior blocked_reason in the checkpoint so a transient
        failure (e.g. dirty bytecode) can be retried after the underlying fix.
        """
        with SqliteSaver.from_conn_string(str(self.checkpoint_db)) as saver:
            app = self.build_graph(saver)
            config = {"configurable": {"thread_id": workflow_id}}
            if clear_block:
                app.update_state(config, {"blocked_reason": None})
            return app.invoke(None, config)
