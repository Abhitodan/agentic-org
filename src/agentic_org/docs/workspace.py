"""Create and maintain feature folders and managed documents.

Scaffold layout under projects/<project>/features/<feature>/:

    FEATURE_BRAIN.md
    feature.yaml
    documents.json          # manifest of managed docs
    charter.md              # from template (stub until workflow fills)
    implementation-plan.md
    decisions/ sessions/ artifacts/ summaries/ docs/
    artifacts/pageindex/    # PageIndex trees
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..brain.feature_brain import BRAIN_SECTIONS, FeatureBrain
from ..core.ids import utc_now

DOC_KINDS = {
    "brain": "FEATURE_BRAIN.md",
    "charter": "charter.md",
    "plan": "implementation-plan.md",
    "repo-map": "artifacts/repo-map.md",
    "manifest": "documents.json",
}

SUBDIRS = (
    "decisions",
    "sessions",
    "artifacts",
    "summaries",
    "docs",
    "artifacts/pageindex",
)


@dataclass
class DocRecord:
    kind: str
    path: str
    status: str  # stub | draft | approved | archived
    updated_at: str
    source: str  # template | workflow | human | agent
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": self.path,
            "status": self.status,
            "updated_at": self.updated_at,
            "source": self.source,
            "title": self.title,
        }


class FeatureWorkspace:
    """Filesystem + manifest lifecycle for one feature folder."""

    def __init__(self, root: Path, project_name: str, feature_name: str):
        self.root = Path(root)
        self.project_name = project_name
        self.feature_name = feature_name
        self.brain = FeatureBrain(root, project_name, feature_name)
        self.dir = self.brain.dir
        self.manifest_path = self.dir / "documents.json"
        self.templates_dir = self.root / ".agent-org" / "templates"

    def exists(self) -> bool:
        return self.dir.is_dir()

    def create(self, feature_id: str, objective: str) -> Path:
        """Create brain, subdirs, stub docs from templates, and manifest."""
        self.brain.create(feature_id, objective)
        self._ensure_subdirs()
        self.ensure_doc("charter", from_template=True, status="stub")
        self.ensure_doc("plan", from_template=True, status="stub")
        self._register("brain", DOC_KINDS["brain"], status="draft", source="template",
                       title=f"Feature Brain: {self.feature_name}")
        self._write_readme()
        return self.dir

    def maintain(self) -> dict[str, Any]:
        """Ensure folder shape, stub missing managed docs, refresh manifest paths."""
        created: list[str] = []
        if not self.brain.exists():
            raise FileNotFoundError(f"feature brain missing: {self.dir}")
        self._ensure_subdirs()
        for kind in ("charter", "plan"):
            path = self.dir / DOC_KINDS[kind]
            if not path.exists():
                self.ensure_doc(kind, from_template=True, status="stub")
                created.append(kind)
        self._register("brain", DOC_KINDS["brain"], status="draft", source="maintain",
                       title=f"Feature Brain: {self.feature_name}")
        if (self.dir / DOC_KINDS["repo-map"]).exists():
            self._register("repo-map", DOC_KINDS["repo-map"], status="draft",
                           source="maintain", title="Repository Map")
        self._write_readme()
        return {
            "feature": self.feature_name,
            "path": str(self.dir),
            "created_stubs": created,
            "documents": self.list_docs(),
        }

    def ensure_doc(
        self,
        kind: str,
        *,
        from_template: bool = True,
        status: str = "stub",
        content: str | None = None,
    ) -> Path:
        rel = DOC_KINDS.get(kind)
        if not rel:
            raise KeyError(f"unknown document kind: {kind}")
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            if content is not None:
                path.write_text(content, encoding="utf-8")
                source = "agent"
            elif from_template:
                path.write_text(self._template_body(kind), encoding="utf-8")
                source = "template"
            else:
                path.write_text(f"# {kind}\n\n_TBD_\n", encoding="utf-8")
                source = "human"
            self._register(kind, rel, status=status, source=source, title=kind)
        return path

    def write_doc(
        self,
        kind: str,
        content: str,
        *,
        source: str = "human",
        status: str = "draft",
        title: str = "",
    ) -> Path:
        rel = DOC_KINDS.get(kind)
        if not rel:
            # Allow custom docs under docs/
            if kind.startswith("docs/") or "/" in kind:
                rel = kind if kind.endswith(".md") else f"{kind}.md"
            else:
                rel = f"docs/{kind}.md"
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._register(
            kind if kind in DOC_KINDS else rel,
            rel,
            status=status,
            source=source,
            title=title or path.stem,
        )
        return path

    def list_docs(self) -> list[dict[str, Any]]:
        manifest = self._load_manifest()
        docs = list(manifest.get("documents") or [])
        # Discover extra markdown under the feature folder.
        known = {d["path"] for d in docs}
        for path in sorted(self.dir.rglob("*.md")):
            rel = str(path.relative_to(self.dir)).replace("\\", "/")
            if rel in known or rel.startswith("artifacts/pageindex/"):
                continue
            docs.append({
                "kind": "discovered",
                "path": rel,
                "status": "draft",
                "updated_at": utc_now(),
                "source": "discovered",
                "title": path.stem,
            })
        return docs

    def get_doc_path(self, kind: str) -> Path:
        rel = DOC_KINDS.get(kind)
        if not rel:
            raise KeyError(f"unknown document kind: {kind}")
        return self.dir / rel

    def add_decision(self, title: str, body: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in title)[:60]
        path = self.dir / "decisions" / f"{utc_now()[:10]}_{safe}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")
        self._register(
            f"decision:{safe}", str(path.relative_to(self.dir)).replace("\\", "/"),
            status="draft", source="human", title=title,
        )
        return path

    def _ensure_subdirs(self) -> None:
        for sub in SUBDIRS:
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    def _template_body(self, kind: str) -> str:
        mapping = {
            "charter": "feature-charter.md",
            "plan": "sprint-plan.md",
        }
        name = mapping.get(kind)
        if name:
            template = self.templates_dir / name
            if template.exists():
                return template.read_text(encoding="utf-8")
        if kind == "plan":
            return (
                "# Implementation Plan\n\n## Epics\n\n_TBD_\n\n"
                "## Stories\n\n_TBD_\n\n## Test Expectations\n\n_TBD_\n\n"
                "## Rollback Notes\n\n_TBD_\n"
            )
        return f"# {kind}\n\n_TBD_\n"

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "feature": self.feature_name,
                "project": self.project_name,
                "documents": [],
                "updated_at": utc_now(),
            }
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _register(
        self,
        kind: str,
        rel: str,
        *,
        status: str,
        source: str,
        title: str,
    ) -> None:
        manifest = self._load_manifest()
        docs = [d for d in manifest.get("documents", []) if d.get("path") != rel]
        docs.append(DocRecord(
            kind=kind, path=rel, status=status, updated_at=utc_now(),
            source=source, title=title,
        ).to_dict())
        manifest["documents"] = docs
        manifest["updated_at"] = utc_now()
        manifest["feature"] = self.feature_name
        manifest["project"] = self.project_name
        manifest["brain_sections"] = list(BRAIN_SECTIONS)
        self.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _write_readme(self) -> None:
        readme = self.dir / "README.md"
        body = (
            f"# Feature: {self.feature_name}\n\n"
            f"Project: `{self.project_name}`\n\n"
            "## Managed documents\n\n"
            "- `FEATURE_BRAIN.md` — Tier-1 operational memory\n"
            "- `charter.md` — feature charter\n"
            "- `implementation-plan.md` — implementation plan\n"
            "- `documents.json` — manifest\n"
            "- `artifacts/pageindex/` — PageIndex trees\n"
            "- `decisions/`, `sessions/`, `summaries/`, `docs/`\n\n"
            "Maintain with `agentctl docs-maintain` / `agentctl docs-index`.\n"
        )
        if not readme.exists():
            readme.write_text(body, encoding="utf-8")


def project_workspace(
    root: Path,
    project_name: str,
    *,
    repo_path: str | None = None,
    shape: str = "mono",
) -> Path:
    """Ensure product folder, README, features/, and product.yaml topology."""
    from ..products.topology import ensure_topology

    path = root / "projects" / project_name
    path.mkdir(parents=True, exist_ok=True)
    readme = path / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# Product: {project_name}\n\n"
            "Features live under `features/<feature-name>/`.\n"
            "Topology (mono/multi components) is in `product.yaml`.\n",
            encoding="utf-8",
        )
    features = path / "features"
    features.mkdir(exist_ok=True)
    ensure_topology(root, project_name, repo_path=repo_path, shape=shape)
    return path
