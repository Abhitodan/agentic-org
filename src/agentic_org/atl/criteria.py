"""Parse structured acceptance-criterion IDs from feature charters."""

from __future__ import annotations

import re
from dataclasses import dataclass

# - AC-1: text  |  - **AC-1**: text  |  * [AC-1] text  |  - AC-1 text
_AC_LINE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?\[?AC-(\d+)\]?(?:\*\*)?\s*[:\-]?\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str  # e.g. AC-1
    text: str


def parse_acceptance_criteria(charter_text: str) -> list[AcceptanceCriterion]:
    """Extract AC-# criteria from charter markdown (order-preserving, unique)."""
    seen: set[str] = set()
    out: list[AcceptanceCriterion] = []
    for match in _AC_LINE.finditer(charter_text or ""):
        cid = f"AC-{int(match.group(1))}"
        if cid in seen:
            continue
        seen.add(cid)
        out.append(AcceptanceCriterion(id=cid, text=match.group(2).strip()))
    return out
