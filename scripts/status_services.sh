#!/usr/bin/env bash
# ==============================================================================
# Service Status Inspector for Fashion Vision Pipeline in Google Colab
# ==============================================================================
set -u

echo "================================================================="
echo "Service Process and Port Status"
echo "================================================================="

check_service() {
    local name="$1"
    local pid_file="$2"
    local port="$3"

    local pid_status="STOPPED"
    local pid=""
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            pid_status="RUNNING (PID: $pid)"
        else
            pid_status="DEAD (stale PID file: $pid)"
        fi
    fi

    if [ "$pid_status" = "STOPPED" ]; then
        case "$name" in
            "MinIO") pid=$(pgrep -f "minio server" | head -n1 || true) ;;
            "Kafka KRaft") pid=$(pgrep -f "kafka.Kafka" | head -n1 || true) ;;
            "FastAPI Gateway") pid=$(pgrep -f "uvicorn.*fashion_pipeline" | head -n1 || true) ;;
            "Fashion Worker") pid=$(pgrep -f "fashion_pipeline.worker.main" | head -n1 || true) ;;
        esac
        if [ -n "$pid" ]; then
            pid_status="RUNNING (PID: $pid)"
            mkdir -p .pids
            echo "$pid" > "$pid_file"
        fi
    fi

    local port_status="PORT $port CLOSED"
    if (echo > "/dev/tcp/localhost/$port") >/dev/null 2>&1; then
        port_status="PORT $port OPEN"
    fi

    printf "%-18s | %-28s | %s\n" "$name" "$pid_status" "$port_status"
}

# PostgreSQL check
pg_status="STOPPED"
if service postgresql status >/dev/null 2>&1; then
    pg_status="RUNNING (system service)"
fi
pg_port="PORT 5432 CLOSED"
if (echo > /dev/tcp/localhost/5432) >/dev/null 2>&1; then
    pg_port="PORT 5432 OPEN"
fi
printf "%-18s | %-28s | %s\n" "PostgreSQL" "$pg_status" "$pg_port"

MINIO_PORT="${MINIO_PORT:-9020}"
check_service "MinIO" ".pids/minio.pid" "$MINIO_PORT"
check_service "Kafka KRaft" ".pids/kafka.pid" "9092"
check_service "FastAPI Gateway" ".pids/api.pid" "8000"
check_service "Fashion Worker" ".pids/worker.pid" "N/A"

echo "================================================================="
echo "Recent Logs (last 5 lines):"
echo "================================================================="
for log in logs/minio.log logs/kafka.log logs/api.log logs/worker.log; do
    if [ -f "$log" ]; then
        echo "--- $log ---"
        tail -n 5 "$log"
        echo ""
    fi
done
