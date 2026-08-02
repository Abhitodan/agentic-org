"""ATL completion lock — refuse COMPLETED without a valid Acceptance Trace."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .criteria import parse_acceptance_criteria
from .seal import OracleSeal, mint_seal, verify_seal_against_repo
from .trace import (
    LINKAGE_FILENAME,
    TRACE_FILENAME,
    AcceptanceTrace,
    build_acceptance_trace,
    load_linkage,
    test_source_covers_criterion,
)


@dataclass
class ATLDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    forge_class: str | None = None  # F1..F5 when a known forge pattern matches
    trace: AcceptanceTrace | None = None

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ("ok" if self.allowed else "denied")


def atl_enabled() -> bool:
    return os.environ.get("AGENTIC_ORG_ATL", "1").strip() not in {"0", "false", "False", "off"}


def unlocked_suite_green_allows_completed(*, suite_exit_code: int, writes_count: int = 0) -> bool:
    """Pre-ATL Mode A completion heuristic: suite green alone.

    Ignores writes / criterion coverage / seal freshness / gate digests.
    Used by the forge harness to show the hole ATL closes.
    """
    del writes_count  # intentionally unused — that is the hole
    return suite_exit_code == 0


def evaluate_atl(
    *,
    repo: Path,
    charter_text: str,
    feature_artifacts: Path,
    workflow_id: str,
    writes_count: int,
    gate_digests: dict[str, str],
    seal: OracleSeal | None = None,
    mint_if_missing: bool = True,
    org_root: Path | None = None,
) -> ATLDecision:
    """Evaluate whether COMPLETED is allowed under Acceptance-Trace Lock."""
    reasons: list[str] = []
    forge: str | None = None

    criteria = parse_acceptance_criteria(charter_text)
    if not criteria:
        return ATLDecision(
            allowed=False,
            reasons=["charter has no AC-# acceptance criteria"],
            forge_class="F3",
        )

    linkage_path = feature_artifacts / LINKAGE_FILENAME
    linkage = load_linkage(linkage_path)
    if not linkage:
        return ATLDecision(
            allowed=False,
            reasons=[f"missing linkage artifact: {LINKAGE_FILENAME}"],
            forge_class="F3",
        )

    if writes_count < 1:
        return ATLDecision(
            allowed=False,
            reasons=["empty implement: writes_count < 1"],
            forge_class="F1",
        )

    for gate in ("plan-approval", "release-approval"):
        digest = (gate_digests or {}).get(gate) or ""
        if not str(digest).strip():
            return ATLDecision(
                allowed=False,
                reasons=[f"missing gate digest for {gate}"],
                forge_class="F5",
            )

    # Seal: prefer provided; else mint fresh against current HEAD
    paths_to_hash: list[str] = []
    for nodeids in linkage.values():
        for nid in nodeids:
            paths_to_hash.append(nid.split("::", 1)[0])

    active = seal
    if active is None and mint_if_missing:
        active = mint_seal(repo, paths_to_hash=paths_to_hash, org_root=org_root)
    if active is None:
        return ATLDecision(
            allowed=False,
            reasons=["no oracle seal available"],
            forge_class="F4",
        )

    fresh_ok, fresh_msg = verify_seal_against_repo(active, repo)
    if not fresh_ok:
        # Stale/tampered provided seal: remint only when explicitly allowed.
        # Forge F4 tests pass mint_if_missing=False with a planted stale seal.
        if mint_if_missing:
            active = mint_seal(repo, paths_to_hash=paths_to_hash, org_root=org_root)
            fresh_ok, fresh_msg = verify_seal_against_repo(active, repo)
        if not fresh_ok:
            return ATLDecision(
                allowed=False,
                reasons=[fresh_msg],
                forge_class="F4",
            )

    passed = set(active.passed_nodeids)
    orphan: list[str] = []
    hollow: list[str] = []
    missing_pass: list[str] = []

    for crit in criteria:
        linked = linkage.get(crit.id) or []
        if not linked:
            orphan.append(crit.id)
            continue
        for nodeid in linked:
            if nodeid not in passed and not _nodeid_soft_match(nodeid, passed):
                missing_pass.append(f"{crit.id}->{nodeid}")
                continue
            if not test_source_covers_criterion(repo, nodeid, crit.id):
                hollow.append(f"{crit.id}->{nodeid}")

    if orphan:
        return ATLDecision(
            allowed=False,
            reasons=[f"orphan criteria (no linkage): {', '.join(orphan)}"],
            forge_class="F3",
        )
    if missing_pass:
        return ATLDecision(
            allowed=False,
            reasons=[f"linked tests not in passing seal: {', '.join(missing_pass)}"],
            forge_class="F2",
        )
    if hollow:
        return ATLDecision(
            allowed=False,
            reasons=[
                "hollow tests: linked tests do not mention criterion IDs "
                f"or ATL_COVERS: {', '.join(hollow)}"
            ],
            forge_class="F2",
        )

    trace = build_acceptance_trace(
        workflow_id=workflow_id,
        criteria=criteria,
        linkage=linkage,
        seal=active,
        writes_count=writes_count,
        gate_digests=gate_digests,
    )
    # Persist for audit
    feature_artifacts.mkdir(parents=True, exist_ok=True)
    (feature_artifacts / "oracle_seal.json").write_text(
        __import__("json").dumps(active.to_dict(), indent=2),
        encoding="utf-8",
    )
    trace.save(feature_artifacts / TRACE_FILENAME)

    return ATLDecision(allowed=True, reasons=["acceptance trace verified"], trace=trace)


def _nodeid_soft_match(wanted: str, passed: set[str]) -> bool:
    """Allow path-normalized or suffix match for Windows path quirks."""
    w = wanted.replace("\\", "/")
    if w in passed:
        return True
    for p in passed:
        if p.replace("\\", "/") == w:
            return True
        if p.endswith(w) or w.endswith(p):
            return True
    return False
