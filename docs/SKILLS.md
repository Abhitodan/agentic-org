# Skills — install and use

Skills are executable packages under `.agent-org/skills/<category>/<name>/` (or project override `.agents/skills/`). Each has `SKILL.md`, `scripts/`, and optional `references/`.

The nine categories follow the delivery lifecycle: `discovery`, `product`, `planning`, `implementation`, `verification`, `review`, `delivery`, `ceremonies`, `orchestration`. See `docs/SKILL_CATALOG.md` for the full index of what ships today and what is specified next.

Skill names are globally unique regardless of category — categories group and route, they do not namespace. A flat `<name>/SKILL.md` layout still loads, for backward compatibility.

Always-on standards live separately in `.agent-org/rules/` (common + stack overlays): rules say *what* the standard is; skills say *how* with scripts and deep references.

## Humans (`agentctl`)

```bash
agentctl skill-list --grouped                    # whole catalog by category
agentctl skill-list --category ceremonies        # one category
agentctl skill-list --persona product-owner-agent
agentctl skill-show sprint-planning
agentctl skill-run repository-analysis --repo path/to/repo --out .agent-org/state/maps
agentctl skill-eval retrospective
agentctl map-repository --repo path/to/repo      # invokes repository-analysis

# Install the same skills into a coding agent (symlink, or --copy on Windows)
agentctl skill-install cursor --dry-run
agentctl skill-install claude
agentctl skill-install codex --copy
agentctl skill-install project                   # -> .agents/skills
```

Mode A nodes call skills: `map_repository` → repository-analysis, `plan` → feature-planning, `implement` → implementation, `review` → code-review. Invocations emit `skill.started` / `skill.finished` / `skill.failed` events.

## Agile skills return a shared envelope

Skills in `product/`, `planning/`, and `ceremonies/` all return the same shape, so an orchestrator can consume any of them without special-casing:

```json
{"ok": false, "findings": [{"severity": "error", "code": "no_owner",
  "subject": "action-2", "field": "owner", "detail": "…"}],
 "error_count": 1, "warn_count": 2, "info_count": 0, "evidence": "…"}
```

`ok` is false only when an error-severity finding exists. They share parsing and arithmetic from `src/agentic_org/agile/` rather than each reimplementing story handling.

## Coding agents (Cursor / Claude / Codex)

Use `agentctl skill-install` so every consumer sees the **same** scripts and `SKILL.md` files — do not hand-copy bodies into chat.

| Target | Default destination |
| ------ | ------------------- |
| `cursor` | `~/.cursor/skills/agentic-org` |
| `claude` | `~/.claude/skills/agentic-org` |
| `codex` | `~/.codex/skills/agentic-org` |
| `project` | `<org>/.agents/skills` |

Verify after install:

1. Destination contains categorized folders (`discovery/`, `product/`, …) with `SKILL.md` + `scripts/`.
2. `agentctl skill-list` still resolves the org tree (install is a projection, not a fork).
3. Respect `network: none|declared` — never silently add network.
4. Prefer `agentctl skill-run` / Mode A over re-implementing scripts in chat.

Package-bundled fallbacks live in `src/agentic_org/skills/bundled/` for fresh installs and tests.

## Adding a skill

1. Create `.agent-org/skills/<category>/<name>/` with frontmatter (`name`, `description`, `category`, `personas`, `triggers`, `network`, `entrypoint`).
2. Add `scripts/<entry>.py` with a `run(...) -> dict` matching the declared entrypoint.
3. Add `references/` for deep material loaded on demand.
4. Register an eval in `src/agentic_org/cli/skill_evals.py`. This is mandatory: `tests/test_skill_eval_registry.py` fails the build for any skill without one.
5. Bind the skill to the personas that use it in `.agent-org/agents/`.
6. Re-mirror the package bundle so fresh installs and tests get it:
   `robocopy .agent-org\skills src\agentic_org\skills\bundled /E /XD __pycache__`

Bootstrap seeds the tree; it never reverts authored work. A skill directory that already has a script, and an agent card that already declares `skills:` in frontmatter, are both left untouched (covered by `tests/test_bootstrap_preserves_authored_work.py`).
