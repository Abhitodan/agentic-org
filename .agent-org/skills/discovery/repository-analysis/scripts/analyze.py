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
    if out_dir is not None:
        json_path, md_path = save_repo_map(repo_map, Path(out_dir))
        artifacts = [str(json_path), str(md_path)]

    return {
        "ok": True,
        "summary": summarize_repo_map(repo_map),
        "file_count": repo_map["file_count"],
        "languages": repo_map["languages"],
        "tests": len(repo_map.get("tests") or []),
        "entry_points": len(repo_map.get("entry_points") or []),
        "artifacts": artifacts,
        "repo_map": repo_map,
        "evidence": _EVIDENCE,
    }
