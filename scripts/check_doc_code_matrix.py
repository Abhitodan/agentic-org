#!/usr/bin/env python3
"""Fail if docs deny capabilities that exist in src/ (Phase 0 anti-manipulation)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "agentic_org"

# If these symbols exist in src, these phrases in docs/README are contradictions.
CHECKS: list[tuple[str, str, list[str]]] = [
    (
        "node_implement",
        "Implementation / release nodes exist in runner",
        [
            r"Implementation, test, review, and release agents are \*\*not built\*\*",
            r"Implementation/test/review nodes beyond `plan` are not built",
            r"no implement node",
        ],
    ),
    (
        "node_release",
        "Release node exists",
        [r"release agents are \*\*not built\*\*"],
    ),
    (
        "McpGateway",
        "MCP gateway class exists (may still be unused on runner path)",
        [r"MCP not enforced"],  # soft; allow "library only" wording
    ),
]

# Global forbidden when CI file exists
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def _src_haystack() -> str:
    parts = []
    for path in SRC.rglob("*.py"):
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def _doc_paths() -> list[Path]:
    paths = [ROOT / "README.md"]
    docs = ROOT / "docs"
    if docs.is_dir():
        paths.extend(sorted(docs.rglob("*.md")))
    return [p for p in paths if p.is_file()]


def main() -> int:
    hay = _src_haystack()
    errors: list[str] = []

    if CI_PATH.is_file():
        for path in _doc_paths():
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if rel.startswith("docs/DEVELOPMENT_REVIEW") or \
               "path-to-10" in rel or "IMPROVEMENT_PLAN" in rel:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\bNo CI\b", text) or re.search(r"No CI workflow", text):
                errors.append(
                    f"{rel}: claims no CI but {CI_PATH.relative_to(ROOT)} exists"
                )

    for symbol, label, patterns in CHECKS:
        if symbol not in hay:
            continue
        for path in _doc_paths():
            # Skip historical review docs that quote the bug.
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            if rel.startswith("docs/DEVELOPMENT_REVIEW") or \
               rel.startswith("docs/superpowers/plans/2026-08-01-path"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    errors.append(
                        f"{rel}: pattern /{pat}/ contradicts presence of "
                        f"{symbol} ({label})"
                    )

    if errors:
        print("DOC/CODE MATRIX FAILURES (Phase 0):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("doc/code matrix OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
