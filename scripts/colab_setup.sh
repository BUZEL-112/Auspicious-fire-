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
sudo -u postgres psql -d fashion_db -c "GRANT ALL ON SCHEMA public TO fashion_user;" 2>/dev/null || true

# Run schema initialization
if [ -f "scripts/init_db.sql" ]; then
    sudo -u postgres psql -d fashion_db -f scripts/init_db.sql
    sudo -u postgres psql -d fashion_db -c "ALTER TABLE jobs OWNER TO fashion_user; GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fashion_user; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fashion_user;" 2>/dev/null || true
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

if ! command -v aria2c &>/dev/null; then
    echo "Installing aria2 for accelerated multi-connection downloads..."
    apt-get install -y -qq aria2
fi

KAFKA_DIR="/opt/kafka"
if [ ! -d "$KAFKA_DIR" ]; then
    echo "Downloading Apache Kafka 3.7.0..."
    mkdir -p /opt
    rm -f /tmp/kafka.tgz /tmp/kafka.tgz.aria2

    # Primary download from Apache Archive (Default)
    KAFKA_URL="https://archive.apache.org/dist/kafka/3.7.0/kafka_2.13-3.7.0.tgz"
    if command -v aria2c &>/dev/null; then
        echo "Using aria2c for accelerated download (16 connections)..."
        aria2c -x 16 -s 16 -k 1M --allow-overwrite=true --auto-file-renaming=false --summary-interval=5 --dir=/tmp -o kafka.tgz "$KAFKA_URL" || curl -fsSL "$KAFKA_URL" -o /tmp/kafka.tgz
    else
        curl -fsSL "$KAFKA_URL" -o /tmp/kafka.tgz
    fi
    tar -xzf /tmp/kafka.tgz -C /opt/
    mv /opt/kafka_2.13-3.7.0 "$KAFKA_DIR"
    rm -f /tmp/kafka.tgz /tmp/kafka.tgz.aria2

    # Maven repository fallback option (uncomment below and comment out archive.apache.org above if archive is slow):
    # KAFKA_MAVEN_REPO="https://repo1.maven.org/maven2/org/apache/kafka/kafka_2.13/3.7.0"
    # KAFKA_JAR_URL="${KAFKA_MAVEN_REPO}/kafka_2.13-3.7.0.jar"
    # mkdir -p "$KAFKA_DIR/libs"
    # aria2c -x 16 -s 16 -k 1M --allow-overwrite=true --auto-file-renaming=false --dir="$KAFKA_DIR/libs" -o kafka_2.13-3.7.0.jar "$KAFKA_JAR_URL" || curl -fsSL "$KAFKA_JAR_URL" -o "$KAFKA_DIR/libs/kafka_2.13-3.7.0.jar"
fi

# Ensure Kafka KRaft storage is formatted
if [ -d "$KAFKA_DIR" ]; then
    if ! "$KAFKA_DIR/bin/kafka-storage.sh" info -c "$KAFKA_DIR/config/kraft/server.properties" &>/dev/null; then
        echo "Formatting Kafka KRaft storage..."
        KAFKA_CLUSTER_ID="$("$KAFKA_DIR/bin/kafka-storage.sh" random-uuid)"
        "$KAFKA_DIR/bin/kafka-storage.sh" format -t "$KAFKA_CLUSTER_ID" -c "$KAFKA_DIR/config/kraft/server.properties" --ignore-formatted
    fi
fi

echo "=== [5/5] Installing Python Dependencies ==="
pip install -q -r requirements.txt
pip install -q git+https://github.com/facebookresearch/segment-anything.git || true
pip install -q -e .

# Pre-download SAM ViT-B checkpoint
if [ ! -f "sam_vit_b_01ec64.pth" ]; then
    echo "Downloading SAM ViT-B checkpoint..."
    SAM_URL="https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
    if command -v aria2c &>/dev/null; then
        aria2c -x 16 -s 16 -k 1M --allow-overwrite=true --auto-file-renaming=false -o sam_vit_b_01ec64.pth "$SAM_URL" || curl -fsSL "$SAM_URL" -o sam_vit_b_01ec64.pth || true
    else
        curl -fsSL "$SAM_URL" -o sam_vit_b_01ec64.pth || true
    fi
fi

echo "=== Setup complete! Next run: bash scripts/start_services.sh ==="
