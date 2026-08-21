# Distributed Job Scheduler

📌 **Repository URL:** https://github.com/gurusivagnanam11-sys/distributed-job-scheduler  
*(You can download or clone the project via this link)*

---

## **🚀 HOW TO RUN AND TEST**

### **1. HOW TO RUN THE PROJECT**

**Step 1: Copy environment variables**
```bash
cp .env.example .env
```

**Step 2: Start all services via Docker Compose (PostgreSQL, Backend API, Worker, React Dashboard)**
```bash
docker-compose up --build
```
*(Database migrations run automatically on container startup)*

**Access Endpoints:**
- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)
- **Interactive API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### **2. HOW TO RUN TESTS**

**Run the complete automated test suite (51 passing unit, integration, and concurrency tests):**
```bash
docker-compose exec backend pytest -v
```

---

A production-inspired distributed background job scheduling platform built with **FastAPI**, **PostgreSQL** (SQLAlchemy 2.0 async), and **React (Vite)**.

The system reliably executes asynchronous background jobs across multiple worker instances using PostgreSQL transactional row locking (`SELECT ... FOR UPDATE` + `SKIP LOCKED`).

---

## 🚀 Key Features

- **Multi-Tenant Hierarchy**: Organizations -> Users -> Projects -> Queues -> Jobs.
- **Dual Authentication**: JWT bearer tokens for dashboard/API users; project-scoped `X-API-Key` headers for automated job submitters.
- **Queue Concurrency Control**: Per-queue configurable concurrency limits enforced atomically during claiming.
- **Queue Pause & Resume**: Instantly pause job claiming on a queue without stopping active executions.
- **5 Submission Modes**: Immediate, Delayed (`delay_seconds`), Scheduled (`scheduled_at`), Recurring Cron (`cron_expression`), and Batch (atomic multi-job submission).
- **Workflow & Dependency Graphs**: Job DAG execution (`depends_on_job_id`) ensuring parent jobs complete before children are claimed.
- **Idempotency & Deduplication**: Queue-scoped `dedupe_key` prevents duplicate active submissions; `JobExecution` attempt tracking guarantees execution auditability.
- **Atomic Multi-Worker Claiming**: `SELECT ... FOR UPDATE SKIP LOCKED` guarantees zero double-claim race conditions across worker instances.
- **Worker Heartbeats & Lease Recovery**: Background heartbeat loop extends leases; background reaper loop reclaims abandoned jobs from crashed workers.
- **Flexible Retry Strategies**: Configurable Fixed, Linear, and Exponential backoff algorithms.
- **Dead-Letter Queue (DLQ)**: Automatic routing of exhausted jobs to DLQ with manual single-click re-queueing.
- **Rich Observability**: Granular job timelines, execution audit trails, queue throughput metrics, and structured JSON logging (`job_id`, `worker_id`, `attempt`).
- **AI Failure Summaries (Bonus)**: LLM integration (Gemini / Claude) generating plain-English root-cause analyses for failed job executions.
- **Full React Dashboard**: Modern UI for queue configuration, real-time job exploration, submission modals, worker status monitoring, and key management.

---

## 🏗 Architecture Overview

```text
               +-----------------------------+
               |   React (Vite) Dashboard    |
               +--------------+--------------+
                              | REST API (JWT / X-API-Key)
                              v
               +-----------------------------+
               |    FastAPI Backend Server   |
               +--------------+--------------+
                              | Async SQLAlchemy 2.0
                              v
               +-----------------------------+
               |     PostgreSQL Database     |
               +--------------+--------------+
                              ^
            SELECT ... FOR    | Worker Lease
          UPDATE SKIP LOCKED  | & Heartbeats
       +----------------------+----------------------+
       |                      |                      |
+------+------+        +------+------+        +------+------+
| Worker 1    |        | Worker 2    |        | Worker N    |
+-------------+        +-------------+        +-------------+
```

For complete technical specifications, see [Architecture Documentation](docs/ARCHITECTURE.md) and [ER Diagram](docs/ER_DIAGRAM.md).

---

## ⚡ Concurrency & Reliability Model

### Atomic Claim Query
Workers do not rely on Redis or Celery. Jobs are claimed directly from PostgreSQL using transactional row locking:

