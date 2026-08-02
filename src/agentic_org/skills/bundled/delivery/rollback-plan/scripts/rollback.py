"""Validate a rollback plan is executable and honest about irreversibility."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_rollback_completeness"


def run(
    plan: Any = None,
    migrations: Any = None,
    human_approval_for_data_loss: bool = False,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    data = plan if isinstance(plan, dict) else {}
    if not data:
        findings.error("no_plan", "rollback plan dict required")
        return build_result(findings, _EVIDENCE)

    revert_to = str(data.get("revert_to") or data.get("artifact_version") or "").strip()
    if not revert_to:
        findings.error(
            "no_revert_target",
            "plan must name the artifact version to revert to",
            field_name="revert_to",
        )

    verify = str(data.get("verify") or data.get("verification") or "").strip()
    if not verify:
        findings.error(
            "no_verify_step",
            "plan must name a verification step after rollback",
            field_name="verify",
        )

    migs = list(migrations or data.get("migrations") or [])
    irreversible: list[str] = []
    for index, raw in enumerate(migs, 1):
        if isinstance(raw, dict):
            name = str(raw.get("name") or raw.get("id") or f"migration-{index}")
            rev = raw.get("reversible")
            forward_fix = str(raw.get("forward_fix") or "").strip()
            data_loss = bool(raw.get("data_loss"))
        else:
            name, rev, forward_fix, data_loss = str(raw), None, "", False
        if rev is False:
            irreversible.append(name)
            if not forward_fix:
                findings.error(
                    "irreversible_without_forward_fix",
                    f"{name}: irreversible migration needs a documented forward-fix",
                    name,
                )
            if data_loss and not human_approval_for_data_loss:
                findings.error(
                    "data_loss_unapproved",
                    f"{name}: data-loss migration requires human_approval_for_data_loss",
                    name,
                )

    owner = str(data.get("owner") or "").strip()
    if not owner:
        findings.warn("no_owner", "rollback plan has no named owner")

    return build_result(
        findings,
        _EVIDENCE,
        revert_to=revert_to or None,
        verify=verify or None,
        irreversible_migrations=irreversible,
        migration_count=len(migs),
    )
