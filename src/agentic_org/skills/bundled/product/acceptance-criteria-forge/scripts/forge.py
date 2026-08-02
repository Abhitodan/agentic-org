"""Check acceptance criteria are testable: observable, specific, unambiguous.

Contract:
- Testability is judged by observable structure (outcome markers, numbers,
  Given/When/Then), never by guessing intent.
- A criterion built only from feeling-words ("works properly") is an error:
  no test can be derived from it.
"""

from __future__ import annotations

import re
from typing import Any

_EVIDENCE = "deterministic_ac_testability"

MIN_CRITERION_CHARS = 15

# Conjunctions that fuse two guarantees into one untestable criterion.
_COMPOUND = re.compile(r"\b(?:\sand\salso\s|\s;\s)|,\s+and\s+then\s", re.IGNORECASE)

_GWT = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.IGNORECASE | re.DOTALL)


def run(
    criteria: Any = None,
    story_id: str = "",
    require_gherkin: bool = False,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, story_from_dict

    story = story_from_dict({"id": story_id or "AC-SET", "acceptance_criteria": criteria})
    parsed = story.acceptance_criteria
    findings = FindingList()
    if not parsed:
        findings.error("no_criteria", "no acceptance criteria supplied", story_id)
        return build_result(findings, _EVIDENCE, criterion_count=0, criteria=[])

    seen_ids: set[str] = set()
    testable = 0
    for criterion in parsed:
        subject = f"{story_id}/{criterion.id}" if story_id else criterion.id

        if criterion.id in seen_ids:
            findings.error(
                "duplicate_criterion_id",
                f"criterion id {criterion.id!r} reused",
                subject,
                "id",
            )
        seen_ids.add(criterion.id)

        if len(criterion.text) < MIN_CRITERION_CHARS:
            findings.error(
                "criterion_too_short",
                f"under {MIN_CRITERION_CHARS} characters; cannot express a guarantee",
                subject,
                "text",
            )

        vague = criterion.vague_terms()
        measurable = criterion.is_measurable()
        if not measurable:
            findings.error(
                "not_measurable",
                "no observable outcome: add an expected result, a number, or "
                "a Given/When/Then structure",
                subject,
                "text",
            )
        else:
            testable += 1
        if vague:
            severity = findings.error if not measurable else findings.warn
            severity(
                "vague_wording",
                f"subjective term(s) {', '.join(vague)} — state the observable outcome",
                subject,
                "text",
            )

        if _COMPOUND.search(criterion.text):
            findings.warn(
                "compound_criterion",
                "criterion asserts more than one guarantee; split it",
                subject,
                "text",
            )

        if require_gherkin and not _GWT.search(criterion.text):
            findings.warn(
                "not_gherkin",
                "Given/When/Then structure required by this team but absent",
                subject,
                "text",
            )

    return build_result(
        findings,
        _EVIDENCE,
        criterion_count=len(parsed),
        testable_count=testable,
        criteria=[
            {
                "id": c.id,
                "measurable": c.is_measurable(),
                "vague_terms": c.vague_terms(),
            }
            for c in parsed
        ],
    )
