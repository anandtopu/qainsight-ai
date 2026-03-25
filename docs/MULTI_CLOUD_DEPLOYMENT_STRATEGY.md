# QA Insight AI Multi-Cloud Deployment Strategy

This document defines a cloud-portable strategy for deploying QA Insight AI on AWS, GCP, Azure, and private cloud Kubernetes/OpenShift.

## 1) Deployment baseline

- Runtime images: `backend`, `frontend`, `mcp`
- Async images/workloads: `qainsight-worker`, `qainsight-beat` (from backend image)
- Environment model:
  - `k8s/overlays/dev`
  - `k8s/overlays/staging`
  - `k8s/overlays/prod`
  - `k8s/overlays/openshift`

## 2) Cloud platform mappings

### AWS

- Kubernetes: EKS
- Registry: ECR
- Postgres: RDS PostgreSQL
- Mongo-compatible: DocumentDB or MongoDB Atlas
- Redis: ElastiCache
- Object storage: S3
- Secrets: AWS Secrets Manager (+ External Secrets)

### GCP

- Kubernetes: GKE (recommended for full async workloads)
- Managed path: Cloud Run + Cloud SQL for stateless services
- Registry: Artifact Registry
- Mongo-compatible: MongoDB Atlas
- Redis: Memorystore
- Object storage: GCS/S3-compatible endpoint

### Azure

- Kubernetes: AKS
- Registry: ACR
- Postgres: Azure Database for PostgreSQL
- Mongo-compatible: Cosmos DB (Mongo API) or Atlas
- Redis: Azure Cache for Redis
- Object storage: Blob (or S3-compatible provider)

### Private cloud

- Kubernetes distributions: kubeadm/RKE2/Tanzu/others
- OpenShift: use `k8s/overlays/openshift` with Route resources
- Secrets: Vault/ESO/OpenShift Secrets

## 3) Standard deployment workflow

1. Build and tag images.
2. Push to registry.
3. Apply overlay for target environment.
4. Run Alembic migration.
5. Verify backend + async rollout.
6. Run smoke tests (`/health`, login, ingestion sample).

## 4) Environment expectations

- Dev: lower cost, low async capacity (`worker=1`, `beat=0`)
- Staging: production-like validation (`worker=1`, `beat=1`)
- Prod: scaled async path (`worker=3`, `beat=1`, worker HPA)

## 5) Operational commands

```bash
# Deploy overlays
kubectl apply -k k8s/overlays/dev
kubectl apply -k k8s/overlays/staging
kubectl apply -k k8s/overlays/prod
kubectl apply -k k8s/overlays/openshift

# Rollout checks
make k8s-rollout-async-dev
make k8s-rollout-async-staging
make k8s-rollout-async-prod

# Status checks
make k8s-status-async K8S_NAMESPACE=qainsight-ai
```

## 6) Security and compliance

- Keep secrets out of repository history.
- Use cloud secret managers or Vault for production credentials.
- Restrict ingress/routes to required hosts only.
- Keep MCP service authenticated (`QAINSIGHT_USERNAME`/`QAINSIGHT_PASSWORD`).
- Enforce image provenance and vulnerability scanning in CI.

