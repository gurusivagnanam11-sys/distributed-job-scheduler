# Design Decisions

This document records the implementation choices that were made where the brief left room for interpretation. The goal is to be explicit about what the system does and why.

## Summary

| Decision | What we chose |
|---|---|
| Priority | Per job, ordered in the claim query by `priority DESC, scheduled_at ASC`. |
| Delayed vs scheduled | One mechanism: both use future `scheduled_at` values. |
| Dedupe | Per queue, non-terminal duplicates return the existing row, terminal rows can be reused. |
| Idempotency | At-least-once execution with full attempt history in `JobExecution`. |
| Locking | Queue-row `FOR UPDATE` plus job-row `FOR UPDATE SKIP LOCKED`. |
| API keys | Project-scoped `X-API-Key` auth for submission clients. |

## Priority is per job, not per queue

Priority lives on `Job`, not `Queue`. A single per-queue priority would not create meaningful scheduling choice, because every job in that queue would inherit the same value.

The claim query uses `ORDER BY priority DESC, scheduled_at ASC`, so urgent jobs can jump ahead of routine work within the same queue while still respecting scheduled time.

## Delayed and scheduled jobs use the same mechanism

“Delayed” and “scheduled” jobs are the same behavior in the database: both set a future `scheduled_at`.

Once that timestamp passes, the normal claim query picks the job up. The distinction is terminology in the brief, not a separate execution path.

## Dedupe key semantics

`dedupe_key` is scoped per queue.

If a duplicate key is submitted while the existing job is still non-terminal, the API returns the existing job with `200 OK` instead of creating a second row. Once that job reaches a terminal state (`completed`, `failed`, or `dead_letter`), the same key can be reused for a fresh submission.

That prevents duplicate in-flight work without making the key permanently one-time-only. The implementation is race-safe as well: concurrent submissions are handled by catching the unique-constraint violation and returning the existing row, not by relying on a check-then-insert sequence.

The code matches that rule: it checks for an existing non-terminal job first, then catches the queue-level dedupe unique-constraint violation and resolves the race by returning the already-created row.

## Idempotency contract

The system guarantees at-least-once execution and records every attempt in `JobExecution` rows.

It does not suppress side effects automatically if a worker dies mid-job. In that case the reaper can reclaim the job and it will run again as a new, logged attempt. True exactly-once behavior is the handler’s responsibility, usually by making side effects idempotent and keyed on `job_id`.

### Why not exactly-once?

Exactly-once side effects would require the handler and its downstream systems to coordinate durable deduplication. This scheduler does not try to own that problem. It owns execution tracking, retries, and recovery; handlers own their own idempotent writes.

## Row-locking design for claim and reaper

`claim.py` uses two levels of locking on purpose. A queue-row `FOR UPDATE` lock serializes concurrent claim attempts for the same queue, so `available_slots` is computed against committed state only. Inside that transaction, job rows are selected with `FOR UPDATE SKIP LOCKED`, which keeps workers from blocking each other on individual jobs.

That trade-off serializes claim throughput per queue, but it preserves correctness and keeps the logic simple. It is an acceptable scope choice here, and the system scales horizontally by adding more queues instead of pushing more parallel claim throughput into a single queue.

The reaper uses the same `SKIP LOCKED` pattern independently so two reaper loops cannot double-reclaim the same stale job.

## API-key authentication design

There are two auth paths with different intended audiences.

JWT is for the dashboard and human users. API keys are for external job-submission clients and are sent in the `X-API-Key` header.

API keys are project-scoped, not org-scoped. That is stricter than JWT auth: a key issued for Project A cannot submit into a queue owned by Project B, even if both projects belong to the same organization.

Job-submission endpoints accept either JWT or API key. All other endpoints remain JWT-only.

## Known scope trade-offs

- Frontend auth/session state is in memory only, so a hard refresh requires re-login. That is fine for this assessment; a production version would persist session state.
- The frontend API base URL is hardcoded to `http://localhost:8000` for local development. A deployed build would read this from configuration.
- Worker execution concurrency uses a fixed per-worker semaphore (`MAX_CONCURRENT_EXECUTIONS = 10`) rather than dynamically matching each queue’s `concurrency_limit`. Queue limits are still enforced correctly at claim time; this only controls how many jobs a single worker runs in parallel.

## Other simplification

The job timeline endpoint is derived from `JobLog` rows and timestamp data, with event types inferred from the logged messages.

That keeps the audit trail compact and avoids adding a separate event table for this assessment.
