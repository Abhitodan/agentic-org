"""Product topology (mono | multi) stored as projects/<name>/product.yaml."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

COMPONENT_KINDS = (
    "main", "backend", "frontend", "sql", "ssis", "ssrs", "docs", "other",
)
SHAPES = ("mono", "multi")


@dataclass
class Component:
    id: str
    name: str
    kind: str = "main"
    path: str | None = None
    default_branch: str = "main"
    test_command: str | None = None
    order_hint: int = 100

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Component":
        kind = str(data.get("kind") or "main")
        if kind not in COMPONENT_KINDS:
            kind = "other"
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            kind=kind,
            path=(str(data["path"]) if data.get("path") else None),
            default_branch=str(data.get("default_branch") or "main"),
            test_command=(
                str(data["test_command"]) if data.get("test_command") else None
            ),
            order_hint=int(data.get("order_hint") or 100),
        )


@dataclass
class ProductTopology:
    name: str
    shape: str = "mono"
    components: list[Component] = field(default_factory=list)
    policies: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.shape not in SHAPES:
            raise ValueError(f"shape must be one of {SHAPES}")
        if not self.policies:
            self.policies = {
                "suggest_only": True,
                "human_gates": ["plan-approval", "release-approval"],
            }

    @property
    def primary_path(self) -> str | None:
        """Default repo path for Mode A runner (lowest order_hint with a path)."""
        ordered = sorted(self.components, key=lambda c: (c.order_hint, c.id))
        for c in ordered:
            if c.path:
                return c.path
        return None

    def runnable(self) -> bool:
        return bool(self.primary_path)

    def component(self, component_id: str) -> Component | None:
        for c in self.components:
            if c.id == component_id:
                return c
        return None

    def upsert_component(self, component: Component) -> None:
        rest = [c for c in self.components if c.id != component.id]
        rest.append(component)
        self.components = sorted(rest, key=lambda c: (c.order_hint, c.id))
        if len(self.components) > 1 and self.shape == "mono":
            self.shape = "multi"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "shape": self.shape,
            "components": [c.to_dict() for c in self.components],
            "policies": self.policies,
            "primary_path": self.primary_path,
            "runnable": self.runnable(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductTopology":
        comps = [
            Component.from_dict(c)
            for c in (data.get("components") or [])
            if isinstance(c, dict) and c.get("id")
        ]
        shape = str(data.get("shape") or ("multi" if len(comps) > 1 else "mono"))
        return cls(
            name=str(data.get("name") or ""),
            shape=shape if shape in SHAPES else "mono",
            components=comps,
            policies=dict(data.get("policies") or {}),
        )

    @classmethod
    def mono(cls, name: str, repo_path: str | None = None) -> "ProductTopology":
        comps = []
        if repo_path:
            comps.append(Component(
                id="main",
                name="Main",
                kind="main",
                path=str(Path(repo_path).resolve()),
                order_hint=10,
            ))
        else:
            comps.append(Component(
                id="main", name="Main", kind="main", path=None, order_hint=10,
            ))
        return cls(name=name, shape="mono", components=comps)


def topology_path(root: Path, product_name: str) -> Path:
    return Path(root) / "projects" / product_name / "product.yaml"


def load_topology(root: Path, product_name: str) -> ProductTopology | None:
    path = topology_path(root, product_name)
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid product.yaml: {path}")
    data.setdefault("name", product_name)
    topo = ProductTopology.from_dict(data)
    if not topo.name:
        topo.name = product_name
    return topo


def save_topology(root: Path, topo: ProductTopology) -> Path:
    path = topology_path(root, topo.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": topo.name,
        "shape": topo.shape,
        "components": [c.to_dict() for c in topo.components],
        "policies": topo.policies,
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def ensure_topology(
    root: Path,
    product_name: str,
    *,
    repo_path: str | None = None,
    shape: str = "mono",
) -> ProductTopology:
    """Load existing topology or create mono/multi bootstrap."""
    existing = load_topology(root, product_name)
    if existing:
        if repo_path and not existing.primary_path:
            existing.upsert_component(Component(
                id="main", name="Main", kind="main",
                path=str(Path(repo_path).resolve()), order_hint=10,
            ))
            save_topology(root, existing)
        return existing
    if shape == "multi":
        topo = ProductTopology(name=product_name, shape="multi", components=[])
        if repo_path:
            topo.upsert_component(Component(
                id="main", name="Main", kind="main",
                path=str(Path(repo_path).resolve()), order_hint=10,
            ))
    else:
        topo = ProductTopology.mono(product_name, repo_path)
    save_topology(root, topo)
    return topo


def sync_repo_path_from_topology(
    store: Any,
    project_id: str,
    topo: ProductTopology,
) -> None:
    """Keep projects.repo_path aligned with primary component for Mode A."""
    path = topo.primary_path
    if path:
        store.set_project_repo(project_id, path)


def list_product_topologies(root: Path) -> list[ProductTopology]:
    projects = Path(root) / "projects"
    if not projects.is_dir():
        return []
    out: list[ProductTopology] = []
    for d in sorted(projects.iterdir()):
        if not d.is_dir():
            continue
        topo = load_topology(root, d.name)
        if topo:
            out.append(topo)
        else:
            out.append(ProductTopology.mono(d.name, None))
    return out
