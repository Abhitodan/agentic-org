# delivery — specified, not yet built

Skills that gate shipping. These directories contain no scripts on purpose;
a release gate that always passes is worse than no gate.

## Planned skills

### `release-readiness`

Aggregate the evidence a release requires: every included story
demonstrated and evidenced, no unresolved error findings from review, a
rollback plan present, and the release approval gate recorded.

- Inputs: included stories, review results, test evidence, approval record
- Gate: any missing evidence blocks; "probably fine" is not a state
- Evidence: `deterministic_release_evidence`

### `changelog-forge`

Build a changelog from delivered stories and their acceptance criteria, not
from commit subjects. Every entry traces to a story id; unattributed
commits are reported rather than silently omitted.

- Inputs: delivered stories, commit range
- Gate: commits with no story attribution are listed as gaps
- Evidence: `deterministic_changelog_traceability`

### `rollback-plan`

Verify a rollback plan is executable: it names the artifact version to
revert to, the data migrations that are irreversible, and the verification
step that confirms the rollback worked.

- Inputs: release plan, migration list
- Gate: an irreversible migration without a documented forward-fix blocks
- Evidence: `deterministic_rollback_completeness`

### `deployment-verification`

Confirm post-deployment checks actually ran and passed, with the output
hashed the same way `test-evidence` hashes test runs. A deployment reported
as successful without verification output is an error.

- Inputs: declared verification commands, deployment record
- Gate: missing or failing verification blocks the release from being closed
- Evidence: `deterministic_deployment_checks`

## Build order

`release-readiness` first — it composes evidence the other categories
already produce. `deployment-verification` next, reusing the command-runner
and hashing already built for `test-evidence`.
