# QA Insight AI — Developer Guide

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/yourorg/qainsight-ai.git
cd qainsight-ai
cp .env.example .env

# 2. Start all services
make dev

# If make is unavailable on your shell (common on Windows)
docker compose up -d --build

# 3. Run database migrations
make migrate

# 4. Pull local LLM (Ollama)
make pull-llm        # qwen2.5:7b + nomic-embed-text

# 5. Create your first user account (no default credentials exist)
#    Easiest: open http://localhost:8000/docs → POST /api/v1/auth/register → Try it out
#
#    Git Bash / macOS / Linux:
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","username":"admin","full_name":"Admin","password":"changeme123"}'
#
#    Windows cmd.exe (single line, escaped quotes):
#    curl -s -X POST http://localhost:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"email\":\"admin@example.com\",\"username\":\"admin\",\"full_name\":\"Admin\",\"password\":\"changeme123\"}"

# 6. Simulate a test run
make simulate-upload

# 7. Set up MCP server (optional — for AI Assistant integration)
make mcp-install
```

Services will be available at:
| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | Email + password you registered in step 5 |
| API Docs | http://localhost:8000/docs | — (use the Authorize button with a JWT token) |
| MinIO Console | http://localhost:9001 | `admin` / `password123` |
| Flower (Celery) | http://localhost:5555 | No auth in dev |
| MCP SSE Server | http://localhost:8002/sse | — |

> **No default dashboard credentials.** The database starts empty. Register your first account via `POST /api/v1/auth/register` (Swagger or curl above). All registered users default to the `QA_ENGINEER` role. To promote to `ADMIN`:
> ```bash
> make shell-db
> # inside psql:
> UPDATE users SET role = 'ADMIN' WHERE username = 'admin';
> ```

---

## Project Structure

```
qainsight-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI app factory + router registration
│   │   ├── core/
│   │   │   ├── config.py        ← All settings (Pydantic v2 BaseSettings)
│   │   │   └── security.py      ← JWT helpers (create_access_token, verify_token)
│   │   ├── db/
│   │   │   ├── postgres.py      ← Async SQLAlchemy engine + session
│   │   │   ├── mongo.py         ← Motor MongoDB client
│   │   │   ├── minio.py         ← aioboto3 S3 helpers
│   │   │   └── storage.py       ← STORAGE_BACKEND router (minio | local)
│   │   ├── models/
│   │   │   ├── postgres.py      ← SQLAlchemy ORM models (all tables)
│   │   │   └── schemas.py       ← Pydantic v2 request/response schemas
│   │   ├── routers/             ← One module per API feature area
│   │   │   ├── webhooks.py      ← POST /webhooks/minio
│   │   │   ├── projects.py      ← CRUD /api/v1/projects
│   │   │   ├── runs.py          ← GET /api/v1/runs + test cases
│   │   │   ├── metrics.py       ← GET /api/v1/metrics/*
│   │   │   ├── analytics.py     ← GET /api/v1/analytics/* (flaky, categories, coverage…)
│   │   │   ├── search.py        ← GET /api/v1/search
│   │   │   ├── analyze.py       ← POST /api/v1/analyze (AI triage)
│   │   │   ├── auth.py          ← POST /api/v1/auth/register, /login
│   │   │   ├── live.py          ← WS /ws/live/{project_id}
│   │   │   └── integrations.py  ← POST /api/v1/integrations/jira
│   │   ├── services/            ← Business logic (no HTTP concerns)
│   │   │   ├── agent.py         ← LangChain ReAct agent runner (with timeout)
│   │   │   ├── ingestion.py     ← Allure/TestNG → PostgreSQL + MongoDB
│   │   │   ├── allure_parser.py ← Parse Allure JSON result files
│   │   │   ├── testng_parser.py ← Parse TestNG surefire XML
│   │   │   ├── llm_factory.py   ← Provider-agnostic LLM factory
│   │   │   ├── jira_client.py   ← Jira REST API v3 + ADF builder
│   │   │   ├── metrics_service.py ← Dashboard KPI aggregations
│   │   │   └── ocp_client.py    ← OpenShift pod metadata queries
│   │   ├── agents/              ← LangGraph multi-agent pipeline
│   │   │   ├── workflow.py      ← _build_offline_graph() + _build_deep_graph() + run_*_pipeline()
│   │   │   ├── state.py         ← WorkflowState typed dict (shared by both pipelines)
│   │   │   ├── base.py          ← BaseAgent (stage tracking, broadcast helpers)
│   │   │   ├── cluster_agent.py ← stage_name="failure_clustering"; semantic grouping
│   │   │   ├── log_intelligence_agent.py ← specialist; called by cluster/flaky agents
│   │   │   ├── contract_agent.py         ← specialist; API schema drift per cluster
│   │   │   ├── flaky_sentinel_agent.py   ← stage_name="flaky_sentinel"; lifecycle investigation
│   │   │   ├── test_health_agent.py      ← stage_name="test_health"; anti-pattern scan
│   │   │   └── release_risk_agent.py     ← stage_name="release_risk"; GO/NO_GO LLM decision
│   │   ├── tools/               ← LangChain agent tool definitions (11 tools)
│   │   │   ├── fetch_stacktrace.py       ← Standard pipeline tools (5)
│   │   │   ├── fetch_rest_payload.py
│   │   │   ├── query_splunk.py
│   │   │   ├── check_flakiness.py
│   │   │   ├── analyze_ocp.py
│   │   │   ├── embed_and_cluster.py      ← Deep pipeline tools (6)
│   │   │   ├── reconstruct_trace.py
│   │   │   ├── detect_log_anomaly.py
│   │   │   ├── validate_api_contract.py
│   │   │   ├── fetch_build_changes.py
│   │   │   └── fetch_app_metrics.py
│   │   ├── routers/
│   │   │   ├── deep_investigation.py    ← POST /deep-investigate, GET /clusters, GET /findings
│   │   │   └── release_readiness.py     ← GET /release-readiness, POST /override
│   │   └── worker/
│   │       ├── celery_app.py    ← Celery configuration + beat schedule
│   │       └── tasks.py         ← Background task definitions
│   ├── migrations/
│   │   ├── env.py               ← Alembic async environment
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       ├── 0002_*.py … 0005_*.py
│   │       └── 0006_deep_investigation.py  ← failure_clusters, deep_findings, release_decisions, contract_violations
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
│   │   ├── App.tsx              ← Router with all lazy-loaded routes (incl. /deep-investigate, /release-gate)
│   │   ├── pages/               ← One file per route
│   │   │   ├── OverviewPage.tsx      ← Executive Dashboard
│   │   │   ├── RunsPage.tsx          ← Jenkins build list
│   │   │   ├── RunDetailPage.tsx     ← Test cases within a run
│   │   │   ├── TestCasePage.tsx      ← Split-pane detail + AI panel
│   │   │   ├── SearchPage.tsx        ← Full-text search
│   │   │   ├── CoveragePage.tsx      ← Suite coverage breakdown
│   │   │   ├── FailureAnalysisPage.tsx ← Flaky leaderboard + category pie
│   │   │   ├── TrendsPage.tsx        ← Period-based KPI trend charts
│   │   │   ├── DefectsPage.tsx       ← Paginated defects + Jira links
│   │   │   ├── ProjectsPage.tsx      ← Project management
│   │   │   ├── AgentStatusPage.tsx   ← Live pipeline stage monitor (9 stages for deep pipeline)
│   │   │   ├── DeepInvestigationPage.tsx ← Cluster list + finding detail panel; trigger button
│   │   │   ├── ReleaseGatePage.tsx   ← GO/NO_GO banner, risk gauge, QA lead override form
│   │   │   └── SettingsPage.tsx      ← Configuration overview
│   │   ├── components/
│   │   │   ├── ui/              ← Generic reusable components
│   │   │   ├── charts/          ← Recharts wrappers (TrendChart, PassRateGauge…)
│   │   │   ├── layout/          ← App shell (AppLayout, Sidebar, TopBar)
│   │   │   │   └── Sidebar.tsx  ← AI_NAV includes Deep Analysis (Layers) + Release Gate (Shield)
│   │   │   └── ai/              ← AI-specific (AIAnalysisPanel, LogViewer)
│   │   ├── services/            ← Axios API client modules
│   │   │   ├── api.ts           ← Base axios instance (VITE_API_BASE_URL)
│   │   │   ├── analyticsService.ts
│   │   │   ├── metricsService.ts
│   │   │   ├── runsService.ts
│   │   │   ├── aiService.ts
│   │   │   ├── projectsService.ts
│   │   │   ├── searchService.ts
│   │   │   └── deepInvestigationService.ts  ← triggerDeep, getClusters, getFindings, getReleaseDecision, overrideRelease
│   │   ├── hooks/               ← SWR data-fetching hooks
│   │   │   ├── useMetrics.ts    ← useFlakyTests, useFailureCategories, …
│   │   │   ├── useRuns.ts
│   │   │   └── useDeepInvestigation.ts  ← useFailureClusters, useDeepFindings, useReleaseDecision
│   │   ├── store/
│   │   │   └── projectStore.ts  ← Zustand: active project + project list
│   │   └── utils/
│   │       └── formatters.ts    ← Date, duration, status helpers
│   └── package.json
│
├── mcp/                         ← MCP Server (AI assistant integration)
│   ├── server.py                ← Entry point — FastMCP, registers all tools/resources/prompts
│   ├── config.py                ← Settings via QAINSIGHT_* env vars
│   ├── client.py                ← httpx async client with JWT auto-auth + 401 refresh
│   ├── tools/
│   │   ├── auth.py              ← login, health_check
│   │   ├── projects.py          ← list_projects, get_project, create_project
│   │   ├── runs.py              ← list_test_runs, get_run_details, list_test_cases, get_test_case
│   │   ├── metrics.py           ← get_dashboard_metrics, get_test_trends
│   │   ├── analytics.py         ← get_flaky_tests, get_failure_categories, get_top_failing_tests,
│   │   │                           get_coverage_report, get_defects, get_ai_analysis_summary
│   │   ├── analysis.py          ← trigger_ai_analysis, search_tests
│   │   └── release.py           ← check_release_readiness
│   ├── resources/
│   │   └── registry.py          ← 10 resources (qainsight://projects, runs, tests, defects…)
│   ├── prompts/
│   │   └── templates.py         ← 6 workflows (investigate_failure, release_readiness_report…)
│   ├── Dockerfile               ← Container for SSE transport (port 8002)
│   ├── requirements.txt         ← mcp, httpx, pydantic-settings
│   └── .env.example
│
├── k8s/
│   ├── base/                    ← Kustomize base (all environments)
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml         ← TEMPLATE ONLY — never commit real values
│   │   ├── rbac.yaml
│   │   ├── backend-deployment.yaml  (+ HPA)
│   │   ├── worker-deployments.yaml  ← Celery worker + beat workloads
│   │   ├── frontend-deployment.yaml
│   │   ├── mcp-deployment.yaml      ← MCP server (SSE transport)
│   │   ├── ollama-deployment.yaml   (+ PVC)
│   │   ├── services.yaml
│   │   └── ingress.yaml
│   └── overlays/
│       ├── dev/kustomization.yaml
│       ├── staging/kustomization.yaml
│       ├── prod/kustomization.yaml
│       └── openshift/kustomization.yaml
│
├── infra/cloudrun/              ← Cloud Run deployment assets
│   ├── backend.env.example
│   ├── frontend.env.example
│   ├── mcp.env.example          ← MCP server env template for Cloud Run
│   ├── cloudbuild.backend.yaml
│   ├── cloudbuild.frontend.yaml
│   └── cloudbuild.mcp.yaml      ← Cloud Build for MCP image
│
├── .github/workflows/
│   └── ci.yml                   ← Test → Build → Push → Deploy pipeline (incl. MCP lint job)
│
├── scripts/
│   ├── init-db.sql              ← PostgreSQL extension setup
│   ├── simulate-upload.sh       ← End-to-end ingestion test
│   └── setup-minio.sh           ← One-time MinIO configuration
│
├── docker-compose.yml           ← Full local development stack (incl. mcp service)
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
9. **Expose via MCP:** add a new tool in `mcp/tools/<group>.py` and register in `mcp/server.py`

### Adding a new MCP tool

1. Choose the appropriate module in `mcp/tools/` (or create a new one)
2. Add a function decorated with `@mcp.tool()` inside the `register(mcp)` function
3. Call the backend via `await api.get(...)` or `await api.post(...)`
4. Register the module in `mcp/server.py`: `from tools import <module>` + `<module>.register(mcp)`
5. Test manually: `make mcp-start`, then ask the AI Assistant to call the tool

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

### Running the MCP server locally

```bash
cd mcp
pip install -r requirements.txt
cp .env.example .env    # fill in QAINSIGHT_USERNAME and QAINSIGHT_PASSWORD
python server.py --transport stdio   # for MCP Clients
python server.py --transport sse     # for SSE clients on :8002
```

Or via Make:
```bash
make mcp-install
make mcp-start     # stdio
make mcp-sse       # SSE on port 8002
```

### Kubernetes async rollout helpers

```bash
# Wait for worker + beat rollout by environment
make k8s-rollout-async-dev
make k8s-rollout-async-staging
make k8s-rollout-async-prod

# Check async deployment + HPA status in a specific namespace
make k8s-status-async K8S_NAMESPACE=qainsight-staging
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

Then restart: `docker compose restart backend worker`

### Iterative development phases

| Phase | Feature area | Key files to work on |
|-------|-------------|---------------------|
| P1 | Infrastructure | `docker-compose.yml`, `backend/app/main.py`, DB setup |
| P2 | Ingestion | `services/ingestion.py`, `services/allure_parser.py`, `routers/webhooks.py` |
| P3 | Core dashboards | `pages/OverviewPage.tsx`, `pages/RunsPage.tsx`, `pages/TestCasePage.tsx` |
| P4 | Analytics | `pages/CoveragePage.tsx`, `pages/FailureAnalysisPage.tsx`, `pages/TrendsPage.tsx` |
| P5 | AI triage | `services/agent.py`, `tools/`, `components/ai/AIAnalysisPanel.tsx` |
| P6 | Quality Gates | New `routers/quality_gates.py` + frontend |
| P7 | MCP Server | `mcp/tools/`, `mcp/resources/`, `mcp/prompts/`, `mcp/server.py` |
| P8 | Production | `k8s/`, `.github/workflows/ci.yml` |
| P9 | Performance & scalability | Connection pools, parallel ingestion, WebSocket limits |
| P10 | LangGraph multi-agent pipeline | `agents/workflow.py`, `agents/state.py`, `agents/base.py` |
| P11 | Redis Streams + live reporting | `streams/`, circuit breaker, DLQ |
| P12 | Continuous fine-tuning | `services/training/`, `worker/training_tasks.py`, model registry |
| P13 | Deep Investigation + Release Gate | `agents/cluster_agent.py` through `release_risk_agent.py`, new tools (6), `routers/deep_investigation.py`, `routers/release_readiness.py`, `migrations/0006_deep_investigation.py`, `pages/DeepInvestigationPage.tsx`, `pages/ReleaseGatePage.tsx` |
