"""Execute work packages against topology components (Phase 3)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..coding.implementer import Implementer, default_test_command
from ..core.ids import new_id
from .topology import ProductTopology
from .work_packages import (
    WorkPackage,
    WorkPackagePlan,
    parse_test_command,
    save_plan,
    validate_plan,
)


@dataclass
class PackageExecResult:
    package_id: str
    component_id: str
    ok: bool
    reason: str = ""
    task_id: str | None = None
    worktree: str | None = None
    actions_applied: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass
class MultiExecResult:
    ok: bool
    reason: str = ""
    packages: list[PackageExecResult] = field(default_factory=list)
    # Primary (last successful) worktree for merge compatibility
    primary_task_id: str | None = None
    primary_worktree: str | None = None
    primary_repo: str | None = None
    primary_branch: str | None = None


def resolve_test_command(
    package: WorkPackage,
    topology: ProductTopology,
) -> list[str]:
    if package.test_command:
        parsed = parse_test_command(package.test_command)
        if parsed:
            return parsed
    comp = topology.component(package.component_id)
    if comp and comp.test_command:
        parsed = parse_test_command(comp.test_command)
        if parsed:
            return parsed
    return default_test_command()


def _load_actions(
    feature_dir: Path,
    package: WorkPackage,
    fallback: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    artifacts = feature_dir / "artifacts"
    if package.actions_file:
        path = artifacts / package.actions_file
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                raise ValueError(f"actions file must be array: {path}")
            return data
    # Fallback: shared implementation_actions.json for primary-only / mono
    shared = artifacts / "implementation_actions.json"
    if shared.exists() and fallback is None:
        data = json.loads(shared.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    return fallback


def execute_work_packages(
    *,
    topology: ProductTopology,
    plan: WorkPackagePlan,
    feature_dir: Path,
    worktrees_root: Path,
    org_root: Path,
    objective: str = "",
    plan_text: str = "",
    gateway: Any | None = None,
    shared_actions: list[dict[str, Any]] | None = None,
) -> MultiExecResult:
    """Run each pending package in order against its component repo."""
    errors = validate_plan(plan, topology)
    if errors:
        return MultiExecResult(ok=False, reason="; ".join(errors))

    ordered = sorted(plan.packages, key=lambda p: (p.order, p.id))
    results: list[PackageExecResult] = []
    primary_task = None
    primary_wt = None
    primary_repo = None
    primary_branch = None

    for pkg in ordered:
        if pkg.status in {"done", "skipped"}:
            results.append(PackageExecResult(
                package_id=pkg.id, component_id=pkg.component_id,
                ok=True, reason=f"already {pkg.status}",
            ))
            continue
        comp = topology.component(pkg.component_id)
        assert comp and comp.path  # validated
        repo = Path(comp.path)
        pkg.status = "running"
        save_plan(feature_dir, plan)
        try:
            actions = _load_actions(feature_dir, pkg, shared_actions)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            pkg.status = "failed"
            pkg.notes.append(str(exc))
            save_plan(feature_dir, plan)
            results.append(PackageExecResult(
                package_id=pkg.id, component_id=pkg.component_id,
                ok=False, reason=f"actions load: {exc}",
            ))
            return MultiExecResult(
                ok=False, reason=f"package {pkg.id} failed: {exc}",
                packages=results,
            )

        task_id = new_id("task")
        implementer = Implementer(repo, worktrees_root / pkg.id, org_root=org_root)
        test_cmd = resolve_test_command(pkg, topology)
        result = implementer.run(
            task_id,
            actions,
            gateway=gateway if actions is None else None,
            objective=pkg.objective or objective,
            plan_text=plan_text,
            test_command=test_cmd,
        )
        if not result.ok:
            pkg.status = "failed"
            pkg.notes.append(result.reason)
            save_plan(feature_dir, plan)
            results.append(PackageExecResult(
                package_id=pkg.id, component_id=pkg.component_id,
                ok=False, reason=result.reason, task_id=task_id,
                worktree=str(result.worktree) if result.worktree else None,
                actions_applied=result.actions_applied,
                notes=list(result.notes),
            ))
            return MultiExecResult(
                ok=False,
                reason=f"package {pkg.id} failed: {result.reason}",
                packages=results,
            )

        pkg.status = "done"
        pkg.notes.append(f"task={task_id}")
        save_plan(feature_dir, plan)
        results.append(PackageExecResult(
            package_id=pkg.id, component_id=pkg.component_id,
            ok=True, reason=result.reason, task_id=task_id,
            worktree=str(result.worktree) if result.worktree else None,
            actions_applied=result.actions_applied,
            notes=list(result.notes),
        ))
        primary_task = task_id
        primary_wt = str(result.worktree) if result.worktree else None
        primary_repo = str(repo)
        primary_branch = f"agent/{task_id}"

    if not results:
        return MultiExecResult(ok=False, reason="no work packages to execute")
    return MultiExecResult(
        ok=True,
        reason="all work packages passed tests",
        packages=results,
        primary_task_id=primary_task,
        primary_worktree=primary_wt,
        primary_repo=primary_repo,
        primary_branch=primary_branch,
    )
