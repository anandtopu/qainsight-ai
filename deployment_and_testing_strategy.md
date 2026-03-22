# QA Insight AI: Deployment and Testing Strategy

This document provides a comprehensive strategy to deploy and test the QA Insight AI application on your Local Machine and Google Cloud Platform (GCP). By following this strategy, you can ensure a reliable rollout while avoiding common deployment errors.

---

## Part 1: Local Machine Deployment & Testing Strategy

Local deployment uses Docker Compose to run the full stack, including the local LLM (Ollama) and vector database (ChromaDB) if desired.

### 1. Pre-Deployment Setup
* **Prerequisites**: Ensure you have Docker Desktop 4.x+, Node.js 20 LTS, and Python 3.11+ installed.
* **Environment Configuration**: 
  * Clone the repository.
  * Run `cp .env.example .env` and configure any specific local constraints.
  * Ensure ports `3000` (Frontend), `8000` (Backend API), `5432` (Postgres), `27017` (Mongo), `6379` (Redis), `9000/9001` (MinIO), and `11434` (Ollama) are free on your machine.

### 2. Deployment Execution
* **Start the Stack**: Run `make dev` (which executes `docker compose up -d --build`).
* **Initialize Database**: Run `make migrate` to apply Alembic migrations.
* **Fetch AI Models (Optional)**: Run `make pull-llm` to download `qwen2.5:7b` for local offline AI inference.

### 3. Testing & Verification
To ensure the local application is error-free, follow these testing phases:

* **Automated Testing Suite**: 
  * Run `make test-backend` to execute pytest for backend endpoints.
  * Run `make test-frontend` to run Vitest for UI components.
  * Run `make test-e2e` for Playwright end-to-end testing.
* **Component Health Checks**:
  * Verify the backend is up by calling `curl http://localhost:8000/health`.
  * Ensure the MinIO console is accessible at `http://localhost:9001` (admin/password123).
  * Check the Celery worker and broker using Flower at `http://localhost:5555`.
* **Manual UI & Integration Check**:
  * Open `http://localhost:3000` in your browser.
  * Create a sample test run to verify the async ingestion worker and database layers (Postgres & Mongo) operate successfully.

---

## Part 2: Google Cloud Platform (GCP) Deployment & Testing Strategy

The GCP strategy utilizes a single `e2-medium` VM instance deploying with Docker Compose. To save on RAM and disk costs, we swap the local Ollama LLM for the Google Gemini free API.

### 1. Pre-Deployment Setup
* **Provision the VM**: Create an `e2-medium` Debian 12 VM with a 30GB standard persistent disk.
* **Configure Firewall**: Open ports `22` (SSH), `80` (Frontend), and `8000` (Backend).
* **Install Docker**: Install Docker and Docker Compose plugin on the VM.
* **Get API Keys**: Obtain a free Gemini API Key for lightweight cloud AI.

### 2. Deployment Execution
* **Configuration**: 
  * SSH into the VM, clone the repo, and run `cp .env.gcp-vm.example .env`.
  * Update `.env` with strong passwords, the Gemini `GOOGLE_API_KEY`, and set `VITE_API_BASE_URL` to your VM's external IP address.
* **Add Swap Memory**: To prevent Out-Of-Memory (OOM) crashes, configure a 2GB swap file (`sudo fallocate -l 2G /swapfile`, `mkswap`, `swapon`).
* **Start Core Services**: 
  * Run `docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml up -d --build`.
  * Apply migrations: `docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml exec backend alembic upgrade head`.
* **Start Async Workers**:
  * `docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml --profile async up -d worker beat`.

### 3. Testing & Verification
Since the GCP environment replaces local models with cloud APIs and relies on dynamic IPs, testing focuses on integration and resource stability.

* **Health and Port Checks**:
  * Run `curl http://localhost:8000/health` directly from the VM SSH terminal to ensure the API resolves internally.
  * Access `http://<VM_External_IP>` from your personal browser. If it fails, verify GCP Firewall rules and container statuses.
* **Database & Migration Sanity**:
  * Run `docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml exec backend alembic current` to verify schemas align with the application base.
* **AI Provider Test**:
  * Ensure the Gemini API works by checking the `backend` Docker logs or manually curling the GenerateLanguage API from the VM terminal.
* **Load/Resource Monitoring**:
  * Monitor VM memory via `docker stats` and `free -h` to ensure the 2GB swap file handles the background workers correctly. Make sure `backend` doesn't OOM restart.

---

## Post-Deployment Workflow (GCP Cost Management)
Because GCP charges by the hour for compute, coordinate with your team to safely stop and resume the VM:
1. **Stop down gracefully**: `docker compose ... down` to flush states safely.
2. **Stop the VM**: Stop the instance from the GCP Console or CLI.
3. **Re-starting**: The VM External IP will change. Always update `VITE_API_BASE_URL` in `.env` and rebuild the frontend container (`docker compose ... up -d --build frontend`) when you spin it up the next day.
