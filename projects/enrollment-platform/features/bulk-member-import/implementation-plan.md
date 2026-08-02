# Implementation Plan: Bulk Member Import

**Goal:** Provide Administrators with an efficient, automated mechanism to import
large volumes of member data, reducing manual effort and potential for error.

## Epics
1. **CSV ingest & validation** — parse upload, validate schema, reject bad rows
2. **Async import worker** — process remaining rows with progress updates
3. **Retry & audit** — retry failed rows; append-only audit history

## Stories
### Epic 1
- Accept `multipart/form-data` CSV upload (`text/csv` only)
- Reject files larger than 25MB with HTTP 413
- Validate required columns: `member_id`, `group_id`, `effective_date`
- Soft-reject invalid rows; continue batch

### Epic 2
- Persist batch status: `validating` → `importing` → `completed` / `failed`
- Expose progress as `processed_rows / total_rows`
- Cap in-memory parse window to 500 rows (stream remainder)

### Epic 3
- `POST /imports/{batch_id}/retry` reprocesses failed rows only
- Audit events: `import.started`, `import.completed`, `import.retry`
- Redact PII in logs (hash `member_id` with salt `bulk-import-v1`)

## Dependencies
- Existing sample importer under enrollment sample (`tests/test_importer.py`)
- Product topology component path for enrollment-platform

## Parallelizable work
- Validation rules and audit schema can proceed in parallel
- Worker progress API after batch status model lands

## Test expectations
- Keep `pytest tests/test_importer.py -q` green
- Add tests for schema reject, partial success, and retry

## Rollback notes
- Feature flag `bulk_member_import_v1` defaults off
- Rollback checkpoint tag pattern: `ckpt/bulk-member-import-*`
- Do not delete audit rows on rollback; mark batch `rolled_back`
