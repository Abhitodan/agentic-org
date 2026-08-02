# Demo walkthrough: bulk member import

This is the same use case shown in the README screenshots / GIF.

## What you are proving

1. The product maps a real sample repo.
2. It builds feature memory (brain / charter artifacts).
3. It **stops at a human gate** instead of silently continuing.
4. Guardrails show budget remaining (`$0 / $8` on a fresh run).
5. The audit chain verifies (`agentctl verify`).

## Steps

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\create_sample_repo.py

agentctl init
agentctl create-project enrollment-platform --repo .\examples\enrollment-sample
agentctl create-feature enrollment-platform bulk-member-import --objective "Add bulk member import"
agentctl run enrollment-platform bulk-member-import --budget-usd 8
```

Expected (offline / no key or fail-closed model path): workflow reaches a decision/blocked state with real artifacts — **not** a fabricated “plan complete”.

```powershell
agentctl status
agentctl verify
agentctl serve
```

Open `http://127.0.0.1:8787` and inspect:

| Panel | Look for |
| ----- | -------- |
| Pipeline | Intake → Repo Map → Brain → Charter → **Decision (human gate)** |
| Agent theater | Banner: human decision required |
| Documents | Charter / Repo map tabs |
| Guardrails | Cost vs `$8` budget, pending `plan-approval` |
| Checkpoints | `workflow-start` (revertible) |

Approve when ready:

```powershell
agentctl approve <workflow_id>
```

## Screenshots in this repo

- `docs/assets/screenshots/01-human-gate-overview.png`
- `docs/assets/screenshots/02-repo-map.png`
- `docs/assets/screenshots/03-gates-guardrails.png`
- `docs/assets/screenshots/demo-command-center.gif`
