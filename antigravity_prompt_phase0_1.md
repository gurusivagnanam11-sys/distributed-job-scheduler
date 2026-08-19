## Antigravity Prompt — Phase 0 (Setup) + Phase 1 (Auth & Project Management)

**Before starting:** read `AGENTS.md` at the repo root in full. It is the source of
truth for stack, folder layout, entity names, and conventions. Follow it exactly —
do not introduce a different stack, folder structure, or naming scheme even if you
think an alternative is better. At the end of this task, update the "Current Status"
table at the bottom of `AGENTS.md` (and mirror the same edit into
`PROJECT_CONTEXT.md` and `docs/CONTEXT.md` — all three must stay identical) so a
second agent (Codex) picking this up later knows exactly what's done.

### Task

Scaffold the full repo and implement Phase 0 + Phase 1 from `AGENTS.md`.

**Phase 0 — Setup**
1. Create the repo layout exactly as described in `AGENTS.md` §3.
2. `backend/app/core/config.py` — Pydantic Settings, load from `.env`, include DB URL,
   JWT secret, JWT expiry, worker lease duration default.
3. `backend/app/core/database.py` — async SQLAlchemy engine + session factory.
4. SQLAlchemy models for ALL entities listed in `AGENTS.md` §4 (Organization, User,
   Project, Queue, RetryPolicy, Job, JobExecution, JobLog, Worker, WorkerHeartbeat,
   DeadLetterEntry) — even though only Auth/Project are used this phase, scaffold the
   full schema now so later phases don't need schema-restructuring migrations.
   Include all fields mentioned in §4, correct FKs, cascade behavior (deleting an
   Organization should cascade to Projects/Queues/Jobs — deleting a Job should NOT
   cascade-delete its JobExecution history, that's an audit trail).
5. Alembic: init, generate first migration for the full schema.
6. `docker-compose.yml`: postgres, backend (uvicorn), frontend (vite dev server),
   with healthchecks and proper env var wiring. A reviewer must be able to run
   `docker-compose up` from a clean clone and have it work.
7. `.env.example` with every variable the app needs.

**Phase 1 — Auth & Project Management**
1. JWT auth: `POST /auth/signup`, `POST /auth/login`, `get_current_user` dependency
   used by protected routes. Password hashing with bcrypt/argon2 (your choice, state
   which in a code comment).
2. Decide and implement: is an Organization auto-created on signup, or is there an
   explicit "create org" step? Make a decision, implement it consistently, and write
   ONE sentence explaining the choice as a comment at the top of the auth router.
   Then update `AGENTS.md` "Known open decisions" to mark this resolved.
3. Project CRUD (`POST/GET/PATCH/DELETE /projects`), scoped to the current user's
   organization — a user must never be able to see or modify another org's projects.
4. API key generation per project (`POST /projects/{id}/api-keys`) — this is separate
   from user JWTs and is what job-submission clients will use in later phases. Store
   only a hash of the key, return the raw key once on creation.
5. Pydantic request/response schemas for everything above, with real validation
   (email format, password min length, project name constraints, etc).
6. Structured error responses matching the `{"error": {"code", "message"}}` shape from
   `AGENTS.md` §7 — no raw stack traces or default FastAPI validation error shape
   leaking to the client.

### Constraints
- Do not touch worker/claim logic — that's Phase 4, explicitly out of scope here.
- Do not add Celery, Redis, or any queue broker — this project builds its own worker
  polling mechanism in a later phase.
- Every model needs its migration in this same task. No schema drift.
- Commit at the end with message `feat(phase-0-1): repo scaffold, docker compose, auth, project CRUD`.

### When done
Update the Current Status table in all three context files (`AGENTS.md`,
`PROJECT_CONTEXT.md`, `docs/CONTEXT.md`) marking Phase 0 and Phase 1 as Done, with a
one-line note on the org-creation decision made in step 2 above. Leave Phase 2 onward
untouched — that's a separate task.
