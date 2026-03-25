# Jenkins Deployment Pipeline

This document describes the Jenkins pipeline provided in `Jenkinsfile` for QA Insight AI.

## What the pipeline does

- Checks out the repository
- Ensures `.env` exists (copies from `.env.example` when missing)
- Validates Docker Compose artifacts (`docker-compose.yml` and `docker-compose.gcp-vm.yml`)
- Runs backend, frontend, and MCP checks inside Docker services
- Builds production images for `backend`, `frontend`, and `mcp`
- Optionally pushes images to a registry
- Optionally deploys to a remote GCP VM over SSH and runs Alembic migrations
- Supports Kubernetes/OpenShift promotion workflows via repository overlays and Make helpers

## Jenkins prerequisites

- Jenkins agent with:
  - Docker Engine + Docker Compose v2
  - Git
  - Bash shell
- Jenkins plugins:
  - Pipeline
  - Credentials Binding
  - SSH Agent
  - JUnit
  - Workspace Cleanup
  - ANSI Color (optional but recommended)
- Tooling:
  - `kubectl`
  - `kustomize` (needed when updating overlay image tags)

## Required Jenkins credentials

- Docker registry credentials (Username/Password)
  - Default ID expected by pipeline parameter: `docker-registry-creds`
- SSH private key for VM deployment
  - Default ID expected by pipeline parameter: `qainsight-vm-ssh`

## Pipeline parameters

- `RUN_TESTS`: run backend/frontend/MCP checks
- `BUILD_IMAGES`: build production images
- `PUSH_IMAGES`: push built images to registry
- `DOCKER_REGISTRY`: image prefix, e.g. `ghcr.io/org/repo`
- `REGISTRY_CREDENTIALS_ID`: Jenkins credentials ID for registry login
- `DEPLOY_TO_VM`: enable remote deploy stage
- `VM_SSH_CREDENTIALS_ID`: Jenkins SSH key credential ID
- `DEPLOY_SSH_TARGET`: remote host in `user@host` format
- `DEPLOY_PATH`: absolute repository path on remote VM
- `DEPLOY_PROFILE`: `standard` or `async` (starts worker/beat when async)

## Suggested job setup

1. Create a Pipeline job in Jenkins.
2. Point it to the repository and set script path to `Jenkinsfile`.
3. Configure a webhook (or poll SCM) for `main`/`develop`.
4. For PR validation jobs:
   - `RUN_TESTS=true`
   - `BUILD_IMAGES=false`
   - `PUSH_IMAGES=false`
   - `DEPLOY_TO_VM=false`
5. For main deployment job:
   - `RUN_TESTS=true`
   - `BUILD_IMAGES=true`
   - `PUSH_IMAGES=true`
   - `DEPLOY_TO_VM=true`

## Example remote deploy assumptions

The deploy stage assumes the VM already has:

- Docker and Docker Compose installed
- Repo cloned at `${DEPLOY_PATH}`
- `.env` configured on the VM
- SSH access from Jenkins agent

Remote deploy command flow:

1. `git fetch --all --prune`
2. `git checkout <branch>` and `git pull --ff-only`
3. `docker compose -f docker-compose.yml -f docker-compose.gcp-vm.yml up -d --build`
4. `docker compose ... exec backend alembic upgrade head`
5. Optionally start async services with `--profile async`

## Notes

- The pipeline intentionally runs checks in containers to keep host dependencies minimal.
- If your Jenkins node is resource-constrained, split testing and deployment into separate jobs.
- If you deploy by image digest instead of source pull, adapt the deploy stage to pull immutable tags and update compose files accordingly.

## Useful deployment checks after Jenkins rollout

```bash
# Verify async components in each environment
make k8s-rollout-async-dev
make k8s-rollout-async-staging
make k8s-rollout-async-prod

# Inspect worker/beat deployments and HPAs
make k8s-status-async K8S_NAMESPACE=qainsight-ai

# OpenShift Route status (if using OpenShift)
make k8s-status-openshift K8S_NAMESPACE=qainsight-ai
```

