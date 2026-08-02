"""Index and query the persistent Python code graph.

Modes:
- index: build + save graph
- impact: reverse dependents of paths
- review-pack: ranked files for a diff
- query: filter nodes/edges
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_EVIDENCE_INDEX = "deterministic_python_ast_graph"


def run(
    mode: str = "index",
    repo_path: str | Path | None = None,
    graph_dir: str | Path | None = None,
    paths: list[str] | None = None,
    changed_paths: list[str] | None = None,
    include_inferred: bool = True,
    max_files: int = 20,
    path: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    from agentic_org.code_graph import (
        build_code_graph,
        impact,
        load_graph,
        query,
        review_pack,
        save_graph,
    )

    normalized = str(mode or "index").strip().lower().replace("_", "-")
    if normalized == "index":
        if not repo_path:
            raise ValueError("repo_path is required for index")
        root = Path(repo_path)
        if not root.is_dir():
            raise FileNotFoundError(f"repository not found: {root}")
        graph = build_code_graph(root)
        out = Path(graph_dir) if graph_dir else root / ".agent-org" / "state" / "code-graph"
        saved = save_graph(graph, out)
        return {
            "ok": True,
            "mode": "index",
            "node_count": graph["node_count"],
            "edge_count": graph["edge_count"],
            "graph_dir": str(out),
            "artifacts": [str(saved), str(out / "index.sqlite")],
            "evidence": _EVIDENCE_INDEX,
        }

    gdir = Path(graph_dir) if graph_dir else None
    if gdir is None and repo_path:
        gdir = Path(repo_path) / ".agent-org" / "state" / "code-graph"
    if gdir is None or not (gdir / "graph.json").is_file():
        return {
            "ok": False,
            "mode": normalized,
            "reason": "code graph missing; run mode=index first",
            "evidence": "deterministic_graph_impact" if normalized == "impact"
            else "deterministic_graph_review_pack" if normalized == "review-pack"
            else "deterministic_graph_query",
        }

    graph = load_graph(gdir)
    if normalized == "impact":
        result = impact(
            graph, paths or changed_paths or [],
            include_inferred=include_inferred,
        )
        result["mode"] = "impact"
        result["graph_dir"] = str(gdir)
        return result
    if normalized in ("review-pack", "review_pack"):
        result = review_pack(
            graph, changed_paths or paths or [], max_files=max_files,
        )
        result["mode"] = "review-pack"
        result["graph_dir"] = str(gdir)
        return result
    if normalized == "query":
        result = query(graph, path=path, kind=kind)
        result["mode"] = "query"
        result["graph_dir"] = str(gdir)
        return result
    raise ValueError(
        f"mode must be index|impact|review-pack|query, got {mode!r}"
    )
