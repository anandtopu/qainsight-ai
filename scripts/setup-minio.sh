#!/usr/bin/env bash
# One-time MinIO bucket and webhook notification setup
set -euo pipefail

ALIAS="local"
ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
ACCESS_KEY="${MINIO_ACCESS_KEY:-admin}"
SECRET_KEY="${MINIO_SECRET_KEY:-password123}"
BUCKET="${MINIO_BUCKET_NAME:-test-telemetry}"
BACKEND_URL="${BACKEND_URL:-http://backend:8000}"

echo "🗂️  Setting up MinIO…"

mc alias set ${ALIAS} "${ENDPOINT}" "${ACCESS_KEY}" "${SECRET_KEY}"

# Create buckets
mc mb --ignore-existing ${ALIAS}/${BUCKET}
mc mb --ignore-existing ${ALIAS}/qainsight-attachments
echo "  ✓ Buckets created"

# Allow public read on attachments bucket (for presigned URL access)
mc anonymous set download ${ALIAS}/qainsight-attachments
echo "  ✓ Attachment bucket configured"

# Configure webhook notification (triggers on JSON file uploads)
mc admin config set ${ALIAS} notify_webhook:1 \
  endpoint="${BACKEND_URL}/webhooks/minio" \
  queue_limit=10000 \
  queue_dir="/tmp/minio-events" \
  client_cert="" \
  client_key=""

mc admin service restart ${ALIAS}
sleep 2

mc event add ${ALIAS}/${BUCKET} \
  arn:minio:sqs::1:webhook \
  --event put \
  --suffix .json

echo "  ✓ Webhook notification configured"
echo ""
echo "✅  MinIO setup complete!"
echo "   Bucket:  ${BUCKET}"
echo "   Webhook: ${BACKEND_URL}/webhooks/minio"
