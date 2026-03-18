# CLAUDE.md — QA Insight AI

## Project Overview

**QA Insight AI** is a 360° AI-powered software testing intelligence platform. It ingests test results from 50+ frameworks, uses a LangChain ReAct agent (via Ollama locally or cloud LLMs) to correlate failures, and pushes structured root-cause analysis to Jira.

- Local-LLM capable (air-gapped via Ollama)
- Multi-framework ingestion (Allure, TestNG, JUnit, etc.)
- OpenShift/Kubernetes native (Kustomize)

---

## Architecture

```
React SPA (frontend:3000)
      ↓
FastAPI Backend (backend:8000)
      ↓
┌─────────────────────────────────────┐
│  PostgreSQL  MongoDB  Redis  MinIO  │
│  ChromaDB    Ollama                 │
└─────────────────────────────────────┘
      ↓
Celery Workers (background AI triage, quality gates)
```

**Backend:** FastAPI + SQLAlchemy (async) + Motor (MongoDB) + Celery
**Frontend:** React 18 + Vite + TypeScript + Tailwind CSS + Zustand + SWR
**AI Layer:** LangChain ReAct agent with 5 investigation tools
**Databases:** PostgreSQL 16 (structured), MongoDB 7 (logs/artifacts), Redis 7 (broker), MinIO (S3 object store), ChromaDB (vectors)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend runtime | Python 3.11+ |
| Backend framework | FastAPI 0.115.5 |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| NoSQL | Motor 3.7 (MongoDB) |
| Object storage | aioboto3 (MinIO/S3) |
| Background jobs | Celery 5.4 + Flower |
| AI/LLM | LangChain 0.3.9 + LangGraph 0.2 |
| Local LLM | Ollama (qwen2.5, llama3, mistral) |
| Vector store | ChromaDB 0.5 |
| DB migrations | Alembic 1.14 |
| Frontend framework | React 18.3 |
| Build tool | Vite 6 |
| Language | TypeScript 5.6 |
| State management | Zustand 5 |
| Data fetching | SWR 2.2 + Axios |
| UI components | Radix UI + Recharts + D3 |
| Styling | Tailwind CSS 3.4 |
| Linting (BE) | ruff + mypy |
| Linting (FE) | ESLint + Prettier |
| Testing (BE) | pytest + pytest-asyncio |
| Testing (FE) | Vitest + Playwright |

---

## Common Commands

All commands are via `make` (see `Makefile` for full list):

```bash
make dev                  # Start full stack (docker compose up -d --build)
make stop                 # Stop all services
make clean                # Stop + remove all volumes (destructive)
make migrate              # Run pending Alembic migrations
make migrate-create MSG="name"  # Auto-generate new migration
make migrate-down         # Rollback last migration
make pull-llm             # Download Ollama models (qwen2.5:7b + nomic-embed-text)
make simulate-upload      # Send a sample test run to the API
make test-backend         # pytest tests/ -v
make test-backend-cov     # pytest with HTML coverage report
make test-frontend        # vitest
make test-e2e             # playwright
make test-agent           # AI agent unit tests (mocked tools)
make lint                 # ruff check + eslint
make format               # ruff format + prettier
make type-check           # mypy + tsc
make build                # Build production Docker images
make k8s-deploy-dev       # kubectl apply -k k8s/overlays/dev
make k8s-deploy-staging
make k8s-deploy-prod
make shell-backend        # bash in backend container
make shell-db             # psql in postgres container
make help                 # Show all commands
```

### Without Docker (hot-reload dev)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

---

## Service URLs (Local Dev)

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 (admin/password123) |
| Flower (Celery) | http://localhost:5555 |
| PostgreSQL | localhost:5432 |
| MongoDB | localhost:27017 |
| Redis | localhost:6379 |
| Ollama | http://localhost:11434 |

---

## Project Structure

