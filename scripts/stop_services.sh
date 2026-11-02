#!/usr/bin/env bash
# ==============================================================================
# Service Stopper for Fashion Vision Pipeline in Google Colab (Docker-Free)
# ==============================================================================
set -u

stop_process_from_pid_file() {
    local pid_file="$1"
    local service_name="$2"

    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            for _ in {1..10}; do
                if ! kill -0 "$pid" 2>/dev/null; then
                    break
                fi
                sleep 0.5
            done
            if kill -0 "$pid" 2>/dev/null; then
                echo "Force terminating $service_name (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

echo "=== Stopping Application Services ==="
stop_process_from_pid_file ".pids/worker.pid" "Fashion Worker"
stop_process_from_pid_file ".pids/api.pid" "FastAPI API"

# Fallback pattern and port kills for orphan worker/uvicorn processes
pkill -9 -f "fashion_pipeline.worker.main" 2>/dev/null || true
pkill -9 -f "fashion_pipeline.api.main:app" 2>/dev/null || true
pkill -9 -f "uvicorn" 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true

echo "=== Stopping Infrastructure Services ==="
stop_process_from_pid_file ".pids/kafka.pid" "Apache Kafka"
if [ -d "/opt/kafka" ]; then
    /opt/kafka/bin/kafka-server-stop.sh 2>/dev/null || true
fi
pkill -9 -f "kafka.Kafka" 2>/dev/null || true
fuser -k 9092/tcp 2>/dev/null || true

stop_process_from_pid_file ".pids/minio.pid" "MinIO"
pkill -9 -f "minio server" 2>/dev/null || true
pkill -9 -x "minio" 2>/dev/null || true
fuser -k 9000/tcp 2>/dev/null || true
fuser -k 9001/tcp 2>/dev/null || true

echo "=== Stopping PostgreSQL ==="
service postgresql stop 2>/dev/null || true

echo "All services stopped."
