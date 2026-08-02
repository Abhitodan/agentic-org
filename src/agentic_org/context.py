"""Service wiring: one place that builds the platform services for a root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .core import db
from .core.events import EventStore
from .core.store import Store
from .gateway.model_gateway import ModelGateway
from .mcp.builtin import ensure_builtin_mcp
from .mcp.gateway import McpGateway
from .memory.graph import GraphMemory
from .orchestrator.runner import WorkflowRunner
from .orchestrator.workflow_def import ensure_workflow_defs
from .retrieval.indexer import DocumentIndexer
from .retrieval.vectors import VectorStore


@dataclass
class AppContext:
    root: Path
    store: Store
    events: EventStore
    gateway: ModelGateway
    runner: WorkflowRunner
    mcp: McpGateway
    memory: GraphMemory
    vectors: VectorStore
    indexer: DocumentIndexer


def resolve_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("AGENTIC_ORG_ROOT")
    if env:
        return Path(env).resolve()
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".agent-org").is_dir():
            return candidate
    return current


def build_context(root: str | None = None) -> AppContext:
    resolved = resolve_root(root)
    load_dotenv(resolved / ".env", override=False)
    ensure_workflow_defs(resolved)
    mcp_dir = resolved / ".agent-org" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    for name, body in (
        ("registry.yaml", "servers: []\n"),
        ("permissions.yaml", "grants: []\n"),
    ):
        path = mcp_dir / name
        if not path.exists():
            path.write_text(body, encoding="utf-8")
    ensure_builtin_mcp(mcp_dir)
    conn = db.connect(db.default_db_path(resolved))
    store = Store(conn)
    events = EventStore(conn)
    gateway = ModelGateway(resolved / ".agent-org" / "models.yaml")
    mcp = McpGateway(
        mcp_dir / "registry.yaml",
        mcp_dir / "permissions.yaml",
        events=events,
        org_root=resolved,
    )
    memory = GraphMemory.from_path(
        resolved / ".agent-org" / "state" / "graph.db"
    )
    vectors = VectorStore.from_path(
        resolved / ".agent-org" / "state" / "vectors.db"
    )
    indexer = DocumentIndexer(resolved, vectors, gateway=gateway)
    runner = WorkflowRunner(
        resolved, store, events, gateway, mcp=mcp, indexer=indexer,
    )
    return AppContext(
        resolved, store, events, gateway, runner, mcp, memory, vectors, indexer,
    )
