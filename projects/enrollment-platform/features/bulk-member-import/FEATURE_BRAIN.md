# Feature Brain: bulk-member-import

## Objective
Add bulk member import supporting large CSV files, validation, progress tracking,
partial failure handling, retry, audit history, and defined performance requirements.

## Users and Expected Value
- Administrators: faster group onboarding with fewer manual corrections.
- Operations reviewers: clear failed-row queues and retry path.

## Scope and Exclusions
In scope: CSV upload, validation, progress, partial failure, retry, audit.
Out of scope: HRIS streaming, member UI redesign, billing changes.

## Acceptance Criteria
See `charter.md`. Key bar: 10k rows under 5 minutes with per-row errors and receipt.

## Current State
# Repository Map: C:\Users\abhit\PycharmProjects\agentic-org\examples\enrollment-sample

- Files: 7
- Tests discovered: 1
- Entry points: none detected

## Languages (files / lines)
- python: 6 files, 115 lines
- markdown: 1 files, 6 lines

## Tests
- tests/test_importer.py
- [2026-08-02T02:52:02.796+00:00] worktree task_a60aa6126a9e4827be3f: tests passed (999 ms)

## Languages (files / lines)
- python: 6 files, 115 lines
- markdown: 1 files, 6 lines

## Tests
- tests/test_importer.py

## Languages (files / lines)
- python: 6 files, 115 lines
- markdown: 1 files, 6 lines

## Tests
- tests/test_importer.py

## Repository Components
- Importer sample code + `tests/test_importer.py`
- Feature docs: charter, plan, this brain, artifacts/repo-map.md

## Requirements
- Hybrid architecture (Option C): sync validate first 200 rows; async remainder
- Max upload 25MB; required columns member_id, group_id, effective_date
- Feature flag `bulk_member_import_v1` off by default

## Assumptions
- Sample repo remains the connected component for Mode A demos
- CSV is UTF-8

## Open Questions
- Retention for uploaded CSV blobs: 7 days vs 30 days?
- Should soft-rejected rows block batch completion status?

## Decisions
- [2026-07-31] charter approved; implementation plan at implementation-plan.md
- [2026-08-02] Enriched truncated charter/plan; selected Hybrid Option C
- [2026-08-02] Log redaction salt `bulk-import-v1` for member_id
- [2026-08-02T02:50:27.303+00:00] charter approved; reused implementation plan at implementation-plan.md
- [2026-08-02T02:52:01.667+00:00] charter approved; reused implementation plan at implementation-plan.md

## Architecture Impact
Adds import batch tables/status and optional worker; no payment path changes.

## Dependencies
Connected enrollment-platform component path; pytest importer suite.

## Risks
PII in logs; partial membership inconsistency; memory blowup on full-file load.

## Experiments
Retrieval baselines: PageIndex strong on this feature; Mode A uses hybrid packer.

## Agent Sessions
- Prior Mode A workflows initialized brain (see event store for ids)
- [2026-08-02] Docs enrichment + re-index for packing
- [2026-08-02T02:48:19.861+00:00] workflow wf_8d7ea7e75bc14f9e9084: brain initialized
- [2026-08-02T02:50:00.492+00:00] workflow wf_9344dfca787d4619880c: brain initialized
- [2026-08-02T02:51:35.664+00:00] workflow wf_c14888ab671f4aba89cc: brain initialized

## Code Changes
_Not yet recorded._

## Tests
- `tests/test_importer.py` (existing)
- Planned: validation, partial success, retry

## Metrics
- Target: 10k rows / 5 minutes; track `rejected_row_rate`

## Review Findings
_Not yet recorded._

## Deployment History
_Not yet recorded._

## Incidents
_Not yet recorded._

## Lessons Learned
Truncated LLM charter/plan hurt retrieval eval; keep managed docs complete.
