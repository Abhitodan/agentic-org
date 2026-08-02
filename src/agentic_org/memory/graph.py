"""SQLite-backed graph memory projection.

Canonical owners remain events + git + operational tables. This graph is a
rebuildable projection for relationship / impact queries — never a second
source of truth for execution history.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.events import EventStore
from ..core.ids import new_id, utc_now
from ..core.store import Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id   TEXT PRIMARY KEY,
    kind      TEXT NOT NULL,
    label     TEXT NOT NULL,
    props     TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id   TEXT PRIMARY KEY,
    src_id    TEXT NOT NULL,
    rel       TEXT NOT NULL,
    dst_id    TEXT NOT NULL,
    props     TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_kind ON graph_nodes(kind);
CREATE INDEX IF NOT EXISTS idx_graph_edges_src ON graph_edges(src_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_dst ON graph_edges(dst_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_rel ON graph_edges(rel);
"""


@dataclass
class GraphHit:
    node_id: str
    kind: str
    label: str
    props: dict[str, Any]
    score: float = 1.0


class GraphMemory:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.executescript(SCHEMA)

    @classmethod
    def from_path(cls, db_path: Path) -> "GraphMemory":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return cls(conn)

    def clear(self) -> None:
        self.conn.execute("DELETE FROM graph_edges")
        self.conn.execute("DELETE FROM graph_nodes")
        self.conn.commit()

    def upsert_node(
        self, node_id: str, kind: str, label: str, props: dict[str, Any] | None = None
    ) -> None:
        self.conn.execute(
            """INSERT INTO graph_nodes(node_id, kind, label, props, updated_at)
               VALUES(?,?,?,?,?)
               ON CONFLICT(node_id) DO UPDATE SET
                 kind=excluded.kind, label=excluded.label,
                 props=excluded.props, updated_at=excluded.updated_at""",
            (node_id, kind, label, json.dumps(props or {}, sort_keys=True), utc_now()),
        )

    def upsert_edge(
        self,
        src_id: str,
        rel: str,
        dst_id: str,
        props: dict[str, Any] | None = None,
        edge_id: str | None = None,
    ) -> str:
        eid = edge_id or new_id("gedge")
        # Idempotent logical edge: replace prior src/rel/dst triple.
        self.conn.execute(
            "DELETE FROM graph_edges WHERE src_id = ? AND rel = ? AND dst_id = ?",
            (src_id, rel, dst_id),
        )
        self.conn.execute(
            """INSERT INTO graph_edges(edge_id, src_id, rel, dst_id, props, updated_at)
               VALUES(?,?,?,?,?,?)""",
            (eid, src_id, rel, dst_id, json.dumps(props or {}, sort_keys=True), utc_now()),
        )
        return eid

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM graph_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["props"] = json.loads(d["props"])
        return d

    def neighbors(
        self, node_id: str, rel: str | None = None, direction: str = "out"
    ) -> list[dict[str, Any]]:
        if direction == "out":
            sql = "SELECT * FROM graph_edges WHERE src_id = ?"
            params: list[Any] = [node_id]
        elif direction == "in":
            sql = "SELECT * FROM graph_edges WHERE dst_id = ?"
            params = [node_id]
        else:
            sql = "SELECT * FROM graph_edges WHERE src_id = ? OR dst_id = ?"
            params = [node_id, node_id]
        if rel:
            sql += " AND rel = ?"
            params.append(rel)
        rows = self.conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["props"] = json.loads(d["props"])
            out.append(d)
        return out

    def search(self, query: str, kinds: list[str] | None = None, limit: int = 20) -> list[GraphHit]:
        q = f"%{query.lower()}%"
        sql = "SELECT * FROM graph_nodes WHERE lower(label) LIKE ? OR lower(props) LIKE ?"
        params: list[Any] = [q, q]
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            sql += f" AND kind IN ({placeholders})"
            params.extend(kinds)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        hits = []
        for row in self.conn.execute(sql, params).fetchall():
            hits.append(GraphHit(
                node_id=row["node_id"],
                kind=row["kind"],
                label=row["label"],
                props=json.loads(row["props"]),
            ))
        return hits

    def impact(self, feature_id: str) -> dict[str, Any]:
        """Return related project, workflows, and file nodes for a feature."""
        feature = self.get_node(f"feature:{feature_id}")
        projects = []
        for edge in self.neighbors(f"feature:{feature_id}", rel="CONTAINED_IN"):
            node = self.get_node(edge["dst_id"])
            if node:
                projects.append(node)
        workflows = []
        for edge in self.neighbors(f"feature:{feature_id}", rel="HAS_WORKFLOW", direction="in"):
            # HAS_WORKFLOW is workflow -> feature; use inbound FOR_FEATURE instead
            pass
        for edge in self.neighbors(f"feature:{feature_id}", rel="FOR_FEATURE", direction="in"):
            node = self.get_node(edge["src_id"])
            if node:
                workflows.append(node)
        files = []
        for edge in self.neighbors(f"feature:{feature_id}", rel="TOUCHES"):
            node = self.get_node(edge["dst_id"])
            if node:
                files.append(node)
        return {
            "feature": feature,
            "projects": projects,
            "workflows": workflows,
            "files": files,
        }

    def rebuild(self, store: Store, events: EventStore, root: Path) -> dict[str, int]:
        """Full rebuild from operational tables + recent events + brain paths."""
        self.clear()
        counts = {"nodes": 0, "edges": 0}

        for project in store.list_projects():
            pid = f"project:{project['id']}"
            self.upsert_node(pid, "PROJECT", project["name"], {
                "id": project["id"], "repo_path": project.get("repo_path"),
            })
            counts["nodes"] += 1

        features = store.conn.execute("SELECT * FROM features").fetchall()
        for feature in features:
            fid = f"feature:{feature['id']}"
            self.upsert_node(fid, "FEATURE", feature["name"], {
                "id": feature["id"],
                "objective": feature["objective"],
                "state": feature["state"],
            })
            counts["nodes"] += 1
            self.upsert_edge(fid, "CONTAINED_IN", f"project:{feature['project_id']}")
            counts["edges"] += 1
            brain = (
                root / "projects" / self._project_name(store, feature["project_id"])
                / "features" / feature["name"] / "FEATURE_BRAIN.md"
            )
            if brain.exists():
                bid = f"brain:{feature['id']}"
                self.upsert_node(bid, "BRAIN", str(brain.name), {"path": str(brain)})
                counts["nodes"] += 1
                self.upsert_edge(fid, "DOCUMENTED_BY", bid)
                counts["edges"] += 1

        for workflow in store.list_workflows():
            wid = f"workflow:{workflow['id']}"
            self.upsert_node(wid, "WORKFLOW", workflow["id"], {
                "kind": workflow["kind"], "state": workflow["state"],
            })
            counts["nodes"] += 1
            self.upsert_edge(wid, "FOR_FEATURE", f"feature:{workflow['feature_id']}")
            counts["edges"] += 1

        for ev in events.list(limit=500):
            eid = f"event:{ev['event_id']}"
            self.upsert_node(eid, "EVENT", ev["event_type"], {
                "status": ev["status"], "event_type": ev["event_type"],
            })
            counts["nodes"] += 1
            if ev.get("workflow_id"):
                self.upsert_edge(eid, "IN_WORKFLOW", f"workflow:{ev['workflow_id']}")
                counts["edges"] += 1
            if ev.get("feature_id"):
                self.upsert_edge(eid, "ABOUT_FEATURE", f"feature:{ev['feature_id']}")
                counts["edges"] += 1
            payload = ev.get("payload") or {}
            if ev["event_type"] == "implementation.succeeded":
                worktree = payload.get("worktree")
                if worktree:
                    self.upsert_edge(
                        f"feature:{ev['feature_id']}", "TOUCHES",
                        f"worktree:{Path(worktree).name}",
                        {"path": worktree},
                    )
                    self.upsert_node(
                        f"worktree:{Path(worktree).name}", "WORKTREE",
                        Path(worktree).name, {"path": worktree},
                    )
                    counts["nodes"] += 1
                    counts["edges"] += 1

        self.conn.commit()
        return counts

    @staticmethod
    def _project_name(store: Store, project_id: str) -> str:
        row = store.conn.execute(
            "SELECT name FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return row["name"] if row else "unknown"
