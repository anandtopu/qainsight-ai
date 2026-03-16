# Cloud Run + Cloud SQL Deployment Path

This path is designed for cleaner internet-accessible testing than a single VM.

It deploys:

- `backend` to Cloud Run
- `frontend` to Cloud Run
- PostgreSQL to Cloud SQL

And uses external managed endpoints for services Cloud Run does not host natively as stateful local containers:

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
  --set-secrets=ENV_FILE=qainsight-backend-env:latest \
  --add-cloudsql-instances=INSTANCE_CONNECTION_NAME \
  --set-env-vars=APP_ENV=production
```

Note: Cloud Run does not automatically parse a dotenv from one env var. Use the explicit env var deploy command below for production use:

```bash
gcloud run services update qainsight-backend \
  --region=${REGION} \
  --env-vars-file=infra/cloudrun/backend.env
```

Run migrations from a one-off Cloud Run job or local admin workstation with network access to Cloud SQL.

## 7) Build and push frontend image

Get backend URL:

```bash
export BACKEND_URL=$(gcloud run services describe qainsight-backend --region=${REGION} --format='value(status.url)')
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

## 8) Post-deploy checks

```bash
curl "${BACKEND_URL}/health"
gcloud run services list --region=${REGION}
```

Open frontend URL from Cloud Run service output.

## 9) Notes for this repository

- Backend expects MongoDB, Redis, and S3-compatible storage endpoints via env vars.
- For cleaner internet deployment, do not run Mongo/Redis/MinIO inside Cloud Run.
- Use external managed services and map them in `infra/cloudrun/backend.env`.
- Async workers (`Celery`) are optional for initial testing; many dashboard paths can still be validated without them.

