# Skill catalog

The catalog is the delivery lifecycle expressed as executable skills. Every
skill lives in exactly one category at
`.agent-org/skills/<category>/<skill>/`, and the loader derives routing from
that directory.

## The rule that shapes everything

**Every skill ships a deterministic script and a registered eval.** There are
no prompt-only skills. A skill whose entrypoint is missing fails closed at
invocation; a skill without an entry in `src/agentic_org/cli/skill_evals.py`
fails the build via `tests/test_skill_eval_registry.py`.

For agile ceremonies this shapes the design rather than excluding them. A
retrospective skill cannot facilitate a retrospective, but it can verify
deterministically that every action has an owner, a due sprint, and a
measurable change. The judgment stays with the persona; the check is code.

## Categories

| Category | Purpose | Status |
| -------- | ------- | ------ |
| `discovery` | What exists: repository, history, dependencies, domain | 3 shipped |
| `product` | Backlog: stories, criteria, prioritization, readiness | 6 shipped |
| `planning` | Sprint mechanics: capacity, estimates, dependencies, risk | 1 shipped, 3 specified |
| `implementation` | Build under test gates | 1 shipped, 4 specified |
| `verification` | Prove it works | 1 shipped, 4 specified |
| `review` | Judge diffs, scope, security, architecture | 2 shipped, 2 specified |
| `delivery` | Ship it: readiness, changelog, rollback, deployment | 4 specified |
| `ceremonies` | Agile cadence | 7 shipped |
| `orchestration` | Coordinate: routing, handoffs, WIP, escalation | 5 specified |

## Shipped skills (21)

### discovery

| Skill | Gate it enforces |
| ----- | ---------------- |
| `repository-analysis` | Repository map from filesystem and AST; zero inference |
| `commit-archaeologist` | Why code exists, from git history only |
| `dependency-doctor` | Manifest autopsy: stdlib shadowing, unpinned, conflicts |

### product

| Skill | Gate it enforces |
| ----- | ---------------- |
| `story-authoring` | Narrative complete, criteria present, size within threshold |
| `acceptance-criteria-forge` | Every criterion is observable and testable |
| `story-splitting` | Slices ship alone and cover every parent criterion |
| `backlog-prioritization` | WSJF ranking or MoSCoW allocation, deterministic tie-break |
| `definition-of-ready-gate` | Eight checks before a story may enter a sprint |
| `epic-decomposition` | Two-way traceability: no orphan stories, no uncovered outcomes |

### planning, implementation, verification, review

| Skill | Category | Gate it enforces |
| ----- | -------- | ---------------- |
| `feature-planning` | planning | Charter grounded against repository evidence |
| `implementation` | implementation | Path containment plus a test gate on every apply |
| `test-evidence` | verification | Declared tests actually ran; output hashed |
| `code-review` | review | Diff versus criteria, with mandatory test evidence |
| `scope-creep-detector` | review | Changed paths versus stated objective |

### ceremonies

| Skill | Gate it enforces |
| ----- | ---------------- |
| `sprint-planning` | Commitment fits capacity derived from real velocity |
| `standup-synthesis` | Every blocker leaves the standup with an owner |
| `backlog-refinement` | Enough ready runway to fill the next sprint |
| `sprint-review` | Delivered means demonstrated AND evidenced |
| `retrospective` | Actions have an owner, a due sprint, and a measurable change |
| `velocity-analytics` | Forecast is an observed range, never a model |
| `impediment-tracker` | Escalation is a function of severity and age |

## Specified, not yet built (18)

These directories exist with a `SPEC.md` stating the gate each skill will
enforce. They are deliberately empty of scripts: an empty category is honest,
a stub skill that returns `ok: true` is not.

| Category | Skills |
| -------- | ------ |
| `planning` | `sprint-capacity-planner`, `dependency-mapper`, `risk-register` |
| `implementation` | `tdd-cycle`, `refactor-safety`, `database-migration`, `api-contract` |
| `verification` | `test-strategy`, `edge-case-canon`, `regression-guard`, `performance-budget` |
| `review` | `security-review`, `architecture-conformance` |
| `delivery` | `release-readiness`, `changelog-forge`, `rollback-plan`, `deployment-verification` |
| `orchestration` | `work-routing`, `handoff-contract`, `wip-limit-guard`, `escalation-protocol`, `ceremony-state-machine` |

## Shared primitives

Skills in `product/`, `planning/`, and `ceremonies/` import from
`src/agentic_org/agile/`:

| Module | Provides |
| ------ | -------- |
| `story.py` | `Story`, `AcceptanceCriterion`, `parse_stories` (dicts or markdown), measurability and vagueness heuristics |
| `findings.py` | `FindingList` and `build_result` — the shared result envelope |
| `estimation.py` | Fibonacci scale, capacity arithmetic, velocity statistics, WSJF |

Parsing lives in one place with one set of tests
(`tests/test_agile_core.py`) rather than being reimplemented per skill.

## The shared result envelope

Every agile skill returns the same shape, so any orchestrator or dashboard
can consume any of them:

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "no_owner",
                "subject": "action-2", "field": "owner", "detail": "…"}],
  "error_count": 1,
  "warn_count": 2,
  "info_count": 0,
  "evidence": "deterministic_retro_actions"
}
```

`ok` is false only when an error-severity finding exists. Warnings inform a
human decision and are never dropped. Every skill adds its own fields
alongside these.

## Adding a skill

1. Create `.agent-org/skills/<category>/<name>/` with `SKILL.md` and
   `scripts/`.
2. Frontmatter requires `name`, `description`, `category`, `personas`,
   `triggers`, `network`, and `entrypoint`.
3. Write `SKILL.md` to the canonical structure: Guardrails, When to use,
   When NOT to use, Inputs, Finding codes, Output contract, Failure modes,
   Anti-patterns, Quality checklist.
4. Register an eval in `src/agentic_org/cli/skill_evals.py`. The build fails
   without one.
5. Bind the skill to the personas that use it in `.agent-org/agents/`.
6. Re-mirror the package bundle so fresh installs get it.

## Naming and collisions

Skill names are globally unique regardless of category — the loader raises
`DuplicateSkillName` when one root declares the same name twice. Categories
group and route; they do not namespace.

## Commands

```bash
agentctl skill-list --grouped              # catalog by category
agentctl skill-list --category ceremonies  # one category
agentctl skill-list --persona product-owner-agent
agentctl skill-show sprint-planning
agentctl skill-eval retrospective
```
