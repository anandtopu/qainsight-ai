# QA Insight AI Installation and Deployment Guide

This guide consolidates the Google Cloud instructions shared earlier and adds ready-to-use deployment assets for:

1. Single-VM deployment on Google Compute Engine (free-tier friendly)
2. Cleaner internet-accessible deployment path with Cloud Run + Cloud SQL

---

## 1) What is realistic on Google Cloud free tier

The current stack in `docker-compose.yml` includes multiple stateful services and AI components. On an Always Free VM, running everything at once is usually not practical.

Recommended baseline for testing:

- Run: `postgres`, `mongo`, `redis`, `minio`, `backend`, `frontend`
- Add only when needed: `worker`, `beat`, `flower`
- Add for AI assistant integration: `mcp` (lightweight — 256MB RAM, no DB access)
- Keep disabled on free-tier VM by default: `ollama`, `chromadb`
- Prefer cloud LLM API for testing (`gemini` or `openai`) instead of local Ollama

---

## 2) GCP prerequisites

- A Google Cloud account with billing enabled
- Docker knowledge and Git access to this repo
- Domain name optional (recommended later for HTTPS)

Set budget alerts before deploying:

- 50%, 90%, and 100% thresholds
- Email notifications enabled

---

## 3) Compute Engine VM deployment (free-tier friendly)

### 3.1 Create project and VM

Use Cloud Shell:

```bash
gcloud projects create qainsight-ai-free --name="QA Insight AI Free"
gcloud config set project qainsight-ai-free
gcloud services enable compute.googleapis.com
```

Create VM (adjust region/zone if needed):

```bash
gcloud compute instances create qainsight-vm \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-type=pd-standard \
  --boot-disk-size=30GB \
  --tags=qainsight-web
```

Open only required ports:

```bash
gcloud compute firewall-rules create qainsight-allow-web \
  --allow=tcp:22,tcp:80,tcp:8000,tcp:8002 \
  --target-tags=qainsight-web \
  --source-ranges=0.0.0.0/0
```

> **Port 8002** is the MCP SSE server — open only if you need remote AI assistant access.
> For local-only Claude Desktop use (stdio mode), do not expose port 8002.

### 3.2 Install Docker + Compose on VM

```bash
gcloud compute ssh qainsight-vm --zone=us-central1-a
```

Inside VM:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### 3.3 Deploy this repository with GCP compose override

```bash
git clone https://github.com/yourorg/qainsight-ai.git
cd qainsight-ai
cp .env.gcp-vm.example .env
```

Edit `.env` — set real secrets, `MCP_USERNAME`, `MCP_PASSWORD`, and the VM public IP as `QAINSIGHT_API_URL`, then start:

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml exec backend alembic upgrade head
```

Validate:

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml ps
curl http://localhost:8000/health
```

Get VM public IP:

```bash
curl ifconfig.me
```

Open:

- `http://<VM_IP>` — frontend dashboard
- `http://<VM_IP>:8000/docs` — backend API docs
- `http://<VM_IP>:8002/sse` — MCP SSE endpoint (for AI assistant integration)

### 3.4 Connect Claude Desktop to the VM-hosted MCP

On your local machine, add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "qainsight": {
      "url": "http://<VM_IP>:8002/sse"
    }
  }
}
```

Or use stdio mode (runs locally, connects to the remote backend):

```json
{
  "mcpServers": {
    "qainsight": {
      "command": "python",
      "args": ["/path/to/qainsight-ai/mcp/server.py"],
      "env": {
        "QAINSIGHT_API_URL": "http://<VM_IP>:8000",
        "QAINSIGHT_USERNAME": "your-user",
        "QAINSIGHT_PASSWORD": "your-pass"
      }
    }
  }
}
```

### 3.5 Optional: enable async workers later

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml --profile async up -d worker beat
```

### 3.6 Optional: enable local AI later (not free-tier friendly)

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml --profile ai up -d ollama chromadb
```

---

## 4) Cloud Run + Cloud SQL deployment path (cleaner internet access)

This path gives cleaner public access for frontend/backend/MCP while moving PostgreSQL to managed Cloud SQL.

Important: Cloud Run cannot host stateful local services like MongoDB/MinIO/Redis for production-style usage. For a cleaner setup:

- PostgreSQL: Cloud SQL (managed)
- MongoDB: MongoDB Atlas free/shared tier
- Redis: Memorystore (paid) or external Redis provider for test usage
- S3-compatible object storage: Cloud Storage S3 interoperability endpoint or external S3-compatible provider
- MCP Server: Cloud Run service (SSE transport, `--no-allow-unauthenticated` recommended)

Use `docs/cloud-run-cloud-sql.md` for full steps.

---

## 5) Security baseline

- Use strong random values for `APP_SECRET_KEY` and `JWT_SECRET_KEY`
- Set `MCP_USERNAME` and `MCP_PASSWORD` — the MCP container authenticates to the backend using these
- Restrict firewall to `22`, `80`, `443` once stable; only expose `8002` if remote MCP access is needed
- Do not expose database ports publicly
- Rotate API keys and secrets periodically
- On Cloud Run, deploy MCP with `--no-allow-unauthenticated` and use IAM to restrict invoker access

---

## 6) Cost control checklist

- Create billing budget alerts
- Stop VM when not in use:

```bash
gcloud compute instances stop qainsight-vm --zone=us-central1-a
```

- Start VM only when needed:

```bash
gcloud compute instances start qainsight-vm --zone=us-central1-a
```

- Remove unused images/volumes periodically on VM:

```bash
docker system prune -af
```

- MCP server has minimal resource usage (256MB RAM, no persistent storage) — safe to leave running.

---

## 7) Quick troubleshooting

- Backend unhealthy:

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml logs -f backend
```

- DB migration issues:

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml exec backend alembic current
```

- Frontend cannot reach backend: ensure `VITE_API_BASE_URL` in `.env` points to your public backend URL and rebuild frontend:

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml up -d --build frontend
```

- MCP server not responding:

```bash
docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml logs -f mcp
# Check that QAINSIGHT_API_URL inside the container can reach the backend
docker compose exec mcp python -c "import httpx; import asyncio; print(asyncio.run(httpx.AsyncClient().get('http://backend:8000/health')))"
```

- MCP authentication errors: verify `MCP_USERNAME` and `MCP_PASSWORD` in `.env` match a registered user (POST /api/v1/auth/register).
