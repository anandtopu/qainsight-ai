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
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic BaseSettings (all env vars) — uses Pydantic v2 SettingsConfigDict
│   │   │   └── security.py      # JWT helpers (create_access_token, verify_token)
│   │   ├── db/
│   │   │   ├── postgres.py      # Async SQLAlchemy engine + session factory
│   │   │   ├── mongo.py         # Motor async MongoDB client
│   │   │   ├── minio.py         # aioboto3 MinIO/S3 client
│   │   │   └── storage.py       # STORAGE_BACKEND router (minio | local)
│   │   ├── models/
│   │   │   ├── postgres.py      # SQLAlchemy ORM models
│   │   │   └── schemas.py       # Pydantic v2 request/response schemas
│   │   ├── routers/
│   │   │   ├── webhooks.py      # POST /webhook/ingest — test result ingestion entry point
│   │   │   ├── projects.py      # CRUD for projects
│   │   │   ├── runs.py          # Test run listing and detail
│   │   │   ├── metrics.py       # Dashboard KPI metrics
│   │   │   ├── search.py        # Full-text search across test cases
│   │   │   ├── analyze.py       # Trigger AI root-cause analysis
│   │   │   ├── analytics.py     # /flaky-tests, /failure-categories, /top-failing, /coverage, /defects, /ai-summary
│   │   │   ├── auth.py          # POST /auth/register, /auth/login (JWT), GET /auth/me
│   │   │   ├── live.py          # WebSocket /ws/live/{project_id} (ConnectionManager)
│   │   │   ├── integrations.py  # External integrations (Jira, etc.)
│   │   │   └── debug.py         # Dev-only debug endpoints
│   │   ├── services/
│   │   │   ├── agent.py         # LangChain ReAct agent (5 tools, AgentExecutor with timeout)
│   │   │   ├── ingestion.py     # Orchestrates parser → DB persistence
│   │   │   ├── metrics_service.py  # Analytics queries (uses Python-side datetime arithmetic, not SQL INTERVAL literals)
│   │   │   ├── llm_factory.py   # LLM provider switcher (ollama/openai/gemini/lmstudio/vllm)
│   │   │   ├── jira_client.py   # Jira REST API integration
│   │   │   ├── allure_parser.py # Allure JSON report parser
│   │   │   ├── testng_parser.py # TestNG XML parser
│   │   │   ├── ocp_client.py    # OpenShift/K8s event client
│   │   │   └── mock_generator.py # Test data generator for dev
│   │   ├── tools/               # LangChain agent tools (one file per tool)
│   │   │   ├── fetch_stacktrace.py
│   │   │   ├── fetch_rest_payload.py
│   │   │   ├── query_splunk.py
│   │   │   ├── check_flakiness.py
│   │   │   └── analyze_ocp.py
│   │   └── worker/
│   │       ├── celery_app.py    # Celery app + Redis broker config
│   │       └── tasks.py         # Background tasks (AI triage, quality gates)
│   ├── migrations/              # Alembic migration versions
│   ├── tests/                   # pytest (conftest.py + test files)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Router (react-router-dom) + layout
│   │   ├── main.tsx             # Vite entry point
│   │   ├── pages/
│   │   │   ├── OverviewPage.tsx       # Main dashboard KPIs
│   │   │   ├── ProjectsPage.tsx       # Project list + New Project modal
│   │   │   ├── RunsPage.tsx           # Test run listing
│   │   │   ├── RunDetailPage.tsx      # Per-run test case breakdown
│   │   │   ├── TestCasePage.tsx       # Individual test case + AI panel
│   │   │   ├── SearchPage.tsx         # Full-text search UI
│   │   │   ├── TrendsPage.tsx         # Period-based KPI trend charts
│   │   │   ├── FailureAnalysisPage.tsx # Flaky leaderboard + failure category pie
│   │   │   ├── CoveragePage.tsx       # Suite coverage table + stacked bar
│   │   │   ├── DefectsPage.tsx        # Paginated defects + Jira links
│   │   │   └── SettingsPage.tsx       # App settings
│   │   ├── components/
│   │   │   ├── ui/              # LoadingSpinner, StatusBadge, MetricCard, PageHeader, EmptyState, Pagination
│   │   │   ├── charts/          # PassRateGauge, DefectDonut, TrendChart
│   │   │   ├── layout/          # AppLayout, Sidebar, TopBar
│   │   │   └── ai/              # AIAnalysisPanel, LogViewer
│   │   ├── services/
│   │   │   ├── api.ts           # Axios base instance (baseURL from VITE_API_URL)
│   │   │   ├── projectsService.ts
│   │   │   ├── runsService.ts
│   │   │   ├── metricsService.ts
│   │   │   ├── analyticsService.ts  # Calls /analytics/* endpoints
│   │   │   ├── aiService.ts
│   │   │   └── searchService.ts
│   │   ├── hooks/
│   │   │   ├── useRuns.ts       # SWR hooks for runs
│   │   │   └── useMetrics.ts    # useFlakyTests, useFailureCategories, useTopFailing, useCoverage, useDefects, useAiSummary
│   │   ├── store/
│   │   │   └── projectStore.ts  # Zustand: selected project + project list
│   │   └── utils/
│   │       └── formatters.ts    # Date, duration, status formatters
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
| `STORAGE_BACKEND` | minio \| local (required — no default) |
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

