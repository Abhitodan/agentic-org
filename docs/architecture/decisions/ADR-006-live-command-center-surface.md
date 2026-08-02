# ADR-006: Live Command-Center Surface

- Status: Accepted
- Date: 2026-07-31

## Context

The first command center was a polling dashboard: it re-fetched a handful of
endpoints every five seconds and rendered read-only tables. Two problems made
it unfit as an operations surface.

1. **No situational awareness.** An operator could see that a workflow was
   `BLOCKED` but not *where* in the pipeline it stopped, which agent owned that
   stage, or how much budget the run had consumed against its cap. Reconstructing
   that required reading the CLI audit log.
2. **Observation without control.** Every corrective action (launch, approve,
   resume, revert) had to be typed into a terminal, so the human gate the
   constitution mandates lived outside the surface that showed the evidence.

## Decision

The command center becomes a live operations console with three properties.

**Push, not poll.** `GET /api/stream` is a server-sent-events endpoint that
emits an aggregated snapshot only when the projected state actually changes.
The snapshot is built on a worker thread (`asyncio.to_thread`) so the event
loop is never blocked by SQLite reads. `GET /api/state` serves the same
projection for a one-shot fetch, and the browser falls back to polling it if
the stream cannot be established.

**One projection, many panels.** A single snapshot carries system health,
features, workflows, per-workflow budget/spend, agent runs, checkpoints, and
the newest events. Crucially it also carries a *derived pipeline projection*:
for each workflow, the six graph nodes are labelled `done`, `active`,
`awaiting`, `blocked`, or `pending` by replaying that workflow's event types.
The UI renders orchestration progress from recorded evidence rather than from a
status string the runner asserts.

**Act where you observe.** The console exposes launch, approve, reject, resume,
and revert. Long-running actions (launch, resume) execute on worker threads
that build their own `Context`, because a SQLite connection cannot cross
threads; progress becomes visible through the event store like any other agent
work. Every action appends a `command.issued` event carrying the actor, so
human interventions are auditable alongside agent decisions.

## Guardrails

- **Spending requires confirmation.** Launch and approve start autonomous work
  and bill model calls, so both require an explicit confirmation that names the
  budget cap. An earlier iteration bound these to single-key shortcuts; browser
  testing fired a real run from a stray keypress, so unconfirmed spend paths
  were removed entirely.
- **Buttons follow the state machine.** Approve and reject are enabled only at
  an open gate; resume only when a gate has been passed. The UI cannot invite a
  transition the state machine would reject.
- **No fabricated data.** Panels with no backing data render an explicit empty
  state, and the artifact inspector reports `ARTIFACT NOT PRODUCED YET` rather
  than placeholder content. Blocked workflows surface the recorded reason.
- **Assets are served `no-store`.** A stale console after an upgrade would
  misrepresent live system state.

## Consequences

- The CLI and the console remain equal citizens over the same services and
  SQLite state; neither owns behaviour the other lacks.
- Hash-chain verification is cached for ten seconds because the stream would
  otherwise re-verify the whole chain every tick.
- Reverting through the console resets a working tree, which is why it is the
  one action that both confirms and explains that history is preserved as git
  tags.