```
qainsight-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory + router registration
│   │   ├── core/config.py       # Pydantic BaseSettings (all env vars)
│   │   ├── db/                  # postgres.py, mongo.py, minio.py
│   │   ├── models/              # postgres.py (ORM), schemas.py (Pydantic)
│   │   ├── routers/             # webhooks, projects, runs, metrics, search, analyze
│   │   ├── services/            # agent, ingestion, parsers, llm_factory, jira_client
│   │   ├── tools/               # LangChain agent tools (5 tools)
│   │   └── worker/              # celery_app.py + tasks.py
│   ├── migrations/              # Alembic migration versions
│   ├── tests/                   # pytest (conftest.py + test files)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/               # OverviewPage, RunsPage, TestCasePage, SearchPage, etc.
│   │   ├── components/          # ui/, charts/, layout/, ai/
│   │   ├── services/            # Axios API client modules
│   │   ├── hooks/               # SWR data-fetching hooks
│   │   ├── store/               # Zustand (projectStore.ts)
│   │   └── utils/               # formatters.ts
│   ├── package.json
│   └── Dockerfile
├── k8s/
│   ├── base/                    # Kustomize base (namespace, deployments, services, ingress)
│   └── overlays/                # dev, staging, prod
├── infra/                       # Infrastructure as Code
├── .github/workflows/ci.yml     # GitHub Actions CI/CD
├── scripts/                     # simulate-upload.sh, setup scripts
├── docs/                        # DEVELOPMENT.md, cloud-run-cloud-sql.md
├── docker-compose.yml           # Local dev stack
├── docker-compose.gcp-vm.yml    # GCP VM overlay
├── Makefile                     # Developer commands
├── .env.example                 # Complete env template
└── .env.gcp-vm.example          # GCP-specific env template
```

---

## Environment Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Description |
|----------|-------------|
| `APP_ENV` | dev / staging / prod |
| `LLM_PROVIDER` | ollama \| openai \| gemini \| lmstudio \| vllm |
| `LLM_MODEL` | Model name (e.g., qwen2.5:7b, gpt-4o) |
| `AI_OFFLINE_MODE` | true = Ollama only, no internet calls |
| `POSTGRES_*` | PostgreSQL connection settings |
| `MONGO_*` | MongoDB connection settings |
| `REDIS_*` | Redis broker settings |
| `MINIO_*` | Object storage settings |
| `CHROMA_*` | Vector store settings |
| `JIRA_*` | Jira integration (optional) |
| `SPLUNK_*` | Splunk log query (optional) |
| `JWT_SECRET_KEY` | Must be a strong random value in prod |

**Switching LLM providers** — just update `.env` and restart:
```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
docker compose restart backend worker
```

---

## Adding New Features

### New API endpoint
1. Define Pydantic schemas in `backend/app/models/schemas.py`
2. Create router in `backend/app/routers/<feature>.py`
3. Register in `backend/app/main.py` with `app.include_router(...)`
4. Add service logic in `backend/app/services/<feature>.py`
5. Write tests in `backend/tests/test_<feature>.py`
6. Add frontend API service in `frontend/src/services/<feature>Service.ts`
7. Create SWR hook in `frontend/src/hooks/use<Feature>.ts`
8. Build page in `frontend/src/pages/<Feature>Page.tsx`

### New LangChain agent tool
- Add tool file under `backend/app/tools/`
- Register in `backend/app/services/agent.py`

---

## CI/CD

**GitHub Actions** (`.github/workflows/ci.yml`):
- **Triggers:** Push to `main`/`develop`, PRs to `main`
- **backend-test:** ruff → mypy → pytest (with postgres + redis services)
- **frontend-test:** eslint → tsc → vitest
- **build:** Multi-stage Docker build → push to GHCR (`ghcr.io/<org>/<repo>`)
- **deploy:** `kubectl apply -k k8s/overlays/prod` (optional, on main)

---

## Kubernetes Deployment

Uses **Kustomize** with base + overlays pattern:

```bash
make k8s-deploy-dev       # 1 replica, debug logging
make k8s-deploy-staging   # 2 replicas, info logging
make k8s-deploy-prod      # 3 replicas backend, 2 frontend, error logging
make k8s-status           # Show pods, services, ingress
```

Namespace: `qainsight-ai`

---

## AI Agent Tools

The LangChain ReAct agent (`backend/app/services/agent.py`) has 5 tools:

| Tool | Purpose |
|------|---------|
| `fetch_stacktrace` | Retrieve full stack trace from MongoDB |
| `fetch_rest_payload` | Get request/response payloads |
| `query_splunk` | Search Splunk logs for time-window around test execution |
| `check_flakiness` | Query PostgreSQL for historical flakiness rate |
| `analyze_ocp` | Fetch OpenShift pod events for infra context |

---

## Documentation

| File | Purpose |
|------|---------|
| `README.md` | Overview, features, quick start |
| `installation.md` | GCP VM deployment guide |
| `docs/DEVELOPMENT.md` | Developer workflow, iterative phases |
| `docs/cloud-run-cloud-sql.md` | Cloud Run + Cloud SQL deployment |
| `.env.example` | Environment variable reference |
| `Makefile` | All developer commands |
