"""Path grounding: cited file paths in charter/plan must exist in the repo."""

from __future__ import annotations

import re
from pathlib import Path

# Paths that look like source/docs references (not URLs).
_PATH_RE = re.compile(
    r"(?:^|[\s`\"'(\[])("
    r"(?:[\w.-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|md|yaml|yml|toml|json|sql|css|html)"
    r")(?:$|[\s`\"')\],:])"
)


def extract_cited_paths(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _PATH_RE.finditer(text or ""):
        rel = match.group(1).replace("\\", "/").lstrip("./")
        if rel not in seen:
            seen.add(rel)
            found.append(rel)
    return found


def missing_grounded_paths(
    text: str,
    repo_root: Path,
    *,
    known_files: list[str] | None = None,
) -> list[str]:
    """Return cited relative paths that are not on disk and not in known_files."""
    known = {p.replace("\\", "/") for p in (known_files or [])}
    missing: list[str] = []
    root = repo_root.resolve()
    for rel in extract_cited_paths(text):
        if rel in known:
            continue
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            missing.append(rel)
            continue
        if not candidate.exists() and rel not in known:
            missing.append(rel)
    return missing
