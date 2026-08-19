# AGENTS.md — Shared Context for AI Coding Agents

> **This file is read by both Antigravity and Codex.** It is the single source of truth
> for scope, conventions, and current status. Duplicated verbatim at:
> `AGENTS.md`, `PROJECT_CONTEXT.md`, `docs/CONTEXT.md`.
>
> **Rule for any agent working in this repo: before starting a task, re-read the
> "Current Status" section at the bottom. After finishing a task, update it.**
> This is how Antigravity and Codex stay in sync without talking to each other directly.

---

## 1. Project

**Distributed Job Scheduler** — a production-inspired background job scheduling platform.
Built for a technical assessment (Codity.ai). Evaluated on: system architecture (20),
database design (20), backend engineering (20), reliability & concurrency (15),
frontend & UX (10), API design (5), documentation (5), testing (5).

**75% of the grade is backend/systems thinking, not UI.** Do not over-invest in frontend
polish at the expense of concurrency correctness, migrations, or tests.

## 2. Stack (do not substitute without updating this file)

- Backend: **FastAPI**, Python 3.11+
- DB: **PostgreSQL** via SQLAlchemy 2.0 (async), **Alembic** for migrations
- Auth: JWT (user-facing) + API keys (project-scoped, for job submission clients)
- Task/worker layer: custom polling worker service (NOT Celery — this is the thing being
  built, not delegated to a library)
- Frontend: **React (Vite)**
- Containerization: Docker Compose (postgres + backend + worker + frontend, one command up)
- Testing: pytest (backend), concurrency tests are the highest-priority tests in the repo

## 3. Repo layout

```
/backend
  /app
    /core          # config.py, database.py, security.py
    /models        # SQLAlchemy models — one file per entity, see §4
    /schemas       # Pydantic request/response models
    /routers       # REST endpoints, grouped by resource
    /services       # business logic (claim logic, retry calc, cron parsing)
    /worker        # worker process: claim loop, heartbeat loop, reaper loop
  /alembic
  /tests
/frontend
  /src
    /pages         # JobExplorer, JobDetail, QueueOverview, WorkerStatus
    /components
    /api           # fetch wrappers
/docs
  ARCHITECTURE.md
  ER_DIAGRAM.md (or .png)
  DESIGN_DECISIONS.md
  API.md (or link to /docs OpenAPI)
docker-compose.yml
AGENTS.md            <- this file
README.md
```

## 4. Database entities (do not rename without updating this file)

`Organization`, `User`, `Project`, `Queue`, `RetryPolicy`, `Job`, `JobExecution`,
`JobLog`, `Worker`, `WorkerHeartbeat`, `DeadLetterEntry`.

Job status enum: `queued`, `scheduled`, `claimed`, `running`, `completed`, `failed`,
`retrying`, `dead_letter`.

Job has: `priority`, `scheduled_at`, `claimed_by_worker_id`, `claimed_at`,
`lease_expires_at`, `attempt_count`, `depends_on_job_id` (nullable, for workflow deps),
`dedupe_key` (nullable, for idempotent submission), `batch_id` (nullable).

## 5. THE non-negotiable correctness rule (read before touching worker code)

The atomic claim query is the single most important piece of code in this repo. It MUST:

1. Check the queue's `concurrency_limit` against currently-running jobs **in the same
   transaction** as the claim — never as a separate prior query. Checking availability
   and claiming in two steps is a race condition that lets two workers claim into the
   same "free" slot.
2. Use `SELECT ... FOR UPDATE SKIP LOCKED` to avoid workers blocking on each other.
3. Set `lease_expires_at` on claim, so a reaper process can detect and reclaim jobs from
   dead/stuck workers.

Reference query (do not restructure the transaction boundaries — extend, don't rewrite):

```sql
BEGIN;
SELECT id FROM jobs
WHERE queue_id = :queue_id
  AND status IN ('queued', 'scheduled', 'retrying')
  AND scheduled_at <= now()
  AND (depends_on_job_id IS NULL OR EXISTS (
        SELECT 1 FROM jobs d WHERE d.id = jobs.depends_on_job_id AND d.status = 'completed'))
ORDER BY priority DESC, scheduled_at ASC
LIMIT :available_slots
FOR UPDATE SKIP LOCKED;

UPDATE jobs SET status = 'claimed', claimed_by_worker_id = :worker_id,
       claimed_at = now(), lease_expires_at = now() + interval ':lease_seconds seconds'
WHERE id = ANY(:claimed_ids);
COMMIT;
```

If you are an agent asked to implement or modify claim logic: implement exactly this
shape. If you believe a different approach is better, stop and flag it in your output —
do not silently substitute.

## 6. Idempotency mechanism (decide once, document, don't drift)

Chosen approach: **[FILL IN once decided — see Phase 4B]**. Whichever is chosen, every
agent touching execution logic must honor it consistently. Do not invent a second
idempotency mechanism elsewhere in the codebase.

## 7. Conventions

- REST: plural nouns, standard status codes, pagination via `?page=&page_size=`,
  filtering via query params, structured JSON error bodies `{"error": {"code", "message"}}`.
- All timestamps UTC, stored as `timestamptz`.
- Every new model/field needs an Alembic migration in the same task — don't leave
  schema drift for a later "sync migrations" pass.
- Structured JSON logging with `job_id`, `worker_id`, `queue_id`, `attempt` fields
  wherever relevant.
- Commit at the end of every completed phase/task, with a message referencing the
  phase (e.g. `feat(phase-1): JWT auth + project CRUD`).

## 8. Explicitly out of scope (don't build unless asked)

Queue sharding, distributed locking, full RBAC, rate limiting, WebSockets (polling is
the accepted trade-off — document it, don't apologize for it).

---

## 9. Current Status (UPDATE THIS SECTION AS WORK PROGRESSES)

**Last updated by:** (agent name / human) — (date)

| Phase | Status | Notes |
|---|---|---|
| 0 — Setup | Not started | Docker Compose, Alembic init pending |
| 1 — Auth & Projects | Not started | |
| 2 — Queues & Retry Policies | Not started | |
| 3 — Job Submission API | Not started | |
| 4A — Claim + Execute | Not started | **DO NOT let an agent restructure the claim query — see §5** |
| 4B — Heartbeat/Reclaim/DLQ/Idempotency | Not started | Idempotency mechanism not yet decided — see §6 |
| 5 — Observability | Not started | |
| 6 — Frontend Dashboard | Not started | |
| 7 — Bonus (workflow deps) | Not started | |
| 8 — Docs | Not started | |
| 9 — Tests | Not started | Concurrent-claim test is highest priority — write alongside 4A, not after |

**Known open decisions:**
- Idempotency mechanism (§6) — not yet chosen
- Org creation on signup: automatic vs explicit step — not yet decided
