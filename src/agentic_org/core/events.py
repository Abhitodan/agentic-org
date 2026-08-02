"""Append-only, hash-chained event store.

Every meaningful platform action is recorded here. Events are immutable:
there is deliberately no update or delete API. Each event's hash covers its
canonical JSON body plus the previous event's hash, so tampering anywhere
in history is detectable with `verify_chain`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .ids import new_id, utc_now
from .redact import redact_obj

GENESIS_HASH = "0" * 64


@dataclass
class Event:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    organization_id: str | None = None
    project_id: str | None = None
    feature_id: str | None = None
    workflow_id: str | None = None
    agent_run_id: str | None = None
    agent_role: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    status: str = "ok"


class EventStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _last(self) -> tuple[str | None, str]:
        row = self.conn.execute(
            "SELECT event_id, event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None, GENESIS_HASH
        return row["event_id"], row["event_hash"]

    @staticmethod
    def _hash(body: dict[str, Any], previous_hash: str) -> str:
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((previous_hash + canonical).encode("utf-8")).hexdigest()

    def append(self, event: Event) -> str:
        prev_id, prev_hash = self._last()
        event_id = new_id("evt")
        safe_payload = redact_obj(event.payload)
        body = {
            "event_id": event_id,
            "timestamp": utc_now(),
            "organization_id": event.organization_id,
            "project_id": event.project_id,
            "feature_id": event.feature_id,
            "workflow_id": event.workflow_id,
            "agent_run_id": event.agent_run_id,
            "agent_role": event.agent_role,
            "event_type": event.event_type,
            "payload": safe_payload,
            "tokens_in": event.tokens_in,
            "tokens_out": event.tokens_out,
            "cost_usd": event.cost_usd,
            "duration_ms": event.duration_ms,
            "status": event.status,
            "previous_event_id": prev_id,
        }
        event_hash = self._hash(body, prev_hash)
        self.conn.execute(
            """INSERT INTO events (event_id, timestamp, organization_id, project_id,
               feature_id, workflow_id, agent_run_id, agent_role, event_type, payload,
               tokens_in, tokens_out, cost_usd, duration_ms, status,
               previous_event_id, event_hash)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                body["event_id"], body["timestamp"], body["organization_id"],
                body["project_id"], body["feature_id"], body["workflow_id"],
                body["agent_run_id"], body["agent_role"], body["event_type"],
                json.dumps(body["payload"], sort_keys=True),
                body["tokens_in"], body["tokens_out"], body["cost_usd"],
                body["duration_ms"], body["status"], body["previous_event_id"],
                event_hash,
            ),
        )
        self.conn.commit()
        return event_id

    def list(
        self,
        workflow_id: str | None = None,
        feature_id: str | None = None,
        project_id: str | None = None,
        event_type: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        for col, val in (
            ("workflow_id", workflow_id),
            ("feature_id", feature_id),
            ("project_id", project_id),
            ("event_type", event_type),
        ):
            if val is not None:
                clauses.append(f"{col} = ?")
                params.append(val)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM events {where} ORDER BY seq DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

    def verify_chain(self) -> tuple[bool, str | None]:
        """Recompute the full hash chain. Returns (ok, first_bad_event_id)."""
        rows = self.conn.execute("SELECT * FROM events ORDER BY seq ASC").fetchall()
        prev_hash = GENESIS_HASH
        prev_id = None
        for r in rows:
            body = {
                "event_id": r["event_id"],
                "timestamp": r["timestamp"],
                "organization_id": r["organization_id"],
                "project_id": r["project_id"],
                "feature_id": r["feature_id"],
                "workflow_id": r["workflow_id"],
                "agent_run_id": r["agent_run_id"],
                "agent_role": r["agent_role"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload"]),
                "tokens_in": r["tokens_in"],
                "tokens_out": r["tokens_out"],
                "cost_usd": r["cost_usd"],
                "duration_ms": r["duration_ms"],
                "status": r["status"],
                "previous_event_id": r["previous_event_id"],
            }
            if r["previous_event_id"] != prev_id:
                return False, r["event_id"]
            if self._hash(body, prev_hash) != r["event_hash"]:
                return False, r["event_id"]
            prev_hash = r["event_hash"]
            prev_id = r["event_id"]
        return True, None

    def totals(self, workflow_id: str | None = None) -> dict[str, Any]:
        where = "WHERE workflow_id = ?" if workflow_id else ""
        params = (workflow_id,) if workflow_id else ()
        row = self.conn.execute(
            f"""SELECT COUNT(*) AS events, COALESCE(SUM(tokens_in),0) AS tokens_in,
                COALESCE(SUM(tokens_out),0) AS tokens_out,
                COALESCE(SUM(cost_usd),0) AS cost_usd FROM events {where}""",
            params,
        ).fetchone()
        return dict(row)
