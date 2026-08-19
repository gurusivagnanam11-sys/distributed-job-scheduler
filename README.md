# Distributed Job Scheduler

A production-inspired background job scheduling platform.

## Quick Start

```bash
# Clone and start all services
docker-compose up --build
```

This starts:
- **PostgreSQL** on port 5432
- **Backend API** on port 8000 (FastAPI + uvicorn)
- **Worker** (placeholder — Phase 4)
- **Frontend** on port 5173 (Vite + React)

## API Documentation

Once running, visit:
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

See [AGENTS.md](AGENTS.md) for the full repo layout, stack, and conventions.

## Development

### Running locally (without Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Database migrations

```bash
cd backend
alembic upgrade head
```
