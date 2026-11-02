# Event-Driven Pre-Computed Fashion Vision Pipeline

Production-ready asynchronous, two-phase fashion recognition and outfit parsing engine built on the Claim-Check and Event-Driven Orchestration patterns.

## Features

- **Asynchronous Ingestion**: FastAPI gateway with non-blocking multipart file uploads and presigned URL support (`POST /api/v1/jobs` and `POST /api/v1/analyze`). Returns `202 Accepted` in <30ms.
- **Two Execution Modes**:
  - **Stage 1 (Single-Garment Tagging)**: Isolated garment tagging with multi-faceted attributes (`category`, `color`, `fabric`, `pattern`, `neckline`, `sleeve`, `fit`) using FashionCLIP pre-computed embeddings and Grouped Softmax.
  - **Stage 2 (Multi-Object Outfit Parsing)**: SegFormer-B4 human parser (18 semantic classes), threshold filtering, sequential piece indexing (`piece_0`, `piece_1`, ...), bounding box extraction, solid-white background masking (`255, 255, 255`), and batched Stage 1 forward pass.
- **Pre-Computed Taxonomy**: DeepFashion vocabulary JSON text embeddings pre-computed once on GPU cold start, L2-normalized, and pinned in VRAM.
- **Conditional Tag Rules**: Context-aware suppression (e.g., suppressing sleeve/neckline tags on pants, shoes, bags).
- **Claim-Check Pattern**: Raw images and segmented garment crops stored in MinIO object storage.
- **Real-Time Delivery**: Polling (`GET /api/v1/jobs/{job_id}`) and Server-Sent Events push (`GET /api/v1/jobs/{job_id}/stream`) powered by PostgreSQL `LISTEN`/`NOTIFY`.
- **Resilience**: DLQ routing for poison-pill messages after 3 retries, robust error handling (`NO_GARMENTS_DETECTED`, `CORRUPTED_IMAGE`).

## Quickstart

### Using Docker Compose

```bash
docker compose up --build
```

### Using Google Colab (Docker-Free)

Run these commands inside your Google Colab terminal or notebook cells:

```bash
# 1. Install packages and set up dependencies
bash scripts/colab_setup.sh

# 2. Launch background services (PostgreSQL, MinIO, Kafka KRaft, API, Worker)
bash scripts/start_services.sh

# 3. Verify process and port status
bash scripts/status_services.sh

# 4. Execute end-to-end pipeline verification test
python scripts/test_pipeline_e2e.py

# 5. Stop all background services
bash scripts/stop_services.sh
```

You can also open and run [`notebooks/colab_quickstart.ipynb`](notebooks/colab_quickstart.ipynb).
