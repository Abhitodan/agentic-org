"""Acceptance Trace: criterion ↔ test linkage + seal + gate digests."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .criteria import AcceptanceCriterion
from .seal import OracleSeal

LINKAGE_FILENAME = "acceptance_linkage.json"
TRACE_FILENAME = "acceptance_trace.json"
SEAL_FILENAME = "oracle_seal.json"

# Test source must mention the criterion or an explicit cover marker.
_COVERS = re.compile(r"ATL_COVERS:\s*(AC-\d+)", re.IGNORECASE)


@dataclass
class AcceptanceTrace:
    version: int
    workflow_id: str
    criteria: list[dict[str, str]]
    linkage: dict[str, list[str]]
    seal: dict[str, Any]
    writes_count: int
    gate_digests: dict[str, str]
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def load_linkage(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    links = data.get("links") if isinstance(data, dict) else data
    if not isinstance(links, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, vals in links.items():
        cid = str(key).upper() if str(key).upper().startswith("AC-") else str(key)
        if not str(cid).upper().startswith("AC-"):
            # normalize AC-1
            m = re.match(r"(?i)ac-?(\d+)", str(key))
            cid = f"AC-{int(m.group(1))}" if m else str(key)
        else:
            m = re.match(r"(?i)ac-(\d+)", cid)
            cid = f"AC-{int(m.group(1))}" if m else cid
        out[cid] = [str(v) for v in (vals or [])]
    return out


def save_linkage(path: Path, links: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "links": links}, indent=2),
        encoding="utf-8",
    )


def nodeid_to_file(nodeid: str) -> str:
    """tests/test_x.py::test_foo -> tests/test_x.py"""
    return nodeid.split("::", 1)[0].replace("\\", "/")


def test_source_covers_criterion(repo: Path, nodeid: str, criterion_id: str) -> bool:
    rel = nodeid_to_file(nodeid)
    path = repo / rel
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if criterion_id in text:
        return True
    for match in _COVERS.finditer(text):
        if match.group(1).upper() == criterion_id.upper():
            return True
    return False


def build_acceptance_trace(
    *,
    workflow_id: str,
    criteria: list[AcceptanceCriterion],
    linkage: dict[str, list[str]],
    seal: OracleSeal,
    writes_count: int,
    gate_digests: dict[str, str],
) -> AcceptanceTrace:
    return AcceptanceTrace(
        version=1,
        workflow_id=workflow_id,
        criteria=[{"id": c.id, "text": c.text} for c in criteria],
        linkage=dict(linkage),
        seal=seal.to_dict(),
        writes_count=int(writes_count),
        gate_digests=dict(gate_digests),
    )
