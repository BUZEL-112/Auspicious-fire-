# Event-Driven Pre-Computed Fashion Vision Pipeline

Production-ready asynchronous fashion recognition, wardrobe parsing, and outfit recommendation platform built on Claim-Check and Event-Driven Orchestration patterns.

Detailed technical and scientific documentation is available in the [Technical Architecture Report](docs/TECHNICAL_REPORT.md).

## Features

### Phase 1: Fashion Vision Pipeline
- **Asynchronous Ingestion**: FastAPI gateway with non-blocking multipart file uploads and presigned URL support (`POST /api/v1/jobs` and `POST /api/v1/analyze`). Returns `202 Accepted` in less than 30ms.
- **Stage 1 (Single-Garment Tagging)**: Isolated garment tagging with multi-faceted attributes (`category`, `color`, `fabric`, `pattern`, `neckline`, `sleeve`, `fit`) using FashionCLIP pre-computed embeddings and Grouped Softmax.
- **Stage 2 (Multi-Object Outfit Parsing)**: SegFormer-B4 human parser (18 semantic classes), threshold filtering, sequential piece indexing (`piece_0`, `piece_1`, ...), bounding box extraction, solid-white background masking (`255, 255, 255`), and batched Stage 1 forward pass.
- **Pre-Computed Taxonomy**: DeepFashion vocabulary JSON text embeddings pre-computed once on GPU cold start, L2-normalized, and pinned in memory.
- **Conditional Tag Rules**: Context-aware suppression (for example: suppressing sleeve and neckline tags on pants, shoes, bags).
- **Claim-Check Pattern**: Raw images and segmented garment crops stored in MinIO object storage.
- **Real-Time Delivery**: Polling (`GET /api/v1/jobs/{job_id}`) and Server-Sent Events push (`GET /api/v1/jobs/{job_id}/stream`) powered by PostgreSQL `LISTEN`/`NOTIFY`.
- **Resilience**: DLQ routing for poison-pill messages after 3 retries, robust error handling (`NO_GARMENTS_DETECTED`, `CORRUPTED_IMAGE`).

### Phase 2: Wardrobe Ingestion and Context-Aware Recommendation Engine
- **Wardrobe Ingestion**: Ingest and register user garments via `POST /api/v1/users/{user_id}/wardrobe` with automatic synchronous or asynchronous tagging.
- **Garment Slot Mapping**: Automatic classification into functional outfit slots (`top`, `bottom`, `one_piece`, `outerwear`, `footwear`, `accessory`).
- **Wardrobe Retrieval**: Query user wardrobe by status and slot filter via `GET /api/v1/users/{user_id}/wardrobe`.
- **Context Questionnaire**: Five structured dressing context questions via `GET /api/v1/context/questions` (Occasion, Formality, Weather, Time/Setting, Style Mood).
- **Heuristic Recommendation Engine**: Multi-stage filtering and scoring via `POST /api/v1/users/{user_id}/recommendations`:
  - Hard Thermal Filters (suppresses wool and coats in hot weather, suppresses shorts and sandals in cold weather).
  - Hard Formality Filters (suppresses hoodies and t-shirts in black tie and formal events).
  - Compatibility Scoring (color harmony, style coherence, layer balance).
- **Pre-Packaged Dataset**: 30 hand-verified garments across three style personas in `tests/dummy/dummy_wardrobes.json`, with images bundled in `data/demo_wardrobe/` (sources and licences in `data/demo_wardrobe/ATTRIBUTION.md`).

### Phase 3: Store Catalog Gap Analysis and Outfit Unlock Scoring
- **Store Catalog API**: Explore retail inventory by garment slot via `GET /api/v1/shopping/store/items`.
- **Wardrobe Gap Detection**: Identifies missing garment slots required for specific weather conditions or formality levels.
- **Outfit Unlock Metric**: Calculates the exact number of new high-scoring outfits each store item unlocks (`POST /api/v1/shopping/users/{user_id}/recommendations`).
- **One-Click Wardrobe Addition**: Instantly transfers purchased store items into personal wardrobes via `POST /api/v1/shopping/users/{user_id}/purchase`.

### Interactive Showcase Application
- **Two-Stage Streamlit UI**: Launch via `streamlit run streamlit_app.py` for direct visual analysis, wardrobe inspection, and outfit testing.
- **Stacked Lookbook Generator**: Composes modular garment pieces into an anatomical, vertically stacked lookbook card with labels and score badges.

## Architecture and Alternatives Summary

The platform uses a layered architecture: `API` -> `Services` -> `Repositories` -> `Database`.

1. **Current System (Ensemble Pipeline):**
   - Combines YOLO (person detection), SegFormer (semantic segmentation), SAM (layer splitting), and FashionCLIP (zero-shot facet classification).
   - Offloads image binaries to MinIO (`Claim-Check`), writes events to Apache Kafka, and pushes updates using PostgreSQL `LISTEN`/`NOTIFY`.
2. **Alternative 1: Unified Multimodal VLM:**
   - Replaces the multi-model pipeline with a single end-to-end Vision-Language Model.
   - Preserves global visual context (drape, silhouette, posture) and removes sequential error cascading.
3. **Alternative 2: Learned Machine Learning Recommendation Engine:**
   - Replaces deterministic heuristics with Type-Aware Siamese Networks, Outfit Set Transformers, and Two-Tower user personalization models.
4. **Shopping Integration Architecture:**
   - Integrates live merchant feeds, real-time `pgvector` / Milvus HNSW indexing, unlock utility ranking, and generative virtual try-on (VTON).

For full technical specifications and mathematical formulations, refer to [docs/TECHNICAL_REPORT.md](docs/TECHNICAL_REPORT.md).

## Quickstart

### 1. Interactive Streamlit Showcase

Run the interactive dashboard locally:

```bash
streamlit run streamlit_app.py
```

### 2. Using Docker Compose

```bash
docker compose up --build
```

### 3. Using Google Colab (Docker-Free via Colab CLI)

Run these commands inside your Google Colab terminal, notebook cells, or remotely via the Colab CLI:

```bash
# 1. Install packages and set up dependencies
#    (also fetches the curated demo wardrobe release, demo-wardrobe-v1)
bash scripts/colab_setup.sh

# Optional: refresh only the demo wardrobe data (photos, personas, store catalog)
bash scripts/fetch_demo_wardrobe.sh

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

### 4. Remote Execution via WSL Colab CLI

```bash
# Provision a Colab CPU session and execute the full test suite
bash scripts/colab_cpu_runner.sh fashion-cpu

# Connect interactively to the session
colab console -s fashion-cpu

# Terminate the instance when finished
colab stop -s fashion-cpu
```
