# Design Decisions

## Phase 0 Decisions

### 1. Job Deletion → RESTRICT (not CASCADE or SET NULL)

**Decision**: Jobs that have `JobExecution` or `DeadLetterEntry` records cannot be hard-deleted.

**Rationale**: SET NULL on `JobExecution.job_id` would orphan execution rows — the audit trail
would have execution history with no idea which job it belonged to. CASCADE would destroy the
audit trail entirely. RESTRICT forces soft-delete/archival patterns, which is the correct
production behavior.

**Implication**: The Job deletion API endpoint (Phase 3+) must either:
- Reject deletion of jobs with executions (return 409 Conflict), or
- Implement soft-delete (status → archived) instead of hard delete

### 2. Worker.last_heartbeat_at Sync Rule

**Decision**: When inserting a `WorkerHeartbeat` row, `Worker.last_heartbeat_at` is updated
in the **same transaction**.

**Rationale**: Worker-status queries in Phase 5/6 need to quickly determine if a worker is
alive. If `last_heartbeat_at` only lives in the heartbeat table, every status query requires
a JOIN + MAX aggregation on potentially millions of heartbeat rows. The denormalized column
on Worker makes these queries O(1).

### 3. UUID Primary Keys

**Decision**: All entities use UUID v4 primary keys.

**Rationale**: No collision risk across distributed workers. No information leakage from
sequential IDs. Compatible with multi-region deployment if needed later.

### 4. Password Hashing: bcrypt

**Decision**: Use bcrypt via `passlib` for password hashing.

**Rationale**: Well-audited, widely used, sufficient for this system's auth needs.
