# Rules

Always-on standards for humans and agents working in this organization.
Layered like CSS specificity: `common/` applies everywhere; stack overlays
(e.g. `python/`) extend and override common where they conflict.

```text
rules/
  common/          # language-agnostic, always installed
    coding-style.md
    testing.md
    security.md
    review.md
    git-workflow.md
  python/          # extends common with Python-specific content
    coding-style.md
    testing.md
```

## Rules vs skills

- **Rules** say *what* the standard is (short, enforceable, always loaded).
- **Skills** (`.agent-org/skills/`) say *how* — deep workflows, scripts,
  references loaded on demand.

When a rule needs more than a page of explanation, it belongs in a skill and
the rule should point to it.

## Priority

1. Human decisions recorded in feature brains / ADRs
2. `constitution.md` and `policies/`
3. Stack overlay rules (`python/…`)
4. Common rules (`common/…`)

Overlay rules may relax a common rule only when the language idiom demands it
and the file says so explicitly.