1. **Queue-Level Concurrency Lock**: Locks the target queue row (`SELECT concurrency_limit FROM queues ... FOR UPDATE`) to evaluate available execution slots against currently running jobs within the same transaction.
2. **Job-Level Lock-Free Claiming**: Uses `FOR UPDATE SKIP LOCKED` to select eligible jobs ordered by priority (`priority DESC, scheduled_at ASC`), preventing worker contention or lock-blocking.
3. **Lease Expiration**: Sets a `lease_expires_at` timestamp on claim.

```sql
BEGIN;
SELECT id FROM queues WHERE id = :queue_id AND status = 'active' FOR UPDATE;

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

### Worker Recovery & Reaper Loop
- **Worker Heartbeat**: Active workers emit heartbeats every 10 seconds, refreshing `lease_expires_at` for running tasks.
- **Reaper Process**: Periodically identifies stale jobs (`status IN ('claimed', 'running') AND lease_expires_at < now()`) using `FOR UPDATE SKIP LOCKED`. Stale jobs under max attempts transition to `retrying`; exhausted jobs move to `dead_letter`.
- **Graceful Shutdown**: Intercepts `SIGTERM`/`SIGINT`, stopping new claims and granting in-flight jobs a timeout window before worker termination.

---

## 🔄 Job Lifecycle & State Machine

```text
[Submitted] ---> (queued / scheduled)
                      |
                      v (Worker Atomic Claim)
                  (claimed)
                      |
                      v (Execution Start)
                  (running)
                      |
        +-------------+-------------+
        |                           |
        v (Success)                 v (Failure)
   (completed)                attempt < max_attempts ?
                                    |
                        +-----------+-----------+
                        |                       |
                        v (Yes)                 v (No)
                    (retrying)              (dead_letter)
                        |                       |
                        +---> (queued) <--------+ (Manual Retry)
```

---

## 🔒 Authentication & Scoping

- **JWT Authentication**: User login/signup (`/auth/signup`, `/auth/login`). Authorizes full access to organization resources, projects, and queues.
- **Project-Scoped API Keys**: Generated per-project (`X-API-Key`). Restricted strictly to submitting jobs to queues belonging to that specific project.

---

## 🤖 AI Failure Summaries (Bonus)

Failed job executions feature an automated root-cause analysis endpoint (`GET /jobs/{id}/failure-summary`).
- Uses Gemini / Claude to analyze execution stack traces, stderr, and attempt parameters into concise, plain-English explanations.
- Results are cached in `JobExecution.ai_failure_summary`.
- Graceful degradation: returns raw error details if LLM credentials are missing or API calls time out.

---

## 🛠 Quickstart & Setup

### Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose

### Running the Stack
1. Clone the repository and copy the environment file:
   ```bash
   cp .env.example .env
   ```
2. Start all services (PostgreSQL, Backend API, Worker, React Dashboard):
   ```bash
   docker-compose up --build
   ```
3. Database migrations (`alembic upgrade head`) execute **automatically** on container startup.

### Endpoints & Dashboard
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Testing

The codebase includes a comprehensive suite of 51 unit and integration tests covering concurrency, atomic claim contention, reaper race prevention, worker heartbeats, retry backoff algorithms, API key security, and observability.

Run the test suite inside the Docker container:

```bash
docker-compose exec backend pytest -v
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/jobscheduler` | PostgreSQL connection string |
| `JWT_SECRET` | `dev-secret-change-in-production` | Secret key for signing JWT tokens |
| `JWT_EXPIRY_MINUTES` | `30` | JWT token expiration time |
| `WORKER_LEASE_DURATION_SECONDS` | `300` | Job lease timeout before reaper reclaim |
| `GEMINI_API_KEY` | *(Optional)* | API key for AI Failure Summary feature |

---

## 📚 Technical Documentation

- 📄 [Architecture Specification](docs/ARCHITECTURE.md)
- 📊 [Entity-Relationship Diagram](docs/ER_DIAGRAM.md)
- 🔌 [API Reference](docs/API.md)
- 🎯 [Design Decisions & Trade-offs](docs/DESIGN_DECISIONS.md)

---

## ⚖️ Trade-offs & Limitations

- **Polling vs WebSockets**: Background workers poll queues every 1 second. While introducing minimal database query load, it eliminates broker complexity (e.g. RabbitMQ/Redis) and keeps PostgreSQL as the single source of truth.
- **Idempotency Contract**: Scheduling idempotency is guaranteed via `dedupe_key`. Handler execution follows at-least-once semantics tracked via `JobExecution` rows; job payload handlers must implement idempotent side-effects if exactly-once execution is required.
