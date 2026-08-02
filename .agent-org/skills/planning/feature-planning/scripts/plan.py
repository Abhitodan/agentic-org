"""Planning checklist: acceptance criteria + path grounding, deterministically.

Contract:
- Gaps are ALWAYS recorded; `hard_fail` only decides whether gaps that block
  grounding flip `ok` to False.
- A missing/unreadable repo map or repo path degrades to an explicit gap —
  never a crash, never a silent pass.
- Hard errors (wrong argument types) raise; everything else returns a result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_ac_and_grounding"

# Gap codes (stable API — consumed by runner state and dashboards)
GAP_NO_AC = "no_acceptance_criteria"
GAP_UNGROUNDED = "ungrounded_paths"
GAP_NO_REPO = "repo_path_unavailable"
GAP_MAP_UNREADABLE = "repo_map_unreadable"


def _known_files_from_map(repo_map: Any) -> tuple[list[str], str | None]:
    """Return (known_files, gap_code_or_None). Never raises on bad input."""
    if repo_map is None:
        return [], None
    if isinstance(repo_map, dict):
        data = repo_map
    else:
        path = Path(str(repo_map))
        if not path.is_file():
            return [], GAP_MAP_UNREADABLE
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [], GAP_MAP_UNREADABLE
        if not isinstance(data, dict):
            return [], GAP_MAP_UNREADABLE
    known = [str(f) for f in (data.get("files") or [])]
    if not known and isinstance(data.get("modules"), list):
        known = [
            str(m.get("path") if isinstance(m, dict) else m)
            for m in data["modules"] if m
        ]
    return known, None


def run(
    charter: str,
    plan: str = "",
    repo_path: str | Path = "",
    repo_map: Any = None,
    hard_fail: bool = False,
) -> dict[str, Any]:
    if not isinstance(charter, str):
        raise TypeError(f"charter must be str, got {type(charter).__name__}")
    if not isinstance(plan, str):
        raise TypeError(f"plan must be str, got {type(plan).__name__}")

    from agentic_org.atl.criteria import parse_acceptance_criteria
    from agentic_org.coding.grounding import extract_cited_paths, missing_grounded_paths

    gaps: list[str] = []
    criteria = parse_acceptance_criteria(charter)
    if not criteria:
        gaps.append(GAP_NO_AC)

    combined = f"{charter}\n{plan}"
    cited = extract_cited_paths(combined)

    known, map_gap = _known_files_from_map(repo_map)
    if map_gap:
        gaps.append(map_gap)

    root = Path(repo_path) if str(repo_path).strip() else None
    missing: list[str] = []
    if root is None or not root.is_dir():
        # Grounding impossible: an explicit gap, not a silent pass.
        gaps.append(GAP_NO_REPO)
    else:
        missing = missing_grounded_paths(combined, root, known_files=known)
        if missing:
            gaps.append(GAP_UNGROUNDED)

    blocking = {GAP_UNGROUNDED, GAP_NO_REPO, GAP_MAP_UNREADABLE}
    ok = not (hard_fail and any(g in blocking for g in gaps))

    return {
        "ok": ok,
        "acceptance_criteria": [{"id": c.id, "text": c.text} for c in criteria],
        "cited_paths": cited,
        "missing_paths": missing,
        "gaps": gaps,
        "hard_fail": bool(hard_fail),
        "evidence": _EVIDENCE,
    }
