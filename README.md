# Event-Driven Pre-Computed Fashion Vision Pipeline

Production-ready asynchronous, two-phase fashion recognition and outfit parsing engine built on Claim-Check and Event-Driven Orchestration patterns.

## Features

### Phase 1: Fashion Vision Pipeline
- **Asynchronous Ingestion**: FastAPI gateway with non-blocking multipart file uploads and presigned URL support (`POST /api/v1/jobs` and `POST /api/v1/analyze`). Returns `202 Accepted` in less than 30ms.
- **Stage 1 (Single-Garment Tagging)**: Isolated garment tagging with multi-faceted attributes (`category`, `color`, `fabric`, `pattern`, `neckline`, `sleeve`, `fit`) using FashionCLIP pre-computed embeddings and Grouped Softmax.
- **Stage 2 (Multi-Object Outfit Parsing)**: SegFormer-B4 human parser (18 semantic classes), threshold filtering, sequential piece indexing (`piece_0`, `piece_1`, ...), bounding box extraction, solid-white background masking (`255, 255, 255`), and batched Stage 1 forward pass.
- **Pre-Computed Taxonomy**: DeepFashion vocabulary JSON text embeddings pre-computed once on GPU cold start, L2-normalized, and pinned in memory.
- **Conditional Tag Rules**: Context-aware suppression (e.g., suppressing sleeve/neckline tags on pants, shoes, bags).
- **Claim-Check Pattern**: Raw images and segmented garment crops stored in MinIO object storage.
- **Real-Time Delivery**: Polling (`GET /api/v1/jobs/{job_id}`) and Server-Sent Events push (`GET /api/v1/jobs/{job_id}/stream`) powered by PostgreSQL `LISTEN`/`NOTIFY`.
- **Resilience**: DLQ routing for poison-pill messages after 3 retries, robust error handling (`NO_GARMENTS_DETECTED`, `CORRUPTED_IMAGE`).

### Phase 2: Wardrobe Ingestion & Context-Aware Recommendation Engine
- **Wardrobe Ingestion**: Ingest and register user garments via `POST /api/v1/users/{user_id}/wardrobe` with automatic synchronous or asynchronous tagging.
- **Garment Slot Mapping**: Automatic classification into functional outfit slots (`top`, `bottom`, `one_piece`, `outerwear`, `footwear`, `accessory`).
- **Wardrobe Retrieval**: Query user wardrobe by status and slot filter via `GET /api/v1/users/{user_id}/wardrobe`.
- **Context Questionnaire**: Five structured dressing context questions via `GET /api/v1/context/questions` (Occasion, Formality, Weather, Time/Setting, Style Mood).
- **Heuristic Recommendation Engine**: Multi-stage filtering and scoring via `POST /api/v1/users/{user_id}/recommendations`:
  - Hard Thermal Filters (suppresses wool/coats in hot weather, suppresses shorts/sandals in cold weather).
  - Hard Formality Filters (suppresses hoodies/t-shirts in black tie and formal events).
  - Compatibility Scoring (color harmony, style coherence, layer balance).
- **Pre-Packaged Dataset**: 100 garments across five distinct style personas with real clothing image URLs in `tests/dummy/dummy_wardrobes.json`.

## Quickstart

### Using Docker Compose

```bash
docker compose up --build
```

### Using Google Colab (Docker-Free via Colab CLI)

Run these commands inside your Google Colab terminal, notebook cells, or remotely via the Colab CLI:

```bash
# 1. Install packages and set up dependencies
bash scripts/colab_setup.sh

# 2. Launch background services (PostgreSQL, MinIO, Kafka KRaft, API, Worker)
bash scripts/start_services.sh

# 3. Verify process and port status
bash scripts/status_services.sh

# 4. Execute end-to-end pipeline verification test (Phase 1)
python scripts/test_pipeline_e2e.py

# 5. Execute wardrobe ingestion and recommendation verification test (Phase 2)
python scripts/test_wardrobe_recommendations_e2e.py

# 6. Execute multi-user persona recommendations suite
python scripts/multi_user_recommendations.py

# 7. Stop all background services
bash scripts/stop_services.sh
```

### Remote Execution via WSL Colab CLI

```bash
# Provision a Colab CPU session and execute the full test suite
bash scripts/colab_cpu_runner.sh fashion-cpu

# Connect interactively to the session
colab console -s fashion-cpu

# Terminate the instance when finished
colab stop -s fashion-cpu
```
