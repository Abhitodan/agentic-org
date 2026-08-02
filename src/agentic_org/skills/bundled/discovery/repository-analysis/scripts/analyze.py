"""Deterministic repository mapping: AST + filesystem, zero LLM, zero network.

Contract:
- Everything in the result was extracted from disk; there is no inference
  step. A file either exists or it is not in the map.
- A missing repository is a hard error (raises, surfaces as skill.failed) —
  mapping nothing must never look like mapping something.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_ast_and_filesystem"


def run(repo_path: str | Path, out_dir: str | Path | None = None) -> dict[str, Any]:
    from agentic_org.repo_intel.mapper import (
        build_repo_map,
        save_repo_map,
        summarize_repo_map,
    )

    repo = Path(repo_path)
    if not repo.is_dir():
        raise FileNotFoundError(
            f"repository not found: {repo} — mapping requires an existing directory"
        )

    repo_map = build_repo_map(repo)
    artifacts: list[str] = []
    graph_meta: dict[str, Any] = {}
    if out_dir is not None:
        json_path, md_path = save_repo_map(repo_map, Path(out_dir))
        artifacts = [str(json_path), str(md_path)]
        # Persist the code graph beside the map so review can load impact.
        try:
            from agentic_org.code_graph import build_code_graph, save_graph

            graph_dir = Path(out_dir) / "code-graph"
            graph = build_code_graph(repo)
            saved = save_graph(graph, graph_dir)
            artifacts.extend([str(saved), str(graph_dir / "index.sqlite")])
            graph_meta = {
                "graph_dir": str(graph_dir),
                "node_count": graph["node_count"],
                "edge_count": graph["edge_count"],
            }
        except Exception as exc:  # graph is additive; map still succeeds
            graph_meta = {"graph_error": f"{type(exc).__name__}: {exc}"}

    return {
        "ok": True,
        "summary": summarize_repo_map(repo_map),
        "file_count": repo_map["file_count"],
        "languages": repo_map["languages"],
        "tests": len(repo_map.get("tests") or []),
        "entry_points": len(repo_map.get("entry_points") or []),
        "artifacts": artifacts,
        "repo_map": repo_map,
        "code_graph": graph_meta,
        "evidence": _EVIDENCE,
    }
