"""Operational state store (projects, features, workflows, approvals).

This is workflow state, not history: history lives in the event store.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .budget import Budget, Spent
from .ids import new_id, utc_now


class NotFound(Exception):
    pass


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # -- projects ---------------------------------------------------------
    def create_project(self, name: str, repo_path: str | None = None) -> dict[str, Any]:
        project = {
            "id": new_id("prj"), "name": name,
            "repo_path": repo_path, "created_at": utc_now(),
        }
        self.conn.execute(
            "INSERT INTO projects (id, name, repo_path, created_at) VALUES (?,?,?,?)",
            (project["id"], name, repo_path, project["created_at"]),
        )
        self.conn.commit()
        return project

    def get_project(self, name: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM projects WHERE name = ? OR id = ?", (name, name)
        ).fetchone()
        if not row:
            raise NotFound(f"project not found: {name}")
        return dict(row)

    def list_projects(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM projects ORDER BY created_at").fetchall()]

    def set_project_repo(self, project_id: str, repo_path: str) -> None:
        self.conn.execute(
            "UPDATE projects SET repo_path = ? WHERE id = ?", (repo_path, project_id))
        self.conn.commit()

    # -- features ---------------------------------------------------------
    def create_feature(self, project_id: str, name: str, objective: str) -> dict[str, Any]:
        now = utc_now()
        feature = {
            "id": new_id("feat"), "project_id": project_id, "name": name,
            "objective": objective, "state": "DRAFT",
            "created_at": now, "updated_at": now,
        }
        self.conn.execute(
            """INSERT INTO features (id, project_id, name, objective, state,
               created_at, updated_at) VALUES (?,?,?,?,?,?,?)""",
            tuple(feature.values()),
        )
        self.conn.commit()
        return feature

    def get_feature(self, project_id: str, name: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM features WHERE project_id = ? AND (name = ? OR id = ?)",
            (project_id, name, name),
        ).fetchone()
        if not row:
            raise NotFound(f"feature not found: {name}")
        return dict(row)

    def list_features(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = self.conn.execute(
                "SELECT * FROM features WHERE project_id = ? ORDER BY created_at",
                (project_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM features ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    # -- workflows ----------------------------------------------------------
    def create_workflow(self, feature_id: str, kind: str, budget: Budget) -> dict[str, Any]:
        now = utc_now()
        workflow = {
            "id": new_id("wf"), "feature_id": feature_id, "kind": kind,
            "state": "DRAFT", "budget": budget.model_dump_json(),
            "spent": Spent().model_dump_json(), "created_at": now, "updated_at": now,
        }
        self.conn.execute(
            """INSERT INTO workflows (id, feature_id, kind, state, budget, spent,
               created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
            tuple(workflow.values()),
        )
        self.conn.commit()
        return workflow

    def get_workflow(self, workflow_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if not row:
            raise NotFound(f"workflow not found: {workflow_id}")
        return dict(row)

    def list_workflows(self, feature_id: str | None = None) -> list[dict[str, Any]]:
        if feature_id:
            rows = self.conn.execute(
                "SELECT * FROM workflows WHERE feature_id = ? ORDER BY created_at",
                (feature_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM workflows ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def set_workflow_state(self, workflow_id: str, state: str) -> None:
        self.conn.execute(
            "UPDATE workflows SET state = ?, updated_at = ? WHERE id = ?",
            (state, utc_now(), workflow_id))
        self.conn.commit()

    def save_spent(self, workflow_id: str, spent: Spent) -> None:
        self.conn.execute(
            "UPDATE workflows SET spent = ?, updated_at = ? WHERE id = ?",
            (spent.model_dump_json(), utc_now(), workflow_id))
        self.conn.commit()

    def load_budget(self, workflow: dict[str, Any]) -> tuple[Budget, Spent]:
        return (
            Budget.model_validate(json.loads(workflow["budget"])),
            Spent.model_validate(json.loads(workflow["spent"])),
        )

    # -- approvals ----------------------------------------------------------
    def request_approval(self, workflow_id: str, gate: str, reason: str) -> dict[str, Any]:
        approval = {
            "id": new_id("apr"), "workflow_id": workflow_id, "gate": gate,
            "status": "pending", "reason": reason, "requested_at": utc_now(),
        }
        self.conn.execute(
            """INSERT INTO approvals (id, workflow_id, gate, status, reason,
               requested_at) VALUES (?,?,?,?,?,?)""",
            tuple(approval.values()),
        )
        self.conn.commit()
        return approval

    def decide_approval(self, workflow_id: str, gate: str, approve: bool,
                        decided_by: str, reason: str = "") -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT * FROM approvals WHERE workflow_id = ? AND gate = ?
               AND status = 'pending' ORDER BY requested_at DESC LIMIT 1""",
            (workflow_id, gate)).fetchone()
        if not row:
            raise NotFound(f"no pending approval for gate {gate} on {workflow_id}")
        status = "approved" if approve else "rejected"
        self.conn.execute(
            """UPDATE approvals SET status = ?, decided_at = ?, decided_by = ?,
               reason = ? WHERE id = ?""",
            (status, utc_now(), decided_by, reason or row["reason"], row["id"]))
        self.conn.commit()
        return {**dict(row), "status": status, "decided_by": decided_by}

    def approval_granted(self, workflow_id: str, gate: str) -> bool:
        row = self.conn.execute(
            """SELECT status FROM approvals WHERE workflow_id = ? AND gate = ?
               ORDER BY requested_at DESC LIMIT 1""",
            (workflow_id, gate)).fetchone()
        return bool(row and row["status"] == "approved")

    def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM approvals WHERE status = ? ORDER BY requested_at DESC",
                (status,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM approvals ORDER BY requested_at DESC").fetchall()
        return [dict(r) for r in rows]

    # -- agent runs -----------------------------------------------------------
    def start_agent_run(self, workflow_id: str, agent_role: str, objective: str,
                        model: str | None = None) -> dict[str, Any]:
        run = {
            "id": new_id("run"), "workflow_id": workflow_id, "agent_role": agent_role,
            "model": model, "objective": objective, "status": "running",
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
            "started_at": utc_now(), "finished_at": None,
        }
        self.conn.execute(
            """INSERT INTO agent_runs (id, workflow_id, agent_role, model, objective,
               status, tokens_in, tokens_out, cost_usd, started_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(run.values()),
        )
        self.conn.commit()
        return run

    def finish_agent_run(self, run_id: str, status: str, tokens_in: int = 0,
                         tokens_out: int = 0, cost_usd: float = 0.0) -> None:
        self.conn.execute(
            """UPDATE agent_runs SET status = ?, tokens_in = ?, tokens_out = ?,
               cost_usd = ?, finished_at = ? WHERE id = ?""",
            (status, tokens_in, tokens_out, cost_usd, utc_now(), run_id))
        self.conn.commit()

    def list_agent_runs(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        if workflow_id:
            rows = self.conn.execute(
                "SELECT * FROM agent_runs WHERE workflow_id = ? ORDER BY started_at",
                (workflow_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM agent_runs ORDER BY started_at DESC").fetchall()
        return [dict(r) for r in rows]

    # -- checkpoints ----------------------------------------------------------
    def record_checkpoint(self, workflow_id: str, checkpoint_id: str, kind: str,
                          git_ref: str | None, note: str = "") -> None:
        self.conn.execute(
            """INSERT INTO checkpoints (id, workflow_id, kind, git_ref, note,
               created_at) VALUES (?,?,?,?,?,?)""",
            (checkpoint_id, workflow_id, kind, git_ref, note, utc_now()))
        self.conn.commit()

    def list_checkpoints(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        if workflow_id:
            rows = self.conn.execute(
                "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY created_at",
                (workflow_id,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM checkpoints ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    # -- jobs (command-center background work) --------------------------------
    def upsert_job(self, job: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO jobs (id, kind, workflow_id, label, status, started_at,
               finished_at, error, result_state)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 kind=excluded.kind,
                 workflow_id=excluded.workflow_id,
                 label=excluded.label,
                 status=excluded.status,
                 started_at=excluded.started_at,
                 finished_at=excluded.finished_at,
                 error=excluded.error,
                 result_state=excluded.result_state
            """,
            (
                job["id"], job.get("kind", ""), job.get("workflow_id"),
                job.get("label", ""), job.get("status", "running"),
                job["started_at"], job.get("finished_at"),
                job.get("error"), job.get("result_state"),
            ),
        )
        self.conn.commit()

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {
            "kind", "workflow_id", "label", "status", "started_at",
            "finished_at", "error", "result_state",
        }
        cols = []
        vals: list[Any] = []
        for key, value in fields.items():
            if key in allowed:
                cols.append(f"{key} = ?")
                vals.append(value)
        if not cols:
            return
        vals.append(job_id)
        self.conn.execute(
            f"UPDATE jobs SET {', '.join(cols)} WHERE id = ?", vals
        )
        self.conn.commit()

    def list_jobs(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def running_workflow_ids(self) -> set[str]:
        rows = self.conn.execute(
            "SELECT workflow_id FROM jobs WHERE status = 'running' "
            "AND workflow_id IS NOT NULL"
        ).fetchall()
        return {r["workflow_id"] for r in rows if r["workflow_id"]}
