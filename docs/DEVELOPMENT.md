# QA Insight AI — Developer Guide

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/yourorg/qainsight-ai.git
cd qainsight-ai
cp .env.example .env

# 2. Start all services
make dev

# 3. Run database migrations
make migrate

# 4. Pull local LLM (Ollama)
make pull-llm        # qwen2.5:7b + nomic-embed-text

# 5. Simulate a test run
make simulate-upload
```

Services will be available at:
| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API Docs | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |
| Flower (Celery) | http://localhost:5555 |

---

## Project Structure

```
qainsight-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI app factory + router registration
│   │   ├── core/
│   │   │   ├── config.py        ← All settings (Pydantic BaseSettings)
│   │   │   └── security.py      ← JWT helpers
│   │   ├── db/
│   │   │   ├── postgres.py      ← Async SQLAlchemy engine + session
│   │   │   ├── mongo.py         ← Motor MongoDB client
│   │   │   └── minio.py         ← aioboto3 S3 helpers
│   │   ├── models/
│   │   │   ├── postgres.py      ← SQLAlchemy ORM models (all tables)
│   │   │   └── schemas.py       ← Pydantic v2 request/response schemas
│   │   ├── routers/             ← One module per API feature area
│   │   │   ├── webhooks.py      ← POST /webhooks/minio
│   │   │   ├── projects.py      ← CRUD /api/v1/projects
│   │   │   ├── runs.py          ← GET /api/v1/runs + test cases
│   │   │   ├── metrics.py       ← GET /api/v1/metrics/*
│   │   │   ├── search.py        ← GET /api/v1/search
│   │   │   ├── analyze.py       ← POST /api/v1/analyze (AI triage)
│   │   │   └── integrations.py  ← POST /api/v1/integrations/jira
│   │   ├── services/            ← Business logic (no HTTP concerns)
│   │   │   ├── agent.py         ← LangChain ReAct agent runner
│   │   │   ├── ingestion.py     ← Allure/TestNG → PostgreSQL + MongoDB
│   │   │   ├── allure_parser.py ← Parse Allure JSON result files
│   │   │   ├── testng_parser.py ← Parse TestNG surefire XML
│   │   │   ├── llm_factory.py   ← Provider-agnostic LLM factory
│   │   │   ├── jira_client.py   ← Jira REST API v3 + ADF builder
│   │   │   ├── metrics_service.py ← Dashboard KPI aggregations
│   │   │   └── ocp_client.py    ← OpenShift pod metadata queries
│   │   ├── tools/               ← LangChain agent tool definitions
│   │   │   ├── fetch_stacktrace.py
│   │   │   ├── fetch_rest_payload.py
│   │   │   ├── query_splunk.py
│   │   │   ├── check_flakiness.py
│   │   │   └── analyze_ocp.py
│   │   └── worker/
│   │       ├── celery_app.py    ← Celery configuration + beat schedule
│   │       └── tasks.py         ← Background task definitions
│   ├── migrations/
│   │   ├── env.py               ← Alembic async environment
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── tests/
│   │   ├── conftest.py          ← Shared fixtures
│   │   └── test_agent.py        ← Agent unit tests (mocked tools)
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx             ← React entry point
│   │   ├── App.tsx              ← Router with all lazy-loaded routes
│   │   ├── index.css            ← Tailwind + custom component classes
│   │   ├── pages/               ← One file per route
│   │   │   ├── OverviewPage.tsx      ← Executive Dashboard
│   │   │   ├── RunsPage.tsx          ← Jenkins build list
│   │   │   ├── RunDetailPage.tsx     ← Test cases within a run
│   │   │   ├── TestCasePage.tsx      ← Split-pane detail + AI panel
│   │   │   ├── SearchPage.tsx        ← Full-text search
│   │   │   ├── CoveragePage.tsx      ← (Phase 4 stub)
│   │   │   ├── FailureAnalysisPage.tsx ← (Phase 4 stub)
│   │   │   ├── TrendsPage.tsx        ← (Phase 3 stub)
│   │   │   ├── DefectsPage.tsx       ← (Phase 4 stub)
│   │   │   ├── ProjectsPage.tsx      ← Project management
│   │   │   └── SettingsPage.tsx      ← Configuration overview
│   │   ├── components/
│   │   │   ├── ui/              ← Generic reusable components
│   │   │   │   ├── MetricCard.tsx
│   │   │   │   ├── StatusBadge.tsx
│   │   │   │   ├── LoadingSpinner.tsx
│   │   │   │   ├── EmptyState.tsx
│   │   │   │   ├── Pagination.tsx
│   │   │   │   └── PageHeader.tsx
│   │   │   ├── charts/          ← Recharts wrappers
│   │   │   │   ├── TrendChart.tsx
│   │   │   │   ├── PassRateGauge.tsx
│   │   │   │   └── DefectDonut.tsx
│   │   │   ├── layout/          ← App shell
│   │   │   │   ├── AppLayout.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── TopBar.tsx
│   │   │   └── ai/              ← AI-specific components
│   │   │       ├── AIAnalysisPanel.tsx  ← Full triage result panel
│   │   │       └── LogViewer.tsx        ← Dark terminal stack trace
│   │   ├── services/            ← Axios API client modules
│   │   │   ├── api.ts           ← Base axios instance
│   │   │   ├── metricsService.ts
│   │   │   ├── runsService.ts
│   │   │   ├── aiService.ts
│   │   │   ├── projectsService.ts
│   │   │   └── searchService.ts
│   │   ├── hooks/               ← SWR data-fetching hooks
│   │   │   ├── useMetrics.ts
│   │   │   └── useRuns.ts
│   │   ├── store/
│   │   │   └── projectStore.ts  ← Zustand: active project state
│   │   └── utils/
│   │       └── formatters.ts    ← Date, duration, status helpers
│   └── package.json
│
├── k8s/
│   ├── base/                    ← Kustomize base (all environments)
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml         ← TEMPLATE ONLY — never commit real values
│   │   ├── rbac.yaml
│   │   ├── backend-deployment.yaml  (+ HPA)
│   │   ├── frontend-deployment.yaml
│   │   ├── ollama-deployment.yaml   (+ PVC)
│   │   ├── services.yaml
│   │   └── ingress.yaml
│   └── overlays/
│       ├── dev/kustomization.yaml
│       ├── staging/kustomization.yaml
│       └── prod/kustomization.yaml
│
├── .github/workflows/
│   └── ci.yml                   ← Test → Build → Push → Deploy pipeline
│
├── scripts/
│   ├── init-db.sql              ← PostgreSQL extension setup
│   ├── simulate-upload.sh       ← End-to-end ingestion test
│   └── setup-minio.sh           ← One-time MinIO configuration
│
├── docker-compose.yml           ← Full local development stack
├── .env.example                 ← All environment variables documented
├── Makefile                     ← Developer convenience commands
└── README.md
```

---

## Development Workflow

### Adding a new API endpoint

1. Define Pydantic schemas in `backend/app/models/schemas.py`
2. Create router function in `backend/app/routers/<feature>.py`
3. Register in `backend/app/main.py` with `app.include_router(...)`
4. Add service logic in `backend/app/services/<feature>.py`
5. Write tests in `backend/tests/test_<feature>.py`
6. Add frontend service method in `frontend/src/services/<feature>Service.ts`
7. Create SWR hook in `frontend/src/hooks/use<Feature>.ts`
8. Build/update page component in `frontend/src/pages/<Feature>Page.tsx`

### Running only backend in hot-reload mode (without Docker)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env .env
uvicorn app.main:app --reload --port 8000
```

### Running only frontend in hot-reload mode

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000 with Vite HMR
```

### Switching LLM providers

Edit `.env`:
```bash
# Local Ollama (default — offline)
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b

# OpenAI (requires internet + API key)
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-...
AI_OFFLINE_MODE=false
```

Then restart the backend: `docker compose restart backend worker`

### Iterative development phases

| Phase | Feature area | Key files to work on |
|-------|-------------|---------------------|
| P1 | Infrastructure | `docker-compose.yml`, `backend/app/main.py`, DB setup |
| P2 | Ingestion | `services/ingestion.py`, `services/allure_parser.py`, `routers/webhooks.py` |
| P3 | Core dashboards | `pages/OverviewPage.tsx`, `pages/RunsPage.tsx`, `pages/TestCasePage.tsx` |
| P4 | Analytics | `pages/CoveragePage.tsx`, `pages/FailureAnalysisPage.tsx`, `pages/TrendsPage.tsx` |
| P5 | AI triage | `services/agent.py`, `tools/`, `components/ai/AIAnalysisPanel.tsx` |
| P6 | Quality Gates | New `routers/quality_gates.py` + frontend |
| P7 | Production | `k8s/`, `.github/workflows/ci.yml` |
