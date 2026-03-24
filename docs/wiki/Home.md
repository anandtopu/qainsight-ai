# QA Insight AI Wiki

Welcome to the project wiki for **QA Insight AI**.

QA Insight AI is a 360-degree testing intelligence platform that ingests test results from multiple frameworks, correlates failures using AI, and helps teams move faster from failed test to root cause.

## What You Get

- FastAPI backend for ingestion, analytics, and AI orchestration
- React dashboard for trends, flaky tests, defects, and release signals
- LangChain ReAct agent with investigation tools (stack traces, payloads, logs, infra events)
- Local LLM mode via Ollama for air-gapped/offline deployments
- MCP server for AI assistants and CI integrations

## Architecture at a Glance

```text
React SPA (frontend:3000)
      ↓
FastAPI Backend (backend:8000)
      ↓
PostgreSQL | MongoDB | Redis | MinIO | ChromaDB | Ollama
      ↓
Celery Workers (AI triage, quality gates)
```

## Repository Layout

- `backend/`: FastAPI services, routers, models, workers
- `frontend/`: React + Vite UI
- `mcp/`: MCP server (tools, resources, prompts)
- `k8s/`: Kustomize base and overlays
- `docs/`: engineering and deployment docs

## Local Development (Docker)

### 1) Prepare environment

Copy `.env.example` to `.env` and set required values. Most importantly, set:

- `STORAGE_BACKEND=minio` (or `local`)
- `JWT_SECRET_KEY=<strong-secret>`

### 2) Start all services

```powershell
docker compose up -d --build
```

### 3) Run DB migrations

```powershell
docker compose exec backend alembic upgrade head
```

### 4) Open service URLs

- Dashboard: <http://localhost:3000>
- API docs (Swagger): <http://localhost:8000/docs>
- MinIO Console: <http://localhost:9001>
- Flower: <http://localhost:5555>
- MCP SSE endpoint: <http://localhost:8002/sse>

## Windows Note (No `make` command)

On Windows PowerShell, `make` is often not installed by default. Use direct Docker Compose commands instead of `make dev`:

```powershell
docker compose up -d --build
```

Equivalent mappings:

- `make dev` -> `docker compose up -d --build`
- `make stop` -> `docker compose down`
- `make clean` -> `docker compose down -v --remove-orphans`

## Troubleshooting

### `ERR_EMPTY_RESPONSE` on `http://localhost:8000/docs`

This usually means the backend container is not running or crashed during startup.

Check status:

```powershell
docker compose ps
```

Check backend logs:

```powershell
docker compose logs -f backend
```

Common causes:

- Missing `.env`
- `STORAGE_BACKEND` not set
- Database not healthy yet
- Migration/schema issue

## Stop the Application

```powershell
docker compose down
```

To stop and remove volumes (destructive):

```powershell
docker compose down -v --remove-orphans
```

## Useful Commands

```powershell
docker compose logs -f
docker compose logs -f backend worker
docker compose restart backend worker
docker compose exec backend pytest tests/ -v
```

## More Documentation

- `README.md`
- `docs/DEVELOPMENT.md`
- `docs/cloud-run-cloud-sql.md`
- `CLAUDE.md`

