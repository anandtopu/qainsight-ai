# Cloud Run + Cloud SQL Deployment Path

This path is designed for cleaner internet-accessible testing than a single VM.

It deploys:

- `backend` to Cloud Run
- `frontend` to Cloud Run
- `mcp` to Cloud Run (optional — enables AI assistant integration in CI/hosted environments)
- PostgreSQL to Cloud SQL

Async background processing note:

- `worker` and `beat` are first-class runtime components in this project.
- On Cloud Run, run them as Cloud Run Jobs (scheduled/invoked) or move to GKE for persistent worker behavior.

And uses external managed endpoints for services Cloud Run does not host natively:

- MongoDB: MongoDB Atlas
- Redis: external Redis provider (or Memorystore)
- S3-compatible object storage: S3 provider or GCS interoperability endpoint

## 1) Prerequisites

- `gcloud` CLI authenticated
- Billing enabled
- APIs enabled: Cloud Run, Cloud Build, Artifact Registry, Cloud SQL Admin, Secret Manager

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com
```

Set common variables:

```bash
export PROJECT_ID="YOUR_PROJECT_ID"
export REGION="us-central1"
export REPO="qainsight"
export DB_INSTANCE="qainsight-pg"
export DB_NAME="qainsight"
export DB_USER="qainsight_user"
export DB_PASSWORD="CHANGE_ME_STRONG"
```

## 2) Create Artifact Registry

```bash
gcloud artifacts repositories create ${REPO} \
  --repository-format=docker \
  --location=${REGION} \
  --description="QA Insight AI images"
```

## 3) Create Cloud SQL PostgreSQL

```bash
gcloud sql instances create ${DB_INSTANCE} \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=${REGION}

gcloud sql databases create ${DB_NAME} --instance=${DB_INSTANCE}
gcloud sql users create ${DB_USER} --instance=${DB_INSTANCE} --password=${DB_PASSWORD}
```

Get Cloud SQL instance connection name:

```bash
gcloud sql instances describe ${DB_INSTANCE} --format="value(connectionName)"
```

## 4) Create Secret Manager entries

Use `infra/cloudrun/backend.env.example` as your source template.

```bash
gcloud secrets create qainsight-backend-env --replication-policy="automatic"
gcloud secrets versions add qainsight-backend-env --data-file=infra/cloudrun/backend.env
```

Create frontend env file from `infra/cloudrun/frontend.env.example` and upload:

```bash
gcloud secrets create qainsight-frontend-env --replication-policy="automatic"
gcloud secrets versions add qainsight-frontend-env --data-file=infra/cloudrun/frontend.env
```

Create MCP env file from `infra/cloudrun/mcp.env.example`:

```bash
gcloud secrets create qainsight-mcp-env --replication-policy="automatic"
gcloud secrets versions add qainsight-mcp-env --data-file=infra/cloudrun/mcp.env
```

## 5) Build and push backend image

```bash
gcloud builds submit . \
  --config=infra/cloudrun/cloudbuild.backend.yaml \
  --substitutions=_REGION=${REGION},_PROJECT_ID=${PROJECT_ID},_REPO=${REPO}
```

## 6) Deploy backend service to Cloud Run

Replace `INSTANCE_CONNECTION_NAME` below with Cloud SQL connection name from step 3.

```bash
gcloud run deploy qainsight-backend \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:latest \
  --region=${REGION} \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --memory=1Gi \
  --cpu=1 \
  --add-cloudsql-instances=INSTANCE_CONNECTION_NAME \
  --set-env-vars=APP_ENV=production
```

Apply environment variables:

```bash
gcloud run services update qainsight-backend \
  --region=${REGION} \
  --env-vars-file=infra/cloudrun/backend.env
```

Run migrations from a one-off Cloud Run job or local admin workstation with Cloud SQL access:

```bash
gcloud run jobs create migrate-db \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:latest \
  --region=${REGION} \
  --add-cloudsql-instances=INSTANCE_CONNECTION_NAME \
  --command="alembic" \
  --args="upgrade,head"

gcloud run jobs execute migrate-db --region=${REGION}
```

## 7) Build and push frontend image

Get backend URL:

```bash
export BACKEND_URL=$(gcloud run services describe qainsight-backend \
  --region=${REGION} --format='value(status.url)')
```

Build frontend with API URL baked at build time:

```bash
gcloud builds submit . \
  --config=infra/cloudrun/cloudbuild.frontend.yaml \
  --substitutions=_REGION=${REGION},_PROJECT_ID=${PROJECT_ID},_REPO=${REPO},_VITE_API_BASE_URL=${BACKEND_URL}
```

Deploy frontend:

```bash
gcloud run deploy qainsight-frontend \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend:latest \
  --region=${REGION} \
  --platform=managed \
  --allow-unauthenticated \
  --port=80 \
  --memory=512Mi \
  --cpu=1
```

## 8) Build and deploy MCP server (optional)

The MCP server exposes QA Insight AI to AI Desktop Clients, IDE plugins, and CI pipelines.
Deploying it to Cloud Run enables SSE transport for hosted/CI clients.

Build the MCP image:

```bash
gcloud builds submit . \
  --config=infra/cloudrun/cloudbuild.mcp.yaml \
  --substitutions=_REGION=${REGION},_PROJECT_ID=${PROJECT_ID},_REPO=${REPO}
```

Deploy MCP to Cloud Run (SSE transport on port 8002):

```bash
export BACKEND_URL=$(gcloud run services describe qainsight-backend \
  --region=${REGION} --format='value(status.url)')

gcloud run deploy qainsight-mcp \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/mcp:latest \
  --region=${REGION} \
  --platform=managed \
  --no-allow-unauthenticated \
  --port=8002 \
  --memory=256Mi \
  --cpu=1 \
  --set-env-vars=QAINSIGHT_API_URL=${BACKEND_URL}
```

Apply MCP credentials (do NOT embed credentials in the image):

```bash
gcloud run services update qainsight-mcp \
  --region=${REGION} \
  --env-vars-file=infra/cloudrun/mcp.env
```

Get the MCP SSE URL:

```bash
export MCP_URL=$(gcloud run services describe qainsight-mcp \
  --region=${REGION} --format='value(status.url)')
echo "MCP SSE endpoint: ${MCP_URL}/sse"
```

### Connecting your AI Assistant to the hosted MCP

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "qainsight-cloud": {
      "url": "https://qainsight-mcp-xxxx-uc.a.run.app/sse"
    }
  }
}
```

> **Security note:** Cloud Run MCP is deployed with `--no-allow-unauthenticated`.
> Use `gcloud auth print-identity-token` or set up Cloud Run IAM invoker roles for your service account.

## 9) Post-deploy checks

```bash
# Backend health
curl "${BACKEND_URL}/health"

# MCP SSE endpoint (if deployed)
curl "${MCP_URL}/sse"

# List deployed services
gcloud run services list --region=${REGION}
```

Open frontend URL from Cloud Run service output.

## 10) Notes for this repository

- Backend expects MongoDB, Redis, and S3-compatible storage endpoints via env vars.
- For cleaner internet deployment, do not run Mongo/Redis/MinIO inside Cloud Run.
- Use external managed services and map them in `infra/cloudrun/backend.env`.
- Async workers (`Celery worker` + `beat`) are required for full production behavior.
- For Cloud Run-only deployments, implement async processing via Cloud Run Jobs and Cloud Scheduler, or adopt GKE for always-on workers.
- The MCP server is stateless — it proxies all requests to the backend. No database access required.
- MCP in stdio mode (MCP Clients) does not require a Cloud Run deployment — run `make mcp-start` locally against the hosted backend URL.
