# QA Insight AI 🔭

> **360° AI-Powered Software Testing Intelligence Platform**
> Local-LLM capable · Multi-framework · OpenShift/Kubernetes native · MCP-enabled

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![React 18](https://img.shields.io/badge/React-18-61DAFB)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)](https://fastapi.tiangolo.com)
[![MCP](https://img.shields.io/badge/MCP-Server-blueviolet)](https://modelcontextprotocol.io)

## Overview

QA Insight AI bridges the gap between automated test execution and defect resolution. It ingests test results from 50+ frameworks, applies a LangChain ReAct agent (running locally via Ollama — **no internet required**) to correlate failures across stack traces, Splunk logs, and Kubernetes pod events, and pushes structured root-cause summaries to Jira in one click.

It also ships a first-class **MCP (Model Context Protocol) server** so AI assistants (AI Desktop Clients, IDE plugins, CI pipelines) can query test quality, investigate failures, and gate releases through natural-language conversations — no browser required.

## Key Features

| Domain | Capability |
|--------|-----------|
| **Ingestion** | TestNG, JUnit, Allure, Cucumber, pytest, Robot Framework, JUnit XML (universal) |
| **AI Triage** | LangChain ReAct agent · 5 investigation tools · Ollama/OpenAI/Gemini |
| **Offline AI** | Fully air-gapped with Ollama (qwen2.5, llama3, mistral) |
| **Continuous Learning** | Self-improving models — fine-tuned on your own verified failure data, no external labelling required |
| **Live Reporting** | Real-time WebSocket dashboard during test execution · Redis Streams event pipeline |
| **Fault Tolerance** | Consumer group ACK model · XAUTOCLAIM stale reclaim · Dead-letter queue · LLM circuit breaker |
| **Dashboards** | Pass/fail trends, coverage heatmaps, flaky leaderboard, defect burn-down |
| **Quality Gates** | Automated GO/NO-GO feedback to Jenkins/GitHub Actions |
| **Async Processing** | Celery priority queues (`critical` → `ingestion` → `ai_analysis` → `default`) + beat scheduler |
| **Security** | JWT-based authentication with role-based access control (RBAC) |
| **MCP Server** | 20 tools · 10 resources · 6 prompt workflows for AI assistant integration |
| **Search** | Full-text + semantic RAG search across all test history |
| **Integrations** | Jira, Splunk, OpenShift API, Slack, Teams, GitHub Issues |

## Architecture

```
[Tests/CI Upload] -> [FastAPI Backend/API]
                          |
                          +-> [PostgreSQL]   structured results, AI analyses, feedback, model versions
                          +-> [MongoDB]      raw logs, Allure JSON, audit trails, run summaries
                          +-> [MinIO/S3]     test artifacts, training JSONL exports
                          +-> [Redis]        broker, live run state, model registry, circuit breaker
                          |
                          +-> [AI Agent (LangChain ReAct)] -> [Ollama or Cloud LLM]
                          +-> [Fast Classifier]             -> [Fine-tuned model (registry)]
                          |
                          +-> [Redis Streams] -> [Live Event Consumer] -> [WebSocket broadcast]

[Redis] <-> [Celery Worker]   ingestion · ai_analysis · critical · default queues
[Redis] <-> [Celery Beat]     weekly export · daily trigger check · coverage snapshots

[Continuous Learning Flywheel]
  Resolved Jira tickets → AIFeedback → TrainingDataExporter → MinIO JSONL
  → FineTuningPipeline → ModelEvaluator → ModelRegistry (Redis hot-swap)
  → FastClassifier / ReAct agent uses promoted model automatically

[Frontend SPA] <-> [Backend API]
[MCP Server :8002] <-> [Backend API]

Deployment targets:
- Local Docker Compose (full stack) / docker-compose.dev-lite.yml (~4 GB RAM)
- Kubernetes (dev/staging/prod overlays via Kustomize)
- OpenShift overlay (Route-based exposure)
- Cloud deployment paths (GCP Cloud Run/Cloud SQL and multi-cloud Kubernetes)
```

## System Architecture

The following diagram reflects the current runtime architecture, async processing, and deployment targets:

```mermaid
graph TD
    subgraph Client_Layer [Client and Ingestion]
        UI[React SPA Frontend]
        SDK[Client SDKs: Java, Python, JS, .NET]
        CICD[CI/CD: Jenkins, GitHub Actions]
        MCP_CLIENT[AI Clients: MCP Client / IDE / CI]
    end

    subgraph MCP_Layer [MCP Integration]
        MCP[MCP Server port 8002]
        MCP_TOOLS[20 Tools]
        MCP_RES[10 Resources]
        MCP_PROMPTS[6 Prompt Workflows]
    end

    subgraph API_Layer [API and Application]
        FastAPI[FastAPI Backend Service]
        REST[REST API & Webhook SDK]
        SSE[SSE / WebSocket Streaming]
        Auth[JWT Authentication & Security Middleware]
        Analytics[Analytics Engine]
        Notify[Notification Services - Slack, Teams, Email]
    end

    subgraph AI_Intelligence_Layer [AI and Intelligence]
        Agent[LangChain ReAct Agent]
        Classifier[Fast Classifier single LLM call]
        Factory[LLM Factory + Model Registry]
        Ollama[Ollama Service / Local LLM]
        CloudLLM[Cloud API: OpenAI / Gemini]
        RAG[Semantic Search / Embeddings]
        CircuitBreaker[LLM Circuit Breaker]
    end

    subgraph Continuous_Learning [Continuous Fine-Tuning]
        Feedback[AIFeedback Table]
        JiraHook[Jira Resolution Webhook]
        Exporter[TrainingDataExporter weekly]
        FineTuner[FineTuningPipeline OpenAI / Ollama]
        Evaluator[ModelEvaluator holdout A/B]
        Registry[ModelRegistry Redis hot-swap]
        TrainingData[(MinIO: training-data JSONL)]
    end

    subgraph Async_Processing_Layer [Async Processing]
        Redis[Redis Message Broker]
        Worker[Celery Worker]
        Beat[Celery Beat Scheduler]
        Gates[Quality Gate Engine]
    end

    subgraph Data_Persistence_Layer [Data Persistence]
        PG[(PostgreSQL - Relational)]
        Mongo[(MongoDB - Unstructured)]
        MinIO[(MinIO - Object Storage)]
        Chroma[(ChromaDB - Vector Store)]
    end

    subgraph External_Integrations [External Integrations]
        Jira[Bug Tracking: Jira]
        Slack[Notifications: Slack / Teams]
    end

    subgraph Deployment_Targets [Deployment Targets]
        Compose[Docker Compose local and dev]
        K8s[Kubernetes overlays dev staging prod]
        OCP[OpenShift overlay and Routes]
        Cloud[GCP Cloud Run and Cloud SQL path]
    end

    %% MCP Client connections
    MCP_CLIENT -->|MCP Protocol stdio/SSE| MCP
    MCP --> MCP_TOOLS
    MCP --> MCP_RES
    MCP --> MCP_PROMPTS
    MCP_TOOLS -->|HTTP/REST + JWT| FastAPI
    MCP_RES -->|HTTP/REST + JWT| FastAPI

    %% Client to API Connections
    UI -->|HTTP/REST| FastAPI
    UI -->|Real-Time Data| SSE
    UI -->|Auth & Token| Auth
    UI -->|Trend Data| Analytics
    SDK -->|Test Results| REST
    CICD -->|Trigger/Webhooks| REST
    CICD -->|Quality Gate check via MCP| MCP
    REST --> FastAPI
    SSE --- FastAPI
    Auth --- FastAPI
    Analytics --- FastAPI

    %% API to Storage Connections
    FastAPI -->|Structured Metrics| PG
    FastAPI -->|Raw Logs| Mongo
    FastAPI -->|Artifacts| MinIO
    FastAPI -->|Enqueue Jobs| Redis
    FastAPI -->|Notification Events| Notify

    %% Async Worker Connections
    Redis -->|Consume Jobs| Worker
    Redis -->|Schedules| Beat
    Worker -->|Update Status| PG
    Worker -->|Evaluate Rules| Gates
    Beat -->|Periodic Tasks| Worker
    Gates -->|GO/NO-GO Webhooks| CICD
    Gates -->|Alerts| Slack

    %% AI Connections
    FastAPI -->|Trigger AI Triage| Classifier
    Classifier -->|Fast path hit| Factory
    Classifier -->|Low confidence fallback| Agent
    FastAPI -->|Trigger AI Triage| Agent
    Worker -->|Tier 3 Background Triage| Agent
    Worker -->|Tier 2 Similarity Matching| RAG
    RAG <-->|Query Vectors| Chroma
    Agent -->|Route Provider| Factory
    Classifier -->|Route Provider| Factory
    Factory -->|Check active fine-tuned model| Registry
    Factory -->|Air-Gapped Inference| Ollama
    Factory -->|Cloud Inference| CloudLLM
    Agent -->|Guard LLM calls| CircuitBreaker
    Worker -->|Guard LLM calls| CircuitBreaker

    %% External Tool Invocations
    Agent -->|Auto-Create Defects| Jira

    %% Continuous Learning Connections
    Jira -->|Resolution webhook| JiraHook
    JiraHook -->|Implicit feedback| Feedback
    FastAPI -->|Explicit rating| Feedback
    Beat -->|Weekly export task| Exporter
    Exporter -->|Read verified examples| PG
    Exporter -->|Read ReAct traces| Mongo
    Exporter -->|Write JSONL| TrainingData
    TrainingData -->|Training file| FineTuner
    FineTuner -->|OpenAI fine-tuning API| CloudLLM
    FineTuner -->|ollama create| Ollama
    FineTuner -->|Candidate model| Evaluator
    Evaluator -->|Read holdout JSONL| TrainingData
    Evaluator -->|Approve/reject| Registry
    Registry -->|Active model name| Factory

    FastAPI --- Compose
    FastAPI --- K8s
    FastAPI --- OCP
    FastAPI --- Cloud
```

## Quick Start (Local Development)

### Prerequisites
- Docker Desktop 4.x+
- Node.js 20 LTS
- Python 3.11+

### 1. Clone & Configure
```bash
git clone https://github.com/yourorg/qainsight-ai.git
cd qainsight-ai
cp .env.example .env
# Edit .env — see Environment Variables section
```

Windows PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

### 2. Start the Stack
```bash
docker compose up -d --build
```

### 3. Run Migrations
```bash
docker compose exec backend alembic upgrade head
```

### 4. Pull Local LLM (Ollama)
```bash
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull nomic-embed-text
```

### 5. Access Services
| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | Register via API Docs first |
| API Docs | http://localhost:8000/docs | — |
| MinIO Console | http://localhost:9001 | admin / password123 |
| Flower (Celery) | http://localhost:5555 | — |
| MCP SSE Server | http://localhost:8002/sse | — |

### 6. Connect the MCP Server (AI Assistant)

Install dependencies and configure your MCP client:

```bash
make mcp-install
```

Add to your MCP client configuration (e.g., Claude Desktop, Cursor, etc.):

```json
{
  "mcpServers": {
    "qainsight": {
      "command": "python",
      "args": ["/absolute/path/to/qainsight-ai/mcp/server.py"],
      "env": {
        "QAINSIGHT_API_URL": "http://localhost:8000",
        "QAINSIGHT_USERNAME": "your-user",
        "QAINSIGHT_PASSWORD": "your-pass"
      }
    }
  }
}
```

Then ask the AI Assistant: *"List all QA projects"* or *"Check release readiness for project-alpha"*.

## Project Structure

```
qainsight-ai/
├── backend/                    # FastAPI Python backend
│   ├── app/
│   │   ├── main.py             # Application entry point + lifespan (live consumer)
│   │   ├── core/               # Config, security, dependencies
│   │   ├── routers/            # API route handlers
│   │   │   └── feedback.py     # Feedback + training management endpoints
│   │   ├── services/           # Business logic
│   │   │   ├── model_registry.py        # Redis-backed hot-swap model registry
│   │   │   └── training/                # Continuous fine-tuning pipeline
│   │   │       ├── exporter.py          # Training data export (all 3 tracks)
│   │   │       ├── classifier.py        # Fast single-call failure classifier
│   │   │       ├── finetuner.py         # Provider-specific job submission
│   │   │       └── evaluator.py         # Holdout A/B evaluation gate
│   │   ├── agents/             # LangGraph multi-agent workflow
│   │   ├── streams/            # Redis Streams infrastructure
│   │   │   ├── __init__.py              # Stream/group/key constants
│   │   │   ├── producer.py              # XADD publishers
│   │   │   ├── live_consumer.py         # Asyncio stream consumer
│   │   │   ├── live_run_state.py        # Redis Hash live run state
│   │   │   └── circuit_breaker.py       # CLOSED/OPEN/HALF_OPEN LLM guard
│   │   ├── tools/              # LangChain agent tools (5 tools)
│   │   ├── models/             # SQLAlchemy ORM + Pydantic schemas
│   │   ├── db/                 # Database connections
│   │   └── worker/             # Celery background tasks
│   │       ├── tasks.py                 # Ingestion + analysis + pipeline tasks
│   │       └── training_tasks.py        # Export · trigger-check · fine-tune pipeline
│   ├── migrations/             # Alembic migrations (0001–0005)
│   ├── tests/                  # pytest test suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React + Vite SPA
│   ├── src/
│   │   ├── pages/              # Route-level page components (incl. LoginPage)
│   │   ├── components/         # Reusable UI components & ProtectedRoute
│   │   ├── services/           # API client layer with auth interceptors
│   │   ├── hooks/              # Custom React hooks (SWR)
│   │   ├── store/              # Zustand state management (authStore)
│   │   └── utils/              # Helpers and formatters
│   ├── package.json
│   └── Dockerfile
├── mcp/                        # MCP Server — AI assistant integration
│   ├── server.py               # Entry point (stdio + SSE transport)
│   ├── config.py               # Settings (QAINSIGHT_API_URL, credentials)
│   ├── client.py               # httpx async client with JWT auto-auth
│   ├── tools/                  # 20 callable tools
│   ├── resources/              # 10 readable resources (qainsight:// URIs)
│   ├── prompts/                # 6 investigation workflow templates
│   ├── Dockerfile
│   └── requirements.txt
├── k8s/                        # Kubernetes/OpenShift manifests
│   ├── base/                   # Kustomize base resources
│   └── overlays/               # Environment-specific patches (dev/staging/prod)
├── infra/cloudrun/             # Cloud Run + Cloud SQL deployment assets
├── .github/workflows/ci.yml    # GitHub Actions CI/CD pipeline
├── docker-compose.yml          # Local development stack
├── .env.example                # Environment variable template
├── Makefile                    # Developer convenience commands
└── scripts/                    # Setup and utility scripts
```

## Development

```bash
# Start all services
make dev

# Alternative (if make is unavailable on your shell)
docker compose up -d --build

# Run backend tests
make test-backend

# Run frontend tests
make test-frontend

# Apply DB migrations
make migrate

# Lint all code
make lint

# Build production images
make build

# MCP server (local — for AI Assistants)
make mcp-install && make mcp-start

# MCP server (SSE — for CI/web clients)
make mcp-sse

# Kubernetes async rollout checks
make k8s-rollout-async-dev
make k8s-rollout-async-staging
make k8s-rollout-async-prod
```

## Deployment Documentation

- `installation.md` - installation + deployment entry points (local, GCP VM, Cloud Run)
- `deployment_and_testing_strategy.md` - validation and release strategy by environment
- `deploymentsteps.md` - detailed GCP VM operational runbook
- `docs/cloud-run-cloud-sql.md` - managed GCP deployment path
- `docs/JENKINS_PIPELINE.md` - Jenkins CI/CD pipeline usage

## MCP Server

QA Insight AI ships a full MCP server under `mcp/` that gives AI assistants direct access to your test quality data.

### Available Tools (20)

| Group | Tools |
|-------|-------|
| Auth | `login`, `health_check` |
| Projects | `list_projects`, `get_project`, `create_project` |
| Runs | `list_test_runs`, `get_run_details`, `list_test_cases`, `get_test_case` |
| Metrics | `get_dashboard_metrics`, `get_test_trends` |
| Analytics | `get_flaky_tests`, `get_failure_categories`, `get_top_failing_tests`, `get_coverage_report`, `get_defects`, `get_ai_analysis_summary` |
| Analysis | `trigger_ai_analysis`, `search_tests` |
| Release | `check_release_readiness` |

### Available Prompts (6)

| Prompt | Workflow |
|--------|---------|
| `investigate_failure` | Full root-cause investigation for a failing test |
| `release_readiness_report` | Executive go/no-go assessment |
| `weekly_quality_digest` | Weekly summary for team sharing |
| `flakiness_investigation` | Deep-dive with remediation plan |
| `defect_triage_session` | Structured defect prioritisation |
| `suite_health_check` | Health report for a specific test suite |

### Example Conversations

```
You: "What's our pass rate this week for project-alpha?"
You: "Why is CheckoutTest failing? Investigate it."
You: "Can we release v2.4.0 today?"
You: "Which tests are most flaky this month?"
You: "Generate the weekly quality digest for project-alpha"
```

## Iterative Development Plan

| Phase | Focus | Weeks |
|-------|-------|-------|
| **Phase 1** | Infrastructure foundation (DB, MinIO, skeleton APIs) | 1–2 |
| **Phase 2** | Java ingestion pipeline (Allure JSON + TestNG XML) | 3–4 |
| **Phase 3** | Core dashboards (Executive, Run Explorer, Log Viewer) | 5–6 |
| **Phase 4** | Coverage, trends, failure analysis, search | 7–8 |
| **Phase 5** | AI triage agent (Ollama + LangChain ReAct) | 9–10 |
| **Phase 6** | Quality Gates, manual test management, BDD | 11–12 |
| **Phase 7** | MCP Server — AI assistant integration layer | 13 |
| **Phase 8** | Production deployment (OpenShift + CI/CD) | 14–15 |
| **Phase 9** | Performance & scalability (connection pools, parallel ingestion, WS limits) | 16 |
| **Phase 10** | Context engineering + LangGraph multi-agent pipeline | 17 |
| **Phase 11** | Redis Streams event pipeline · live test reporting · circuit breaker · DLQ | 18 |
| **Phase 12** | Continuous fine-tuning pipeline (3 tracks, Jira webhook, model registry) | 19–20 |

## Continuous Fine-Tuning

QA Insight AI includes a self-improving model pipeline that learns from every resolved defect, every engineer correction, and every Jira ticket outcome — with no external labelling or manual data preparation required.

### How it works

```
Test failures → AI analysis → Jira ticket created
                                      ↓
                             Engineer resolves ticket
                                      ↓
                         Jira webhook → AIFeedback record
                                      ↓
                    Weekly export → MinIO JSONL (train + holdout)
                                      ↓
                    FineTuningPipeline → OpenAI API or ollama create
                                      ↓
                    ModelEvaluator → holdout A/B: must beat baseline by ≥ 2%
                                      ↓
                    ModelRegistry → Redis hot-swap (no restart needed)
                                      ↓
                FastClassifier / ReAct agent uses promoted model automatically
```

### Three training tracks

| Track | Model role | Fast-path latency | Trigger threshold |
|-------|-----------|-------------------|-------------------|
| **classifier** | Single-call failure category prediction (skips full ReAct agent when confidence ≥ 85%) | ~50–200 ms | 500 verified examples |
| **reasoning** | Full ReAct agent — fine-tuned on verified tool-call chains | 10–30 s (same as base, but more accurate) | 2 000 verified traces |
| **embedding** | Domain semantic search — contrastive failure pairs for ChromaDB | — | 1 000 labeled pairs |

### Training signal sources

The system accumulates ground-truth labels passively from three sources:

| Source | Signal type | How captured |
|--------|------------|-------------|
| Jira ticket **resolved** | Positive — AI was correct | `POST /api/v1/feedback/jira-webhook` (configure in Jira) |
| Jira ticket **closed as invalid** | Negative — AI was wrong | Same webhook, `resolution = "Won't Fix"` |
| Engineer rates analysis **correct** | Strong positive | `POST /api/v1/feedback/{analysis_id}` |
| Engineer rates analysis **incorrect** + provides corrected category | Correction | Same endpoint with `corrected_category` field |
| Engineer edits `failure_category` in UI | Category correction | Stored as `source=category_correction` |

### Enabling fine-tuning

Fine-tuning is **disabled by default** (`FINETUNE_ENABLED=false`). Enable it once enough feedback has accumulated:

```bash
# .env
FINETUNE_ENABLED=true
FINETUNE_CLASSIFIER_MIN_EXAMPLES=500    # trigger Track 1
FINETUNE_REASONING_MIN_EXAMPLES=2000   # trigger Track 2
FINETUNE_EMBED_MIN_PAIRS=1000          # trigger Track 3
FINETUNE_INCREMENTAL_TRIGGER=200       # re-trigger after every 200 new verified examples
FINETUNE_EVAL_HOLDOUT=0.10             # 10% of examples held out for A/B evaluation
FINETUNE_MIN_ACCURACY_GAIN=0.02        # candidate must beat current model by ≥ 2%
FINETUNE_EXPORT_BUCKET=training-data   # MinIO bucket for JSONL files
CLASSIFIER_CONFIDENCE_THRESHOLD=85    # fast-path confidence floor (0–100)
```

For **OpenAI fine-tuning** (cloud):
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
FINETUNE_OPENAI_SUFFIX=qainsight       # fine-tune job name suffix
```

For **Ollama fine-tuning** (local/air-gapped):
```bash
LLM_PROVIDER=ollama
# Pre-requisite: train with Unsloth/llama.cpp, export GGUF, upload to MinIO:
#   training-data/classifier/YYYY-MM-DD.gguf
# The pipeline will run: ollama create <model_name> -f Modelfile
```

### Configuring the Jira webhook (recommended)

The most powerful signal source is passive — no engineer action required.

1. In Jira, go to **Settings → System → WebHooks → Create a WebHook**
2. Set URL: `https://your-backend/api/v1/feedback/jira-webhook`
3. Select events: **Issue Updated**
4. Filter: `project = QA AND status changed to (Done, Resolved, Closed)`

From that point, every resolved Jira ticket automatically becomes a training example.

### API reference

| Endpoint | Role | Auth |
|----------|------|------|
| `POST /api/v1/feedback/{analysis_id}` | Rate an AI analysis (correct / incorrect / partially_correct) | Any user |
| `PUT  /api/v1/feedback/{analysis_id}` | Update a previous rating | Same user |
| `GET  /api/v1/feedback/stats` | Feedback counts by rating | Any user |
| `POST /api/v1/feedback/jira-webhook` | Jira resolution webhook receiver | No auth (webhook secret recommended) |
| `GET  /api/v1/training/status` | Registry status, feedback counts, thresholds | Any user |
| `POST /api/v1/training/export` | Manually trigger training data export | QA Lead |
| `POST /api/v1/training/finetune` | Manually trigger fine-tuning for a track | QA Lead |
| `POST /api/v1/training/promote` | Manually promote an externally fine-tuned model | Admin |

### Submitting feedback from the UI

Rate an AI analysis result via the dashboard or directly via the API:

```bash
# Mark analysis as correct
curl -X POST https://your-backend/api/v1/feedback/<analysis_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"rating": "correct"}'

# Correct a wrong category
curl -X POST https://your-backend/api/v1/feedback/<analysis_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": "incorrect",
    "corrected_category": "INFRASTRUCTURE",
    "corrected_root_cause": "Pod OOMKilled during test — not a product bug",
    "comment": "This was an infra issue, not application code"
  }'
```

### Manually promoting an externally fine-tuned model

For providers without an automated fine-tuning API (vLLM, LM Studio, etc.), train the model externally using Unsloth or your preferred tool, then promote it:

```bash
# After fine-tuning with Unsloth and loading into Ollama as "qwen2.5:7b-qainsight-v2"
curl -X POST https://your-backend/api/v1/training/promote \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "track": "classifier",
    "model_name": "qwen2.5:7b-qainsight-v2",
    "eval_accuracy": 0.91,
    "baseline_accuracy": 0.83
  }'
```

The model is hot-swapped via Redis immediately — no backend restart required.

### Checking status

```bash
curl https://your-backend/api/v1/training/status \
  -H "Authorization: Bearer <token>"
```

```json
{
  "finetune_enabled": true,
  "feedback": { "total": 847, "unexported": 212 },
  "thresholds": {
    "classifier": 500,
    "reasoning": 2000,
    "embedding": 1000,
    "incremental_retrigger": 200
  },
  "active_models": {
    "classifier": {
      "active_model": "qwen2.5:7b-qainsight-classifier-20260301",
      "metrics": { "eval_accuracy": 0.91, "baseline_accuracy": 0.83, "improvement": 0.08 }
    },
    "reasoning": { "active_model": null, "metrics": null },
    "embedding": { "active_model": null, "metrics": null }
  }
}
```

### Expected timeline

| Milestone | Approximate calendar time (100k tests/day, 5% failure rate, 30% Jira resolution) |
|-----------|------------|
| 100 resolved defects | ~1 week — validate feedback pipeline |
| 500 resolved defects | ~3–4 weeks — first classifier fine-tune |
| 1 000 labeled pairs | ~6 weeks — embedding model fine-tune |
| 2 000 verified traces | ~12 weeks — full reasoning model fine-tune |
| Continuous improvement | Every 200 new verified examples trigger an incremental retrain |

### Automatic schedule

| Task | Schedule | What it does |
|------|----------|-------------|
| `export_training_data` | Weekly, Sunday 02:00 UTC | Exports all three JSONL tracks to MinIO, triggers fine-tuning if threshold crossed |
| `check_finetune_trigger` | Daily, 03:00 UTC | Fires export if ≥ 200 unexported feedback records accumulated |

---

## Environment Variables

See [`.env.example`](.env.example) for complete reference.

Key variables:

**LLM / AI**
- `LLM_PROVIDER` — `ollama` (default, offline) | `openai` | `gemini` | `lmstudio` | `vllm`
- `LLM_MODEL` — `qwen2.5:7b` (default for Ollama)
- `AI_OFFLINE_MODE` — `true` enforces local-only inference
- `AI_CONFIDENCE_THRESHOLD` — minimum confidence (0–100) to auto-create Jira ticket (default: 80)

**Fine-Tuning**
- `FINETUNE_ENABLED` — `false` by default; set `true` to enable the continuous learning pipeline
- `FINETUNE_CLASSIFIER_MIN_EXAMPLES` — examples needed to trigger Track 1 fine-tune (default: 500)
- `FINETUNE_REASONING_MIN_EXAMPLES` — examples needed to trigger Track 2 fine-tune (default: 2000)
- `FINETUNE_EMBED_MIN_PAIRS` — pairs needed to trigger Track 3 fine-tune (default: 1000)
- `FINETUNE_INCREMENTAL_TRIGGER` — re-trigger fine-tuning after this many new verified examples (default: 200)
- `FINETUNE_EVAL_HOLDOUT` — fraction of examples held out for A/B evaluation (default: 0.10)
- `FINETUNE_MIN_ACCURACY_GAIN` — candidate model must beat baseline by this margin to be promoted (default: 0.02)
- `FINETUNE_EXPORT_BUCKET` — MinIO bucket for training JSONL files (default: `training-data`)
- `CLASSIFIER_CONFIDENCE_THRESHOLD` — fast-path classifier confidence floor (default: 85)
- `CLASSIFIER_MODEL` — override model for fast classifier (default: same as `LLM_MODEL`)

**Authentication**
- `JWT_SECRET_KEY` — randomly generated secret for encoding authentication tokens
- `MCP_USERNAME` / `MCP_PASSWORD` — credentials for the containerised MCP service

## License

Apache 2.0 — see [LICENSE](LICENSE)
