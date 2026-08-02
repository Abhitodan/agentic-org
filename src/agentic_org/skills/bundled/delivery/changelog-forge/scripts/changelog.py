"""Build a changelog from delivered stories; flag unattributed commits."""

from __future__ import annotations

import re
from typing import Any

_EVIDENCE = "deterministic_changelog_traceability"

_STORY_ID = re.compile(r"\b([A-Z]+-\d+)\b")


def run(
    stories: Any = None,
    commits: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, parse_stories

    parsed = parse_stories(stories)
    findings = FindingList()
    if not parsed:
        findings.error("no_stories", "no delivered stories for changelog")
        return build_result(findings, _EVIDENCE, entries=[], gaps=[])

    story_ids = {s.id.upper() for s in parsed if s.id}
    entries: list[dict[str, Any]] = []
    for story in parsed:
        ac_text = "; ".join(c.text for c in story.acceptance_criteria) or story.title
        entries.append({
            "id": story.id,
            "title": story.title or story.id,
            "summary": ac_text[:240],
        })

    gaps: list[str] = []
    attributed = 0
    for index, raw in enumerate(commits or [], 1):
        if isinstance(raw, dict):
            sha = str(raw.get("sha") or raw.get("id") or f"commit-{index}")
            message = str(raw.get("message") or raw.get("subject") or "")
        else:
            sha, message = f"commit-{index}", str(raw)
        found = {m.group(1).upper() for m in _STORY_ID.finditer(message)}
        if found & story_ids:
            attributed += 1
        elif found:
            gaps.append(sha)
            findings.warn(
                "commit_unknown_story",
                f"references {sorted(found)} not in delivered set",
                sha,
            )
        else:
            gaps.append(sha)
            findings.warn(
                "unattributed_commit",
                "commit has no story id; not silently omitted",
                sha,
            )

    return build_result(
        findings,
        _EVIDENCE,
        entries=entries,
        entry_count=len(entries),
        commit_count=len(list(commits or [])),
        attributed_commits=attributed,
        gaps=gaps,
    )
