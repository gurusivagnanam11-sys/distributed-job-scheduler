# API Reference

Full request/response schemas, validation rules, and example payloads are available via the live interactive docs at `/docs` (Swagger UI) when the server is running. This reference is an organized overview, not a replacement for it.

## Auth

| Method + Path | Description | Auth required | Params / notes |
|---|---|---:|---|
| `POST /auth/signup` | Register a new user and auto-create their organization. | Public | Body includes email, password, and `organization_name`. Returns a JWT on success. |
| `POST /auth/login` | Authenticate with email/password and receive a JWT access token. | Public | Body includes email and password. |

## Projects & API Keys

| Method + Path | Description | Auth required | Params / notes |
|---|---|---:|---|
| `POST /projects` | Create a project in the current user’s organization. | JWT | Body includes project name and optional description. |
| `GET /projects` | List projects in the current user’s organization. | JWT | Pagination via `page` and `page_size`. |
| `GET /projects/{project_id}` | Fetch one project in the current user’s organization. | JWT | `project_id` path param. |
| `PATCH /projects/{project_id}` | Update a project in the current user’s organization. | JWT | `project_id` path param; body supports partial updates. |
| `DELETE /projects/{project_id}` | Delete a project in the current user’s organization. | JWT | `project_id` path param. |
| `POST /projects/{project_id}/api-keys` | Create an API key for a project. The raw key is returned once. | JWT | `project_id` path param; body includes label. |
| `GET /projects/{project_id}/api-keys` | List API keys for a project. | JWT | `project_id` path param. Shows prefixes and labels only. |
| `DELETE /projects/{project_id}/api-keys/{key_id}` | Revoke a project API key. | JWT | `project_id` and `key_id` path params. Revocation is idempotent only up to the first call; a second call returns 409. |

## Queues & Retry Policies

| Method + Path | Description | Auth required | Params / notes |
|---|---|---:|---|
| `POST /projects/{project_id}/queues` | Create a queue under a project. | JWT | `project_id` path param; body includes name and concurrency limit. |
| `GET /projects/{project_id}/queues` | List queues for a project. | JWT | Pagination via `page` and `page_size`. |
| `GET /queues/{id}` | Fetch one queue. | JWT | `id` path param. |
| `PATCH /queues/{id}` | Update queue name and/or concurrency limit. | JWT | `id` path param; body supports partial updates. |
| `DELETE /queues/{id}` | Delete a queue if it has no active non-terminal jobs. | JWT | `id` path param. Returns 409 if jobs are still active. |
| `POST /queues/{id}/pause` | Pause a queue. | JWT | `id` path param. |
| `POST /queues/{id}/resume` | Resume a paused queue. | JWT | `id` path param. |
| `GET /queues/{id}/stats` | Get queue job counts by status. | JWT | `id` path param. |
| `POST /queues/{id}/retry-policy` | Create a retry policy for a queue. | JWT | `id` path param; body includes max retries and backoff settings. Returns 409 if one already exists. |
| `GET /queues/{id}/retry-policy` | Fetch a queue’s retry policy. | JWT | `id` path param. |
| `PATCH /queues/{id}/retry-policy` | Update a queue’s retry policy. | JWT | `id` path param; body supports partial updates. |

## Jobs

| Method + Path | Description | Auth required | Params / notes |
|---|---|---:|---|
| `POST /queues/{queue_id}/jobs` | Submit a job to a queue. This one route handles immediate, delayed, scheduled, recurring, and batch submissions. | `JWT or API Key` | `queue_id` path param. API-key submissions are project-scoped; JWT submissions are org-scoped. Body may include `scheduled_at`, `cron_expression`, `batch`, `dedupe_key`, `depends_on_job_id`, and payload data. |
| `GET /queues/{queue_id}/jobs` | List jobs in a queue. | JWT | `queue_id` path param. Filters: `status`, `batch_id`, `created_after`, `created_before`. Pagination via `page` and `page_size`. |
| `GET /jobs/{id}` | Fetch one job. | JWT | `id` path param. |
| `GET /jobs/{id}/timeline` | Return a derived event timeline for a job from timestamps and logs. | JWT | `id` path param. |
| `GET /jobs/{id}/executions` | List execution attempts for a job. | JWT | `id` path param. Pagination via `page` and `page_size`. |
| `POST /jobs/{id}/retry` | Manually re-queue a `dead_letter` job. | JWT | `id` path param. Only works when the current status is `dead_letter`. |
| `GET /queues/{queue_id}/recurring-jobs` | List recurring-job templates for a queue. | JWT | `queue_id` path param. Pagination via `page` and `page_size`. |
| `PATCH /queues/{queue_id}/recurring-jobs/{template_id}` | Update a recurring-job template’s active state. | JWT | `queue_id` and `template_id` path params. |
| `DELETE /queues/{queue_id}/recurring-jobs/{template_id}` | Delete a recurring-job template. | JWT | `queue_id` and `template_id` path params. |

Notes on recurring jobs:

- There is no separate `POST /queues/{queue_id}/recurring-jobs` create route.
- Creation happens through `POST /queues/{queue_id}/jobs` when `cron_expression` is provided, which creates a recurring-job template behind the scenes.

## Workers

| Method + Path | Description | Auth required | Params / notes |
|---|---|---:|---|
| `GET /workers` | List workers. This endpoint is platform-wide, not org-scoped. | JWT | Filters by `status`. Pagination via `page` and `page_size`. |

## Metrics

| Method + Path | Description | Auth required | Params / notes |
|---|---|---:|---|
| `GET /queues/{id}/metrics` | Queue metrics endpoint with counts plus 24-hour throughput, success rate, and average execution duration. | JWT | `id` path param. |

## Authentication

There are two authentication methods in the API:

- JWT: obtain a token with `POST /auth/login`, then send it as `Authorization: Bearer <token>`.
- API key: create one with `POST /projects/{id}/api-keys`. The raw key is shown only once in the create response. Send it as `X-API-Key: <key>`.

Key scoping rule:

- API keys are project-scoped, not org-scoped. They are stricter than JWT auth. A key issued for one project can only submit jobs into queues that belong to that same project.
