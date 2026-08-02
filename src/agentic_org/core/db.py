"""SQLite persistence layer.

Canonical ownership (see .agent-org/memory/graph-schema.md):
- `events` is the append-only event store (immutable execution history).
- Operational tables (projects, features, workflows, agent_runs, checkpoints,
  approvals) hold current workflow state and are rebuildable from events
  plus Git where practical.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       TEXT NOT NULL UNIQUE,
    timestamp      TEXT NOT NULL,
    organization_id TEXT,
    project_id     TEXT,
    feature_id     TEXT,
    workflow_id    TEXT,
    agent_run_id   TEXT,
    agent_role     TEXT,
    event_type     TEXT NOT NULL,
    payload        TEXT NOT NULL DEFAULT '{}',
    tokens_in      INTEGER NOT NULL DEFAULT 0,
    tokens_out     INTEGER NOT NULL DEFAULT 0,
    cost_usd       REAL NOT NULL DEFAULT 0,
    duration_ms    INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'ok',
    previous_event_id TEXT,
    event_hash     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    repo_path  TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS features (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name       TEXT NOT NULL,
    objective  TEXT NOT NULL DEFAULT '',
    state      TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS workflows (
    id         TEXT PRIMARY KEY,
    feature_id TEXT NOT NULL REFERENCES features(id),
    kind       TEXT NOT NULL,
    state      TEXT NOT NULL DEFAULT 'DRAFT',
    budget     TEXT NOT NULL DEFAULT '{}',
    spent      TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id          TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id),
    agent_role  TEXT NOT NULL,
    model       TEXT,
    objective   TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'running',
    tokens_in   INTEGER NOT NULL DEFAULT 0,
    tokens_out  INTEGER NOT NULL DEFAULT 0,
    cost_usd    REAL NOT NULL DEFAULT 0,
    started_at  TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id          TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id),
    kind        TEXT NOT NULL,
    git_ref     TEXT,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id           TEXT PRIMARY KEY,
    workflow_id  TEXT NOT NULL REFERENCES workflows(id),
    gate         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    reason       TEXT NOT NULL DEFAULT '',
    requested_at TEXT NOT NULL,
    decided_at   TEXT,
    decided_by   TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id           TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    workflow_id  TEXT,
    label        TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'running',
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    error        TEXT,
    result_state TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_workflow ON events(workflow_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


def default_db_path(root: Path) -> Path:
    return root / ".agent-org" / "state" / "agentic.db"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
