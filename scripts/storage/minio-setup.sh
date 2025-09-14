#!/bin/bash
# MinIO setup script for development environment
# This script initializes MinIO buckets and policies for local development

set -e

MINIO_ENDPOINT=${MINIO_ENDPOINT:-"localhost:9000"}
MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-"minioadmin"}
MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-"minioadmin123"}

echo "Setting up MinIO buckets and policies..."

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
until mc alias set myminio http://$MINIO_ENDPOINT $MINIO_ACCESS_KEY $MINIO_SECRET_KEY > /dev/null 2>&1; do
    echo "MinIO not ready, waiting 5 seconds..."
    sleep 5
done

echo "MinIO is ready! Creating buckets..."

# Create buckets for different environments
BUCKETS=(
    "test-artifacts"
    "dev-artifacts"
    "staging-artifacts"
    "prod-artifacts"
)

for BUCKET in "${BUCKETS[@]}"; do
    echo "Creating bucket: $BUCKET"
    mc mb myminio/$BUCKET || echo "Bucket $BUCKET already exists"
done

echo "Setting bucket policies..."

# Set public policy for test artifacts (for easier testing)
mc policy set public myminio/test-artifacts

# Set private policies for other buckets
mc policy set private myminio/dev-artifacts
mc policy set private myminio/staging-artifacts
mc policy set private myminio/prod-artifacts

echo "Creating bucket lifecycle policies..."

# Set lifecycle policies for automatic cleanup
# Delete test artifacts after 7 days
cat > /tmp/test-lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "TestArtifactCleanup",
            "Status": "Enabled",
            "Expiration": {
                "Days": 7
            }
        }
    ]
}
EOF

# Delete dev artifacts after 30 days
cat > /tmp/dev-lifecycle.json << EOF
{
    "Rules": [
        {
            "ID": "DevArtifactCleanup",
            "Status": "Enabled",
            "Expiration": {
                "Days": 30
            }
        }
    ]
}
EOF

# Apply lifecycle policies
mc ilm import myminio/test-artifacts < /tmp/test-lifecycle.json || echo "Failed to set test lifecycle policy"
mc ilm import myminio/dev-artifacts < /tmp/dev-lifecycle.json || echo "Failed to set dev lifecycle policy"

echo "Creating test directories structure..."

# Create directory structure for organized storage
mc cp /dev/null myminio/test-artifacts/screenshots/.keep || true
mc cp /dev/null myminio/test-artifacts/videos/.keep || true
mc cp /dev/null myminio/test-artifacts/reports/.keep || true
mc cp /dev/null myminio/test-artifacts/traces/.keep || true
mc cp /dev/null myminio/test-artifacts/logs/.keep || true

mc cp /dev/null myminio/dev-artifacts/screenshots/.keep || true
mc cp /dev/null myminio/dev-artifacts/videos/.keep || true
mc cp /dev/null myminio/dev-artifacts/reports/.keep || true
mc cp /dev/null myminio/dev-artifacts/traces/.keep || true
mc cp /dev/null myminio/dev-artifacts/logs/.keep || true

echo "MinIO setup completed successfully!"
echo ""
echo "MinIO Console URL: http://localhost:9001"
echo "MinIO API Endpoint: http://localhost:9000"
echo "Access Key: $MINIO_ACCESS_KEY"
echo "Secret Key: $MINIO_SECRET_KEY"
echo ""
echo "Available buckets:"
mc ls myminio/

# Cleanup temporary files
rm -f /tmp/test-lifecycle.json /tmp/dev-lifecycle.json