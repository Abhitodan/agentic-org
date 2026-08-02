"""Index feature (and project) documents into PageIndex trees + vectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..docs.workspace import FeatureWorkspace
from ..gateway.model_gateway import ModelGateway
from .pageindex import PageIndexStore, build_page_tree, iter_nodes
from .vectors import VectorStore


@dataclass
class IndexReport:
    project: str
    feature: str
    files_indexed: int = 0
    pageindex_trees: int = 0
    vector_chunks: int = 0
    paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "feature": self.feature,
            "files_indexed": self.files_indexed,
            "pageindex_trees": self.pageindex_trees,
            "vector_chunks": self.vector_chunks,
            "paths": self.paths,
        }


class DocumentIndexer:
    def __init__(
        self,
        root: Path,
        vectors: VectorStore,
        gateway: ModelGateway | None = None,
    ):
        self.root = Path(root)
        self.vectors = vectors
        self.gateway = gateway

    def index_feature(self, project: str, feature: str) -> IndexReport:
        ws = FeatureWorkspace(self.root, project, feature)
        if not ws.exists():
            raise FileNotFoundError(f"feature folder missing: {ws.dir}")
        ws.maintain()
        page = PageIndexStore(ws.dir)
        report = IndexReport(project=project, feature=feature)
        self.vectors.clear(project=project, feature=feature)

        for path in sorted(ws.dir.rglob("*.md")):
            rel = str(path.relative_to(ws.dir)).replace("\\", "/")
            if rel.startswith("artifacts/pageindex/"):
                continue
            if path.name == "README.md" and path.parent == ws.dir:
                # Still index feature README — useful for search.
                pass
            markdown = path.read_text(encoding="utf-8")
            tree_path = page.index_markdown(rel, markdown)
            tree = build_page_tree(markdown, doc_id=rel.replace("/", "__").removesuffix(".md"))
            sections = [
                {
                    "node_id": n.node_id,
                    "title": n.title,
                    "text": n.text,
                    "level": n.level,
                }
                for n in iter_nodes(tree)
            ]
            n_chunks = self.vectors.index_sections(
                sections, doc_path=rel, project=project, feature=feature,
            )
            report.files_indexed += 1
            report.pageindex_trees += 1
            report.vector_chunks += n_chunks
            report.paths.append(rel)
            _ = tree_path
        return report

    def index_all_features(self) -> list[dict[str, Any]]:
        reports = []
        projects = self.root / "projects"
        if not projects.is_dir():
            return reports
        for project_dir in sorted(projects.iterdir()):
            feats = project_dir / "features"
            if not feats.is_dir():
                continue
            for feature_dir in sorted(feats.iterdir()):
                if not feature_dir.is_dir():
                    continue
                report = self.index_feature(project_dir.name, feature_dir.name)
                reports.append(report.to_dict())
        return reports

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        project: str | None = None,
        feature: str | None = None,
        limit: int = 8,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        mode = mode.lower()
        out: dict[str, Any] = {"query": query, "mode": mode, "hits": []}

        vector_hits = []
        page_hits = []
        if mode in {"vector", "hybrid"}:
            vector_hits = [
                {
                    "method": "vector",
                    "score": h.score,
                    "title": h.title,
                    "text": h.text,
                    "doc_path": h.doc_path,
                    "node_id": h.node_id,
                    "project": h.project,
                    "feature": h.feature,
                }
                for h in self.vectors.search(
                    query, limit=limit, feature=feature, project=project,
                )
            ]
        if mode in {"pageindex", "hybrid"}:
            targets: list[FeatureWorkspace] = []
            if project and feature:
                targets.append(FeatureWorkspace(self.root, project, feature))
            else:
                projects = self.root / "projects"
                if projects.is_dir():
                    for p in projects.iterdir():
                        if project and p.name != project:
                            continue
                        feats = p / "features"
                        if not feats.is_dir():
                            continue
                        for f in feats.iterdir():
                            if feature and f.name != feature:
                                continue
                            if f.is_dir():
                                targets.append(FeatureWorkspace(self.root, p.name, f.name))
            for ws in targets:
                if not (ws.dir / "artifacts" / "pageindex").exists():
                    continue
                store = PageIndexStore(ws.dir)
                for hit in store.search(
                    query, gateway=self.gateway, use_llm=use_llm, limit=limit,
                ):
                    hit["method"] = hit.get("method", "pageindex")
                    hit["project"] = ws.project_name
                    hit["feature"] = ws.feature_name
                    page_hits.append(hit)

        if mode == "vector":
            out["hits"] = vector_hits[:limit]
        elif mode == "pageindex":
            page_hits.sort(key=lambda h: h.get("score", 0), reverse=True)
            out["hits"] = page_hits[:limit]
        else:
            # Hybrid: interleave by normalized rank
            merged = []
            for h in vector_hits:
                merged.append(h)
            for h in page_hits:
                merged.append(h)
            merged.sort(key=lambda h: h.get("score", 0), reverse=True)
            # Dedupe by doc_path+title
            seen = set()
            unique = []
            for h in merged:
                key = (h.get("doc_path"), h.get("title"), h.get("node_id"))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(h)
            out["hits"] = unique[:limit]
        return out
