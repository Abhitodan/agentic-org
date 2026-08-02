"""Work-package plan JSON (Phase 3) — component-scoped execute units."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .topology import ProductTopology

STATUSES = ("pending", "running", "done", "failed", "skipped")


@dataclass
class WorkPackage:
    id: str
    component_id: str
    objective: str = ""
    status: str = "pending"
    order: int = 100
    test_command: str | None = None
    actions_file: str | None = None  # relative to feature artifacts/
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPackage":
        status = str(data.get("status") or "pending")
        if status not in STATUSES:
            status = "pending"
        return cls(
            id=str(data["id"]),
            component_id=str(data["component_id"]),
            objective=str(data.get("objective") or ""),
            status=status,
            order=int(data.get("order") or 100),
            test_command=(
                str(data["test_command"]) if data.get("test_command") else None
            ),
            actions_file=(
                str(data["actions_file"]) if data.get("actions_file") else None
            ),
            notes=list(data.get("notes") or []),
        )


@dataclass
class WorkPackagePlan:
    version: int = 1
    packages: list[WorkPackage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "packages": [p.to_dict() for p in self.packages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkPackagePlan":
        pkgs = [
            WorkPackage.from_dict(p)
            for p in (data.get("packages") or [])
            if isinstance(p, dict) and p.get("id") and p.get("component_id")
        ]
        return cls(version=int(data.get("version") or 1), packages=pkgs)


class WorkPackageError(ValueError):
    pass


def validate_plan(plan: WorkPackagePlan, topology: ProductTopology) -> list[str]:
    """Return list of validation errors (empty = ok)."""
    errors: list[str] = []
    seen: set[str] = set()
    for pkg in plan.packages:
        if pkg.id in seen:
            errors.append(f"duplicate package id: {pkg.id}")
        seen.add(pkg.id)
        comp = topology.component(pkg.component_id)
        if comp is None:
            errors.append(
                f"package {pkg.id}: unknown component_id {pkg.component_id}"
            )
        elif not comp.path:
            errors.append(
                f"package {pkg.id}: component {pkg.component_id} has no path"
            )
        if pkg.status not in STATUSES:
            errors.append(f"package {pkg.id}: bad status {pkg.status}")
    return errors


def work_packages_path(feature_dir: Path) -> Path:
    return feature_dir / "artifacts" / "work_packages.json"


def load_plan(feature_dir: Path) -> WorkPackagePlan | None:
    path = work_packages_path(feature_dir)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WorkPackageError("work_packages.json must be an object")
    return WorkPackagePlan.from_dict(data)


def save_plan(feature_dir: Path, plan: WorkPackagePlan) -> Path:
    path = work_packages_path(feature_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    return path


def seed_from_topology(
    topology: ProductTopology,
    objective: str,
    *,
    only_with_path: bool = True,
) -> WorkPackagePlan:
    """Suggest-only seed: one package per component in order_hint order."""
    ordered = sorted(topology.components, key=lambda c: (c.order_hint, c.id))
    packages: list[WorkPackage] = []
    for comp in ordered:
        if only_with_path and not comp.path:
            continue
        packages.append(WorkPackage(
            id=f"wp-{comp.id}",
            component_id=comp.id,
            objective=f"[{comp.kind}] {objective}",
            status="pending",
            order=comp.order_hint,
            test_command=comp.test_command,
            actions_file=f"wp_{comp.id}_actions.json",
        ))
    return WorkPackagePlan(packages=packages)


def parse_test_command(command: str | None) -> list[str] | None:
    if not command or not str(command).strip():
        return None
    return str(command).split()


def cross_component_checklist(
    plan: WorkPackagePlan,
    topology: ProductTopology,
) -> dict[str, Any]:
    """Pre-release validation: every package done; components have paths."""
    items = []
    for pkg in sorted(plan.packages, key=lambda p: (p.order, p.id)):
        comp = topology.component(pkg.component_id)
        ok = pkg.status == "done" and comp is not None and bool(comp.path)
        items.append({
            "package_id": pkg.id,
            "component_id": pkg.component_id,
            "status": pkg.status,
            "path": comp.path if comp else None,
            "ok": ok,
        })
    all_ok = bool(items) and all(i["ok"] for i in items)
    return {
        "ok": all_ok,
        "suggest_only": True,
        "items": items,
        "summary": (
            "all work packages done"
            if all_ok else
            "cross-component validation incomplete"
        ),
    }
