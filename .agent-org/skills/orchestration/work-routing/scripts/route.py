"""Route ready stories to personas by capability, WIP, and components."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_capability_routing"


def run(
    stories: Any = None,
    personas: Any = None,
    assignments: Any = None,
    wip_limit: int = 2,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, parse_stories

    findings = FindingList()
    parsed = parse_stories(stories)
    roster = list(personas or [])
    if not parsed:
        findings.error("no_stories", "no ready stories to route")
        return build_result(findings, _EVIDENCE, routes=[], unroutable=[])
    if not roster:
        findings.error("no_personas", "persona registry empty")
        return build_result(findings, _EVIDENCE, routes=[], unroutable=[])

    # Normalize personas: {id, capabilities: [...]}
    caps: list[dict[str, Any]] = []
    for raw in roster:
        if not isinstance(raw, dict):
            continue
        pid = str(raw.get("id") or raw.get("persona") or "").strip()
        capabilities = [
            str(c).strip().lower()
            for c in (raw.get("capabilities") or raw.get("skills") or [])
            if str(c).strip()
        ]
        if pid:
            caps.append({"id": pid, "capabilities": capabilities})

    load: dict[str, int] = {}
    for item in assignments or []:
        if isinstance(item, dict):
            who = str(item.get("persona") or "").strip()
            if who:
                load[who] = load.get(who, 0) + 1

    routes: list[dict[str, str]] = []
    unroutable: list[dict[str, str]] = []

    for story in parsed:
        subject = story.id or story.title or "<story>"
        needed = [c.lower() for c in story.components] or ["implementation"]
        candidates = []
        for persona in caps:
            if load.get(persona["id"], 0) >= wip_limit:
                continue
            have = set(persona["capabilities"])
            if have and not any(n in have or n.split("-")[0] in have for n in needed):
                # also match backend/frontend keywords in components
                if not any(
                    any(token in cap for token in needed)
                    for cap in have
                ):
                    continue
            candidates.append(persona)
        if not candidates:
            # fallback: any under WIP with empty capabilities means generalist
            candidates = [
                p for p in caps
                if load.get(p["id"], 0) < wip_limit and not p["capabilities"]
            ]
        if not candidates:
            reason = "no_persona_with_capability_or_wip"
            unroutable.append({"id": subject, "reason": reason})
            findings.error("unroutable", reason, subject)
            continue
        # Prefer lowest WIP, then id for stability
        chosen = sorted(
            candidates,
            key=lambda p: (load.get(p["id"], 0), p["id"]),
        )[0]
        routes.append({"story": subject, "persona": chosen["id"]})
        load[chosen["id"]] = load.get(chosen["id"], 0) + 1

    return build_result(
        findings,
        _EVIDENCE,
        routes=routes,
        unroutable=unroutable,
        routed_count=len(routes),
        load=load,
    )
