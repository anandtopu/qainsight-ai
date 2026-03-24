# ============================================================
# QA Insight AI — Developer Makefile
# ============================================================
.PHONY: help dev stop build test-backend test-frontend migrate lint clean logs pull-llm

DOCKER_COMPOSE = docker compose
BACKEND_CONTAINER = qainsight_backend
OLLAMA_CONTAINER = qainsight_ollama

help: ## Show this help message
	@echo "QA Insight AI — Development Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Development ─────────────────────────────────────────────

dev: ## Start all services in development mode
	$(DOCKER_COMPOSE) up -d --build
	@echo "✅ Stack started. Dashboard: http://localhost:3000 | API: http://localhost:8000/docs"

dev-logs: ## Tail logs for all services
	$(DOCKER_COMPOSE) logs -f

stop: ## Stop all services
	$(DOCKER_COMPOSE) down

restart: ## Restart all services
	$(DOCKER_COMPOSE) restart

clean: ## Stop services and remove volumes (WARNING: deletes all data)
	$(DOCKER_COMPOSE) down -v --remove-orphans
	@echo "⚠️  All volumes removed"

# ── Database ─────────────────────────────────────────────────

migrate: ## Run pending Alembic migrations
	$(DOCKER_COMPOSE) exec backend alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add_test_runs")
	$(DOCKER_COMPOSE) exec backend alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	$(DOCKER_COMPOSE) exec backend alembic downgrade -1

migrate-status: ## Show migration status
	$(DOCKER_COMPOSE) exec backend alembic current

# ── AI / LLM ─────────────────────────────────────────────────

pull-llm: ## Pull recommended local LLM models via Ollama
	$(DOCKER_COMPOSE) exec $(OLLAMA_CONTAINER) ollama pull qwen2.5:7b
	$(DOCKER_COMPOSE) exec $(OLLAMA_CONTAINER) ollama pull nomic-embed-text
	@echo "✅ Models downloaded"

pull-llm-large: ## Pull larger/more capable models (requires 16GB+ VRAM)
	$(DOCKER_COMPOSE) exec $(OLLAMA_CONTAINER) ollama pull qwen2.5:14b
	$(DOCKER_COMPOSE) exec $(OLLAMA_CONTAINER) ollama pull llama3.2:8b
	$(DOCKER_COMPOSE) exec $(OLLAMA_CONTAINER) ollama pull deepseek-coder:6.7b

list-llm: ## List downloaded LLM models
	$(DOCKER_COMPOSE) exec $(OLLAMA_CONTAINER) ollama list

# ── Testing ───────────────────────────────────────────────────

test-backend: ## Run backend test suite (pytest)
	$(DOCKER_COMPOSE) exec backend pytest tests/ -v --tb=short

test-backend-cov: ## Run backend tests with coverage report
	$(DOCKER_COMPOSE) exec backend pytest tests/ -v --cov=app --cov-report=html --cov-report=term

test-frontend: ## Run frontend test suite (Vitest)
	$(DOCKER_COMPOSE) exec frontend npm run test

test-e2e: ## Run end-to-end tests (Playwright)
	$(DOCKER_COMPOSE) exec frontend npm run test:e2e

test-agent: ## Run AI agent unit tests with mocked tools
	$(DOCKER_COMPOSE) exec backend pytest tests/test_agent.py -v

# ── Code Quality ─────────────────────────────────────────────

lint: ## Lint all code (ruff + eslint)
	$(DOCKER_COMPOSE) exec backend ruff check app/ tests/
	$(DOCKER_COMPOSE) exec frontend npm run lint

format: ## Auto-format all code (ruff + prettier)
	$(DOCKER_COMPOSE) exec backend ruff format app/ tests/
	$(DOCKER_COMPOSE) exec frontend npm run format

type-check: ## Run type checking (mypy + tsc)
	$(DOCKER_COMPOSE) exec backend mypy app/
	$(DOCKER_COMPOSE) exec frontend npm run type-check

# ── Build ─────────────────────────────────────────────────────

build: ## Build production Docker images
	docker build -t qainsight/backend:latest --target production ./backend
	docker build -t qainsight/frontend:latest --target production ./frontend
	@echo "✅ Production images built"

build-push: ## Build and push images to registry (set REGISTRY env var)
	docker build -t $(REGISTRY)/qainsight/backend:$(VERSION) --target production ./backend
	docker build -t $(REGISTRY)/qainsight/frontend:$(VERSION) --target production ./frontend
	docker push $(REGISTRY)/qainsight/backend:$(VERSION)
	docker push $(REGISTRY)/qainsight/frontend:$(VERSION)

# ── Kubernetes ────────────────────────────────────────────────

k8s-deploy-dev: ## Deploy to development Kubernetes cluster
	kubectl apply -k k8s/overlays/dev

k8s-deploy-staging: ## Deploy to staging Kubernetes cluster
	kubectl apply -k k8s/overlays/staging

k8s-deploy-prod: ## Deploy to production Kubernetes cluster
	kubectl apply -k k8s/overlays/prod

k8s-deploy-openshift: ## Deploy using OpenShift-compatible overlay
	kubectl apply -k k8s/overlays/openshift

k8s-status: ## Show Kubernetes deployment status
	kubectl get pods,svc,ing -n qainsight-ai

# ── Utilities ─────────────────────────────────────────────────

logs: ## Tail backend logs
	$(DOCKER_COMPOSE) logs -f backend worker

shell-backend: ## Open a shell in the backend container
	$(DOCKER_COMPOSE) exec backend bash

shell-db: ## Open psql in the postgres container
	$(DOCKER_COMPOSE) exec postgres psql -U ${POSTGRES_USER:-qainsight_user} -d ${POSTGRES_DB:-qainsight}

simulate-upload: ## Simulate a Jenkins test run upload to MinIO (for testing)
	./scripts/simulate-upload.sh

setup-minio: ## Manually configure MinIO bucket and webhook
	./scripts/setup-minio.sh

# ── MCP Server ────────────────────────────────────────────────

mcp-install: ## Install MCP server Python dependencies
	cd mcp && pip install -r requirements.txt

mcp-start: ## Start MCP server (stdio mode — for MCP Clients)
	cd mcp && python server.py --transport stdio

mcp-sse: ## Start MCP server (SSE mode — for web/CI clients on port 8002)
	cd mcp && python server.py --transport sse --port 8002

mcp-sse-docker: ## Start MCP SSE server via Docker Compose
	$(DOCKER_COMPOSE) up -d mcp
	@echo "✅ MCP SSE server running at http://localhost:8002/sse"
