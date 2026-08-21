# Distributed Job Scheduler

A production-inspired distributed job scheduling platform with JWT auth, organizations, projects, queues, five job submission modes, atomic worker claiming, retries and dead-letter handling, observability endpoints, and a React dashboard for exploring jobs and queues.

## Prerequisites

- Docker
- Docker Compose

## Setup

1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. Set any secrets you want to override locally.
4. `GEMINI_API_KEY` is optional and is used only for the AI failure-summary bonus feature. Everything else works without it.
5. Start the stack:

```bash
docker-compose up --build
```

6. Wait for the services to finish starting and become healthy.
7. If migrations do not run automatically in your environment, apply them manually:

```bash
docker-compose exec backend alembic upgrade head
```

## Running Tests

```bash
docker-compose exec backend pytest -v
```

## Accessing the Application

- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Frontend Dashboard: [http://localhost:5173](http://localhost:5173)

## Project Structure

```text
backend/
  app/
  alembic/
  tests/
frontend/
  src/
docs/
  ARCHITECTURE.md
  ER_DIAGRAM.md
  API.md
  DESIGN_DECISIONS.md
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [ER Diagram](docs/ER_DIAGRAM.md)
- [API Documentation](docs/API.md)
- [Design Decisions](docs/DESIGN_DECISIONS.md)
