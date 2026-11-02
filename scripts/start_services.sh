#!/usr/bin/env bash
# ==============================================================================
# Service Starter for Fashion Vision Pipeline in Google Colab (Docker-Free)
# ==============================================================================
set -euo pipefail

mkdir -p logs .pids /data/minio

# Export environment defaults
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://fashion_user:fashion_pass@localhost:5432/fashion_db}"
export MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
export MINIO_ROOT_USER="${MINIO_ACCESS_KEY}"
export MINIO_ROOT_PASSWORD="${MINIO_SECRET_KEY}"
export MINIO_SECURE="${MINIO_SECURE:-false}"
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"

echo "=== [1/5] Starting PostgreSQL ==="
service postgresql start

echo "=== [2/5] Starting MinIO Server ==="
if curl -fsS http://localhost:9000/minio/health/live >/dev/null 2>&1; then
    echo "MinIO is already running and healthy."
else
    # Release any stale processes on port 9000 and 9001
    fuser -k 9000/tcp 2>/dev/null || true
    fuser -k 9001/tcp 2>/dev/null || true
    pkill -9 -f "minio server" 2>/dev/null || true
    sleep 1

    nohup minio server /data/minio --address ":9000" --console-address ":9001" > logs/minio.log 2>&1 &
    echo $! > .pids/minio.pid
    echo "MinIO started with PID $(cat .pids/minio.pid)"
fi

echo "=== [3/5] Starting Apache Kafka (KRaft mode) ==="
KAFKA_DIR="/opt/kafka"
if (echo > /dev/tcp/localhost/9092) >/dev/null 2>&1; then
    echo "Kafka is already running."
else
    nohup "$KAFKA_DIR/bin/kafka-server-start.sh" "$KAFKA_DIR/config/kraft/server.properties" > logs/kafka.log 2>&1 &
    echo $! > .pids/kafka.pid
    echo "Kafka started with PID $(cat .pids/kafka.pid)"
fi

# Wait for core infrastructure services
echo "Waiting for PostgreSQL, MinIO, and Kafka to become ready..."
INFRA_READY=false
for i in {1..30}; do
    if pg_isready -h localhost -p 5432 -U fashion_user -d fashion_db >/dev/null 2>&1 && \
       curl -fsS http://localhost:9000/minio/health/live >/dev/null 2>&1 && \
       (echo > /dev/tcp/localhost/9092) >/dev/null 2>&1; then
        echo "PostgreSQL, MinIO, and Kafka are ready."
        INFRA_READY=true
        break
    fi
    sleep 1
done

if [ "$INFRA_READY" != "true" ]; then
    echo "ERROR: Infrastructure services failed to become healthy within 30 seconds."
    echo "Check logs/minio.log and logs/kafka.log for details."
    exit 1
fi

# Initialize MinIO Buckets
if command -v mc &>/dev/null; then
    mc alias set local http://localhost:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --api s3v4 >/dev/null 2>&1 || true
    mc mb --ignore-existing local/raw-images >/dev/null 2>&1 || true
    mc mb --ignore-existing local/crops >/dev/null 2>&1 || true
    echo "MinIO buckets 'raw-images' and 'crops' verified with mc."
else
    python3 -c "
from minio import Minio
import os

endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'

client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
for b in ['raw-images', 'crops']:
    if not client.bucket_exists(b):
        client.make_bucket(b)
" >/dev/null 2>&1 || true
    echo "MinIO buckets 'raw-images' and 'crops' verified with Python SDK."
fi

# Initialize Kafka Topics
"$KAFKA_DIR/bin/kafka-topics.sh" --create --if-not-exists --bootstrap-server localhost:9092 --topic fashion.jobs.stage1 >/dev/null 2>&1 || true
"$KAFKA_DIR/bin/kafka-topics.sh" --create --if-not-exists --bootstrap-server localhost:9092 --topic fashion.jobs.stage2 >/dev/null 2>&1 || true
"$KAFKA_DIR/bin/kafka-topics.sh" --create --if-not-exists --bootstrap-server localhost:9092 --topic fashion.jobs.dlq >/dev/null 2>&1 || true
echo "Kafka topics verified."

echo "=== [4/5] Starting FastAPI Application Gateway ==="
if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
    echo "FastAPI API is already running and healthy."
else
    fuser -k 8000/tcp 2>/dev/null || true
    pkill -9 -f "uvicorn.*fashion_pipeline" 2>/dev/null || true
    sleep 1
    nohup uvicorn fashion_pipeline.api.main:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
    echo $! > .pids/api.pid
    echo "FastAPI API started with PID $(cat .pids/api.pid)"
fi

echo "=== [5/5] Starting Fashion GPU Worker Daemon ==="
if pgrep -f "fashion_pipeline.worker.main" > /dev/null 2>&1; then
    echo "Fashion Worker is already running."
else
    nohup python -m fashion_pipeline.worker.main > logs/worker.log 2>&1 &
    echo $! > .pids/worker.pid
    echo "Fashion Worker started with PID $(cat .pids/worker.pid)"
fi

echo "Waiting for API endpoint readiness..."
API_READY=false
for i in {1..20}; do
    if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
        echo "API endpoint is healthy: http://localhost:8000/healthz"
        API_READY=true
        break
    fi
    sleep 1
done

if [ "$API_READY" != "true" ]; then
    echo "ERROR: FastAPI gateway failed to become ready on port 8000."
    echo "Check logs/api.log for details."
    exit 1
fi

echo "================================================================="
echo "All services successfully started without Docker."
echo "Inspect status with: bash scripts/status_services.sh"
echo "Run end-to-end test with: python scripts/test_pipeline_e2e.py"
echo "================================================================="
