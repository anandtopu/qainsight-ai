# QA Insight AI Wiki

Welcome to the project wiki for **QA Insight AI**.

QA Insight AI is a 360-degree testing intelligence platform that ingests test results from multiple frameworks, correlates failures using AI, and helps teams move faster from failed test to root cause.

## What You Get

- FastAPI backend for ingestion, analytics, and AI orchestration
- React dashboard for trends, flaky tests, defects, and release signals
- LangChain ReAct agent with 5 investigation tools (stack traces, payloads, Splunk logs, flakiness, OCP events)
- **Deep Investigation Agent Network** — on-demand 9-stage LangGraph pipeline: semantic failure clustering, distributed trace reconstruction, log anomaly detection, API contract validation, flaky lifecycle analysis, test health scoring, and a GO/NO_GO release gate
- **Release Gate** — AI-backed release recommendation (GO / NO_GO / CONDITIONAL_GO) with risk score, blocking issues list, and QA Lead override with full audit trail
- Local LLM mode via Ollama for air-gapped/offline deployments
- Continuous fine-tuning pipeline — self-improving models trained on your own verified failure data
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
      ↓
┌── Standard Pipeline (LangGraph) ──────────────────────────────────────┐
│   ingestion → anomaly → root_cause → summary → triage → END           │
└────────────────────────────────────────────────────────────────────────┘
┌── Deep Investigation Pipeline (LangGraph) ─────────────────────────────┐
│   ingestion → (parallel) anomaly + root_cause + failure_clustering     │
│            → summary → triage → flaky_sentinel → test_health           │
│            → release_risk (GO/NO_GO/CONDITIONAL_GO) → END              │
└────────────────────────────────────────────────────────────────────────┘
```

### Deep Investigation Agents

| Agent | Role |
|-------|------|
| `ClusterAgent` | Semantically groups similar failures — reduces O(n) LLM calls to O(k) |
| `LogIntelligenceAgent` | Reconstructs distributed Splunk traces; detects log rate anomalies |
| `ContractAgent` | Validates REST API schema against historical MongoDB baselines |
| `FlakySentinelAgent` | Traces flakiness onset build; correlates GitHub commits; recommends quarantine |
| `TestHealthAgent` | Scans automation code for anti-patterns; computes 0–100 health score |
| `ReleaseRiskAgent` | LLM-backed GO / NO_GO / CONDITIONAL_GO with heuristic fast-path |

## Repository Layout

- `backend/app/agents/` — LangGraph multi-agent workflow (standard + deep pipelines; 6 deep agents)
- `backend/app/tools/` — 11 LangChain tools (5 standard + 6 deep investigation)
- `backend/app/routers/` — REST API route handlers (incl. `deep_investigation.py`, `release_readiness.py`)
- `backend/migrations/versions/0006_deep_investigation.py` — failure_clusters, deep_findings, release_decisions, contract_violations tables
- `frontend/src/pages/` — React pages (incl. `DeepInvestigationPage.tsx`, `ReleaseGatePage.tsx`)
- `frontend/src/services/deepInvestigationService.ts` — deep investigate + release readiness API client
- `mcp/` — MCP server (tools, resources, prompts)
- `k8s/` — Kustomize base and overlays
- `docs/` — engineering and deployment docs

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

- `README.md` — full feature reference, architecture diagram, environment variables, Deep Investigation section
- `docs/DEVELOPMENT.md` — developer workflow, project structure, iterative phases (P1–P13)
- `docs/cloud-run-cloud-sql.md` — managed GCP deployment path
- `docs/JENKINS_PIPELINE.md` — Jenkins CI/CD pipeline usage
- `CLAUDE.md` — codebase conventions and coding rules

