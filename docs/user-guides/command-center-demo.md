# Command-Center Demonstration (Output 10)

Start the server:

```powershell
agentctl serve   # http://127.0.0.1:8787
```

The console is a live operations surface, not a report. It holds an open
server-sent-events stream (`/api/stream`) and repaints when platform state
changes; the header shows `LINK LIVE` while the stream is connected and
`LINK POLLING` if it falls back to fetching `/api/state`.

## Layout

| Region | Shows |
| ------ | ----- |
| Header | Stream health, hash-chain verification, model provider status, active missions, clock |
| Features rail | Every registered feature with its latest workflow state and run count |
| Workflows rail | Every run: id, state, spend to date, last update; a pulsing marker means executing |
| Mission Pipeline | The six graph nodes as hexagons, each labelled with its owning agent role and status, with the human gate marked between DECISION and PLAN |
| Action console | Launch Run, Approve Gate, Reject, Resume, Revert Checkpoint |
| Artifact Inspector | Charter, plan, feature brain, and repo map read from disk |
| Budget Telemetry | Radial budget gauge plus meters for cost, iterations, tool calls, tokens, and expensive-model calls against their caps |
| Agent Fleet | Per-agent runs with status, timing, tokens, and cost |
| Checkpoints | Restorable git checkpoints for the selected workflow |
| Live Event Stream | Newest events, filterable by FLOW / AGENTS / GATES / RISK; click any row to expand its payload and hash |

Pipeline status is derived, not asserted: each node is marked `done`,
`active`, `awaiting`, `blocked`, or `pending` by replaying that workflow's
recorded event types. A run that stopped for a missing model key shows
`CHARTER / BLOCKED` with the recorded reason, and the two downstream nodes stay
`PENDING`.

## Required questions

| Question | Console | CLI |
| -------- | ------- | --- |
| What are my agents doing? | Mission Pipeline plus Agent Fleet | `agentctl status` |
| Why / what evidence? | Live Event Stream, expandable to payload and hash | `agentctl audit --workflow <id>` |
| What needs approval? | Amber gate banner and enabled Approve/Reject | `agentctl approve/reject <id>` |
| How much has been spent? | Budget Telemetry (workflow and portfolio) | `agentctl budget <id>` |
| What can be reverted? | Checkpoints panel, Revert Checkpoint action | `agentctl revert <repo> <ckpt>` |
| Is history trustworthy? | `AUDIT CHAIN VERIFIED` header chip | `agentctl verify` |
| Feature brain | Artifact Inspector, git-versioned under `projects/<p>/features/<f>/` | `agentctl inspect <id>` |

## Acting from the console

Approving a gate records the decision with identity and reason, then resumes
the LangGraph thread past the gate into planning; the pipeline repaints as the
run progresses. Every operator action also appends a `command.issued` event, so
human interventions sit in the same audit chain as agent work.

Launch and Approve start autonomous work and bill model calls, so both require
a confirmation that names the budget cap. Revert confirms separately and states
that reverted work is preserved as git tags. Buttons are enabled only for
transitions the state machine permits: Approve and Reject only at an open gate,
Resume only after a gate has been passed.

Experiment history, sprint boards, and the graph explorer are Phase 3-5 panels;
their data contracts (experiment schema, event types) already exist.
