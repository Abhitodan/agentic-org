# Operations runbook (local Mode A)

## Start command center

```powershell
cd c:\Abhitodan\AITeams\agentic-org
.\.venv\Scripts\python.exe -m agentic_org.cli.main serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`. Non-loopback binds require `AGENTIC_ORG_API_TOKEN`.

## Backup

Stop the server first. Copy:

| Path | Contents |
| ---- | -------- |
| `.agent-org/state/agentic.db` | Events, workflows, jobs, approvals |
| `.agent-org/state/langgraph.db` | Graph checkpoints |
| `.agent-org/state/graph.db` | Graph memory projection |
| `.agent-org/state/vectors.db` | Sparse vectors |
| `projects/` | Product topology, brains, feature docs |
| `.env` | Secrets (store separately; never commit) |

Example:

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = ".\backups\backup-$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse .\.agent-org\state $dest\state
Copy-Item -Recurse .\projects $dest\projects
```

## Restore

1. Stop `serve`.
2. Replace `.agent-org/state` and `projects` from the backup.
3. Start `serve` again.
4. Verify: `agentctl verify` (event chain) and open the command center.

## Backup/restore drill checklist

- [ ] Create a throwaway feature run (or use sample project)
- [ ] Backup state + projects
- [ ] Confirm `agentic.db` size > 0 in backup
- [ ] Restore into a copy of the org root (or after intentional rename of state)
- [ ] `agentctl verify` → chain valid
- [ ] UI shows prior workflows/events

## Multi-component products

1. `agentctl product-init <name> --shape multi`
2. `agentctl product-set-component <name> --id sql --path <repo> --kind sql --order 10`
3. Add backend/frontend similarly
4. Suggestions rail shows order; **never auto-approves**
5. After plan, edit `artifacts/work_packages.json` / per-package actions if needed
6. Human plan + release gates remain mandatory

## Quality / evals

```powershell
.\.venv\Scripts\python.exe evals\run_plumbing.py
.\.venv\Scripts\python.exe evals\run_adversarial.py
.\.venv\Scripts\python.exe evals\run_quality.py
```

Live LLM: set `AGENTIC_ORG_LIVE_LLM=1` + key; skip ≠ pass.