## Coding Conventions

### Backend

- **Pydantic v2 only.** Use `@field_validator(..., mode="before")` + `@classmethod` for validators. Use `model_config = SettingsConfigDict(...)` in Settings. Never use deprecated v1 `@validator` or `class Config`.
- **Async everywhere.** All DB calls, HTTP calls, and service methods must be `async def`. SQLAlchemy sessions use `async with AsyncSession` from `backend/app/db/postgres.py`.
- **No SQL INTERVAL string literals with parameters.** PostgreSQL cannot bind params inside string literals like `INTERVAL ':days days'`. Always compute `period_start` in Python (`datetime.now(timezone.utc) - timedelta(days=days)`) and pass as a bound param.
- **Router pattern:** Thin routers — business logic belongs in `services/`, not routers. Routers only handle HTTP concerns (status codes, request parsing, dependency injection).
- **Celery tasks** in `worker/tasks.py` are fire-and-forget — they accept simple serializable args (IDs, dicts), not ORM objects.
- **AgentExecutor** must include `max_execution_time=settings.AI_TIMEOUT_SECONDS` to prevent runaway LLM calls.

### Frontend

- **SWR for all data fetching.** Add hooks in `hooks/` that wrap `useSWR`; pages import hooks, not raw service calls directly.
- **Zustand for global state.** Only project selection and project list live in the store (`store/projectStore.ts`). Per-page state stays local.
- **`api.ts` is the Axios base.** All service files import from `services/api.ts`. Never create a second Axios instance.
- **TestCase breadcrumbs** use `runId?.slice(0,8)` — the `build_number` field lives on `TestRun`, not `TestCase`.
- **TypeScript strict mode is on** — avoid `any`; use `unknown` + type guards when necessary.

---

## Known Pitfalls

These bugs have been encountered and fixed — avoid reintroducing them:

1. **SQL INTERVAL parameterization** — `INTERVAL ':days days'` does NOT work in PostgreSQL. Use Python `timedelta` instead. See `services/metrics_service.py` and `routers/search.py`.
2. **Pydantic v1 syntax** — `@validator` and `class Config` are removed in Pydantic v2. All validators in `core/config.py` use `@field_validator`.
3. **Missing `.env`** — Docker Compose reads `.env` at startup; without it the stack fails silently. `STORAGE_BACKEND` has no default and must be set explicitly.
4. **AgentExecutor timeout** — Without `max_execution_time`, a slow Ollama model will hang the request indefinitely.
5. **TestCase `build_number`** — This field is on `TestRun`, not `TestCase`. Don't reference `tc.build_number`.

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
