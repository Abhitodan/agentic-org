"""Scope verdict for a change set: keep, justify, or split.

Contract:
- Deterministic; no LLM, no network, no filesystem writes.
- Segment-aware allowlist matching (never loose substring prefixes).
- Token overlap is a secondary heuristic and is reported as such.
- Hard errors (bad argument types) raise; domain outcomes return ok/verdict.
"""

from __future__ import annotations

from typing import Any

# Generic words that carry no scope signal; never let them create a match.
_STOPWORDS = {
    "the", "and", "for", "fix", "add", "with", "that", "this", "from",
    "into", "new", "use", "update", "make", "change", "feature", "support",
}

# Verdict threshold: more than this fraction of out-of-scope paths => split.
_JUSTIFY_MAX_FRACTION = 1 / 3

_EVIDENCE = "deterministic_path_scope"


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _segments(path: str) -> list[str]:
    return [s for s in _normalize(path).split("/") if s]


def _covers(path_segs: list[str], allow_segs: list[str]) -> bool:
    """True when one is a whole-segment prefix of the other.

    allow "src" covers "src/x.py"; allow "src/x.py" covers "src" (directory
    touch) and the exact file. "s" never covers "src" — no substring games.
    """
    if not path_segs or not allow_segs:
        return False
    n = min(len(path_segs), len(allow_segs))
    return path_segs[:n] == allow_segs[:n]


def _tokens(text: str) -> set[str]:
    cleaned = (text or "").replace("/", " ").replace("_", " ").replace("-", " ")
    return {
        t.lower()
        for t in cleaned.split()
        if len(t) > 2 and t.lower() not in _STOPWORDS
    }


def _path_tokens(path: str) -> set[str]:
    segs = _segments(path)
    if segs:
        # Drop the file extension from the last segment: "mapper.py" -> "mapper"
        last = segs[-1]
        if "." in last:
            segs = segs[:-1] + [last.rsplit(".", 1)[0]]
    return _tokens(" ".join(segs))


def run(
    objective: str,
    changed_paths: list[str] | None = None,
    allow_prefixes: list[str] | None = None,
    plan_text: str = "",
) -> dict[str, Any]:
    if not isinstance(objective, str):
        raise TypeError(f"objective must be str, got {type(objective).__name__}")
    if changed_paths is not None and not isinstance(changed_paths, (list, tuple)):
        raise TypeError("changed_paths must be a list of relative paths")

    from agentic_org.coding.grounding import extract_cited_paths

    paths = [_normalize(str(p)) for p in (changed_paths or []) if str(p).strip()]
    allows = [_normalize(str(p)) for p in (allow_prefixes or []) if str(p).strip()]
    cited = [_normalize(p) for p in extract_cited_paths(plan_text or "")]
    allowlist = list(dict.fromkeys(allows + cited))
    allow_segs = [_segments(a) for a in allowlist]
    objective_tokens = _tokens(objective) | _tokens(plan_text)

    in_scope: list[str] = []
    out_of_scope: list[str] = []
    matched_by: dict[str, str] = {}
    for path in paths:
        segs = _segments(path)
        if any(_covers(segs, a) for a in allow_segs):
            in_scope.append(path)
            matched_by[path] = "allowlist"
        elif _path_tokens(path) & objective_tokens:
            in_scope.append(path)
            matched_by[path] = "token_overlap"
        else:
            out_of_scope.append(path)

    if not paths or not out_of_scope:
        verdict, ok = "keep", True
    elif len(out_of_scope) <= max(1, int(len(paths) * _JUSTIFY_MAX_FRACTION)):
        verdict, ok = "justify", True  # reviewer must acknowledge each path
    else:
        verdict, ok = "split", False

    return {
        "ok": ok,
        "verdict": verdict,
        "in_scope": in_scope,
        "out_of_scope": out_of_scope,
        "matched_by": matched_by,
        "allow_prefixes": allowlist,
        "heuristic": "segment_allowlist+token_overlap",
        "evidence": _EVIDENCE,
    }
