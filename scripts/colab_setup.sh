#!/usr/bin/env bash
# ==============================================================================
# Setup Script for Fashion Vision Pipeline in Google Colab (Docker-Free)
# ==============================================================================
set -euo pipefail

echo "=== [1/5] Creating runtime directories ==="
mkdir -p logs .pids /data/minio

echo "=== [2/5] Installing and configuring PostgreSQL ==="
if ! command -v psql &>/dev/null; then
    apt-get update -qq
    apt-get install -y -qq postgresql postgresql-contrib
fi

service postgresql start

# Configure user, database, and permissions
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='fashion_user'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER fashion_user WITH PASSWORD 'fashion_pass';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='fashion_db'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE fashion_db OWNER fashion_user;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE fashion_db TO fashion_user;"

# Run schema initialization
if [ -f "scripts/init_db.sql" ]; then
    sudo -u postgres psql -d fashion_db -f scripts/init_db.sql
    echo "PostgreSQL schema and triggers initialized."
fi

echo "=== [3/5] Installing MinIO and MinIO Client ==="
MINIO_URL="https://web.archive.org/web/20260213151321id_/https://dl.min.io/server/minio/release/linux-amd64/minio"
MC_URL="https://web.archive.org/web/20260115183137id_/https://dl.min.io/client/mc/release/linux-amd64/mc"

if ! command -v minio &>/dev/null; then
    echo "Downloading MinIO server binary..."
    curl -fsSL "$MINIO_URL" -o /usr/local/bin/minio || wget -q "$MINIO_URL" -O /usr/local/bin/minio
    chmod +x /usr/local/bin/minio
fi

if ! command -v mc &>/dev/null; then
    echo "Downloading MinIO client binary..."
    (curl -fsSL "$MC_URL" -o /usr/local/bin/mc || wget -q "$MC_URL" -O /usr/local/bin/mc) || true
    chmod +x /usr/local/bin/mc 2>/dev/null || true
fi

echo "=== [4/5] Installing Apache Kafka (KRaft mode) ==="
if ! command -v java &>/dev/null; then
    echo "Installing Java JRE for Kafka..."
    apt-get install -y -qq default-jre
fi

KAFKA_DIR="/opt/kafka"
if [ ! -d "$KAFKA_DIR" ]; then
    echo "Downloading Apache Kafka 3.7.0..."
    mkdir -p /opt
    KAFKA_URL="https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz"
    curl -fsSL "$KAFKA_URL" -o /tmp/kafka.tgz
    tar -xzf /tmp/kafka.tgz -C /opt/
    mv /opt/kafka_2.13-3.7.0 "$KAFKA_DIR"
    rm -f /tmp/kafka.tgz

    echo "Formatting Kafka KRaft storage..."
    KAFKA_CLUSTER_ID="$("$KAFKA_DIR/bin/kafka-storage.sh" random-cluster-id)"
    "$KAFKA_DIR/bin/kafka-storage.sh" format -t "$KAFKA_CLUSTER_ID" -c "$KAFKA_DIR/config/kraft/server.properties"
fi

echo "=== [5/5] Installing Python Dependencies ==="
pip install -q -r requirements.txt
pip install -q -e .

echo "=== Setup complete! Next run: bash scripts/start_services.sh ==="
