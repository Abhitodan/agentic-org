---
name: dependency-doctor
description: Deterministic manifest autopsy — unpinned dependencies, stdlib shadowing, duplicates — across requirements files and pyproject.toml. No network, no registry lookups.
category: discovery
personas:
  - repository-agent
  - security-agent
triggers:
  - dependency-doctor
  - map-repository
network: none
entrypoint: scripts/doctor.py:run
tools: []
---

# Dependency Doctor

> Most dependency incidents are visible in the manifest long before they
> hit production: an unpinned transitive, a package shadowing the stdlib,
> the same dep declared twice with different pins. This skill reads only
> the manifests and reports what is provable from them.

## Guardrails

1. **Real parsers, not regex guessing.** `pyproject.toml` is parsed with
   stdlib `tomllib`; requirements files line-by-line with PEP 508-aware
   extraction. An unparsable manifest is a `manifest_unreadable` warning,
   never a crash and never a silent skip.
2. **Declared intent only.** Reads requirements/pyproject — not lockfiles,
   not the network, not a registry. Findings are provable from the files.
3. **Stable taxonomy.** Finding codes are API: downstream planning depends
   on them not drifting.
4. **Errors block, warnings inform.** `ok: false` only when errors exist.

## When to use

- Before planning dependency upgrades or additions
- During repository intake/audit alongside `repository-analysis`
- CI-style hygiene checks on manifests

## When NOT to use

- To check for known CVEs or latest versions — that requires network and
  belongs to a future `network: declared` skill with its own human gate
- On lockfiles — this reads declared intent, not resolved graphs

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `repo_path` | path | yes | missing → `ok: false` with reason |

Scans: `requirements.txt`, `requirements-dev.txt`, `requirements.in`,
`pyproject.toml` (`[project]` dependencies + optional-dependencies, and
Poetry-style tables).

## Findings taxonomy

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `stdlib_shadow` | error | name collides with stdlib/core tooling — classic typo-squat/confusion vector |
| `unpinned` | warn | no version constraint — irreproducible builds |
| `duplicate` | warn | same package declared twice (cross-manifest too) — pin conflict risk |
| `manifest_unreadable` | warn | pyproject failed to parse; findings incomplete |

## Output contract

```json
{
  "ok": false,
  "findings": [
    {"severity": "error", "code": "stdlib_shadow", "package": "os",
     "file": "requirements.txt", "line": 2, "detail": "…"}
  ],
  "manifests_scanned": ["requirements.txt", "pyproject.toml"],
  "error_count": 1,
  "warn_count": 2,
  "evidence": "deterministic_manifest_scan"
}
```

`line` is null for pyproject findings (TOML parsing is structural, not
line-oriented).

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| `repo_path` missing | `ok: false` with reason, empty findings |
| No manifests found | `ok: true`, `manifests_scanned: []` — honest empty |
| Broken TOML | `manifest_unreadable` warning; other manifests still scanned |

## Anti-patterns

- WRONG: "pin everything to exact versions" as a blanket fix for `unpinned`
  in a library project.
  CORRECT: libraries use compatible ranges; apps pin. The finding says
  "decide deliberately", not "==".
- WRONG: ignoring `stdlib_shadow` because "it installs fine".
  CORRECT: it is an error; the name collision will bite import resolution
  or a future reader.

## Quality checklist

- [ ] Every finding cites file (and line where line-oriented)
- [ ] Duplicate detection ran across all scanned manifests
- [ ] No finding claims anything requiring network knowledge
- [ ] `ok` consistent with `error_count`
