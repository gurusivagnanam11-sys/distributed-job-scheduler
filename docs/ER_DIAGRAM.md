# ER Diagram

> Full ER diagram will be added in Phase 8.

## Entities

Organization → User, Project → Queue → Job → JobExecution, JobLog
Queue → RetryPolicy (1:1)
Job → DeadLetterEntry
Worker → WorkerHeartbeat

See `AGENTS.md` §4 for the complete entity list and field definitions.
