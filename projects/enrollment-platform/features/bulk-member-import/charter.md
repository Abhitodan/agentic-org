# Feature Charter: Bulk Member Import

## Problem
Current member enrollment processes are manual and inefficient for large datasets,
leading to significant administrative overhead and potential for human error when
onboarding new members. There is no existing mechanism to efficiently process
large volumes of member data.

## Users
- **Administrators:** Manage member data, onboard new groups, ensure data accuracy.
- **Operations reviewers:** Inspect failed rows and approve retries.

## Outcome
Import a 10,000-row member CSV in under 5 minutes wall clock with per-row error
reporting and an auditable batch receipt.

## Scope
- CSV upload and schema validation
- Progress tracking for long-running imports
- Partial failure handling with retry of failed rows
- Audit history of import batches

## Exclusions
- Real-time streaming ingest from third-party HRIS
- Member UI redesign
- Payment or billing changes

## Acceptance criteria
- Invalid rows are rejected with line numbers and reason codes
- Successful rows commit even when siblings fail (partial success)
- Retry endpoint reprocesses only failed rows for a batch
- Audit event written for start, complete, and retry
- Existing `tests/test_importer.py` stays green; new coverage for validation/retry

## Risks
- PII leakage in import logs
- Partial batch leaving members in inconsistent group membership
- Large files exhausting memory if loaded wholly into RAM

## Architecture options
### Option A: Sync in-request import
Simple path; blocks HTTP until done. Poor for 10k+ rows.

### Option B: Background worker queue
Upload stores file; worker validates and imports asynchronously with progress.

### Option C: Hybrid (selected)
Sync validate first 200 rows for fast feedback; remainder processed by worker
with progress and audit events.
