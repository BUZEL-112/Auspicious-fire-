# Technical Architecture Report: Event-Driven Fashion Vision and Recommendation Platform

## Document Metadata
- Platform: Event-Driven Pre-Computed Fashion Vision Pipeline
- Version: 2.0.0
- Compliance Standard: ASD-STE-100 (Simplified Technical English)
- Status: Production Engineering Specification

---

## 1. What the Project Does

The platform is an asynchronous, high-throughput fashion intelligence system. It processes fashion imagery, catalogs personal wardrobes, recommends coordinated outfits, and discovers retail purchase opportunities.

```
+---------------------------------------------------------------------------------------------------+
|                                   FASHION PLATFORM PHASES                                         |
+---------------------------------+---------------------------------+-------------------------------+
| PHASE 1: VISION PIPELINE        | PHASE 2: WARDROBE INTELLIGENCE  | PHASE 3: SHOPPING INTEGRATION |
| - Non-blocking REST ingestion   | - Personal wardrobe database    | - Live retail store catalog   |
| - Stage 1 single-item tagging   | - Automated slot classification | - Wardrobe gap detection      |
| - Stage 2 multi-garment parsing | - Five-axis context questionnaire| - Outfit unlock calculation  |
| - Pinned GPU taxonomy vectors   | - Context-aware compatibility   | - Direct wardrobe checkout    |
+---------------------------------+---------------------------------+-------------------------------+
| INTERACTIVE SHOWCASE: Streamlit Web UI + Anatomical Stacked Lookbook Generator                     |
+---------------------------------------------------------------------------------------------------+
```

### Phase 1: Fashion Vision Pipeline
Phase 1 provides computer vision capabilities through two operating modes:
1. **Stage 1 (Single-Garment Tagging):**
   The system ingests an image of an isolated clothing item. It predicts seven distinct fashion facets: `category`, `color`, `fabric`, `pattern`, `neckline`, `sleeve`, and `fit`. The system uses zero-shot classification with pre-computed text vectors and Grouped Softmax normalization.
2. **Stage 2 (Multi-Garment Outfit Parsing):**
   The system ingests a full-body photograph containing a complete outfit. It segments every clothing piece, removes the background, isolates each garment on a neutral canvas, and runs Stage 1 tagging on each extracted garment.

### Phase 2: Wardrobe Ingestion and Context-Aware Outfit Recommendation
Phase 2 manages personal clothing collections and recommends outfits:
1. **Wardrobe Ingestion:**
   Users upload wardrobe items. The system tags the garments and assigns each garment to a functional clothing slot: `top`, `bottom`, `one_piece`, `outerwear`, `footwear`, or `accessory`.
2. **Context Questionnaire:**
   The user supplies five structured lifestyle variables:
   - Occasion (`casual`, `business_casual`, `formal`, `date_night`, `workout_active`, `lounge`)
   - Formality (`ultra_casual`, `smart_casual`, `business_formal`, `semi_formal`, `black_tie`)
   - Weather (`freezing`, `cold`, `mild`, `warm`, `hot`, `rainy`, `snowy`)
   - Time and Setting (`morning_outdoor`, `afternoon_indoor`, `evening_outdoor`, `night_indoor`)
   - Style Mood (`clean_minimalist`, `bold_expressive`, `classic_tailored`, `relaxed_comfort`, `edgy_streetwear`)
3. **Recommendation Engine:**
   The system evaluates wardrobe items against the user context. It enforces hard environmental and formality rules. It then scores combinations using a multi-factor compatibility formula across color harmony, pattern balance, silhouette proportion, fabric texture harmony, and vision confidence.

### Phase 3: Store Catalog Gap Analysis and Outfit Unlock Scoring
Phase 3 connects personal wardrobes with commercial fashion catalogs:
1. **Catalog Exploration:**
   Users browse external store inventories classified by garment slot and attribute tags.
2. **Wardrobe Gap Detection:**
   The system inspects the user wardrobe to detect missing slots required for a specific weather condition or formality level.
3. **Outfit Unlock Scoring:**
   The system simulates adding candidate store items into the user wardrobe. It calculates how many new valid outfits each store item creates. It ranks items that provide the highest number of new high-scoring outfits.
4. **Direct Purchase Ingestion:**
   When a user acquires a store item, the system transfers the item metadata into the personal wardrobe with status `READY`.

### Interactive Showcase Application
The platform includes an interactive Streamlit application (`streamlit_app.py`) and a lookbook composite generator (`src/fashion_pipeline/utils/outfit_visualizer.py`):
- **Operating Modes:** The user can switch between Direct In-Memory Engine Mode (local GPU execution) and Backend API Mode (HTTP client communication).
- **Vision Pipeline Testing:** Users upload images, inspect bounding boxes, view segmentation masks, and inspect facet prediction probabilities.
- **Wardrobe and Recommendation Explorer:** Users select personas, answer the dressing context questionnaire, review top-ranked outfits, and inspect score breakdowns.
- **Lookbook Composite Visualizer:** The rendering engine composes individual wardrobe garment images into an anatomical, vertically stacked lookbook card with labels and badges.
- **Store Catalog and Unlock UI:** Users evaluate store items, view unlocked outfit previews, and add items directly to their digital closet.

---

## 2. How It Works: End-to-End Operational Flow

The platform separates fast HTTP request handling from compute-intensive machine learning inference.

```
CLIENT                API GATEWAY            MINIO STORAGE         APACHE KAFKA          GPU WORKER            POSTGRESQL
  |                        |                       |                     |                    |                    |
  |--- POST /jobs -------->|                       |                     |                    |                    |
  |    (multipart image)   |--- PutObject -------->|                     |                    |                    |
  |                        |<-- Object URI --------|                     |                    |                    |
  |                        |--- Insert Job (PENDING) ------------------------------------------------------------->|
  |                        |--- Produce Event -------------------------->|                    |                    |
  |<-- 202 Accepted -------|                       |                     |                    |                    |
  |    (job_id, < 30ms)    |                       |                     |                    |                    |
  |                        |                       |                     |<-- Consume Event --|                    |
  |                        |                       |                     |    (job_id)        |                    |
  |                        |                       |                     |                    |--- Set PROCESSING->|
  |                        |                       |<-- GetObject ----------------------------|                    |
  |                        |                       |    (image bytes)    |                    |                    |
  |                        |                       |                     |                    |-- Model Inference -|
  |                        |                       |                     |                    |   (CLIP / SegForm) |
  |                        |                       |--- PutObject (crops)-------------------->|                    |
  |                        |                       |                     |                    |--- Set COMPLETED ->|
  |                        |                       |                     |                    |    (save results)  |
  |                        |                       |                     |                    |--- NOTIFY channel -|
  |                        |<-- LISTEN Notification ---------------------------------------------------------------|
  |<-- SSE Stream Event ---|                       |                     |                    |                    |
```

### Step 1: Request Ingestion (< 30 Milliseconds)
1. A client application sends an HTTP `POST` request to `/api/v1/jobs` or `/api/v1/analyze`. The request includes the raw image file and the execution mode (`stage_1` or `stage_2`).
2. The FastAPI gateway accepts the upload stream into memory.
3. The gateway uploads the raw image bytes to MinIO object storage in the `raw-images` bucket. MinIO returns a unique storage key (for example: `raw-images/input/<uuid>.jpg`).
4. The gateway inserts a new row into the PostgreSQL `jobs` table with status `PENDING`.
5. The gateway constructs a compact event payload containing `job_id`, `bucket`, `object_key`, and `mode`.
6. The gateway publishes this event to the Apache Kafka topic `image-processing-tasks-stage1` or `image-processing-tasks-stage2`.
7. The gateway immediately returns an HTTP status code `202 Accepted` to the client. Total response time is under 30 milliseconds.

### Step 2: Message Consumption and Status Update
1. A distributed GPU worker continuously polls the Kafka cluster via an `AIOKafkaConsumer`.
2. When the worker receives an event, it begins execution in an isolated task wrapper.
3. The worker updates the job status to `PROCESSING` in PostgreSQL.
4. If a client connects to the Server-Sent Events stream (`GET /api/v1/jobs/{job_id}/stream`), the client immediately receives a `PROCESSING` status event.

### Step 3: Object Retrieval (Claim-Check Pattern)
1. The worker extracts the `bucket` and `object_key` strings from the event payload.
2. The worker retrieves the binary image payload from MinIO storage over the internal network.
3. The worker decodes the image bytes into an RGB NumPy array.

### Step 4: Machine Learning Inference
1. **If Stage 1:**
   - The engine resizes the image to 224x224 pixels and normalizes pixel values.
   - The engine passes the tensor through the FashionCLIP image encoder.
   - The engine performs matrix multiplication with the pre-computed text matrices.
   - The Grouped Softmax function selects the highest-probability label for each facet.
   - Domain suppression rules eliminate invalid tags (such as sleeve lengths on trousers).
2. **If Stage 2:**
   - The engine executes YOLO person detection to locate individual subjects.
   - The engine resizes each person crop to 384x576 pixels and passes the image through SegFormer.
   - SegFormer generates an 18-class semantic pixel map.
   - The engine filters out masks smaller than the minimum pixel threshold (1.5% of total area).
   - If upper-body garments contain overlapping layers, the engine executes Segment Anything (SAM) to isolate inner tops from outerwear.
   - For each valid mask, the engine creates a neutral canvas patch, places the masked garment, and encodes the patch to PNG bytes.
   - The worker uploads these garment patches to the MinIO `crops` bucket.
   - The engine stacks all extracted garment patches into a single tensor batch and executes a single batched FashionCLIP forward pass.

### Step 5: Persistence and Notification
1. The worker writes the structured analysis results into the `result` JSON column of the `jobs` table.
2. The worker updates the job status to `COMPLETED` and sets the completion timestamp.
3. PostgreSQL executes a database trigger that calls `pg_notify('job_status_channel', payload)`.
4. The FastAPI notification listener catches the notification and forwards the payload over the active Server-Sent Events connection.
5. The worker commits the Kafka consumer offset.

---

## 3. System Design

The architecture uses loose coupling, asynchronous event processing, and clear separation of concerns.

### 3.1 Architectural Structure
The platform follows Clean Architecture principles:
- **API Layer (`src/fashion_pipeline/api`):** Manages HTTP routing, request parsing, input validation, and SSE event streaming. No business logic resides in this layer.
- **Service Layer (`src/fashion_pipeline/services`):** Implements core business logic, including context resolution, heuristic recommendation formulas, and shopping catalog unlock calculations.
- **Repository Layer (`src/fashion_pipeline/repositories`):** Encapsulates all database query operations using SQLAlchemy ORM and asyncpg.
- **Database Model Layer (`src/fashion_pipeline/db`):** Defines relational tables, constraints, foreign keys, and JSON schemas.
- **Machine Learning Engine (`src/fashion_pipeline/ml`):** Manages neural network weights, GPU memory buffers, tensor transformations, and inference operations.

```
+-----------------------------------------------------------------------------------+
|                                  API GATEWAY                                      |
|  - routes.py (FastAPI endpoints)        - notifications.py (LISTEN/NOTIFY SSE)    |
|  - kafka_producer.py (Event publisher)  - dependencies.py (Session injection)     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                 SERVICES LAYER                                    |
|  - recommendation_service.py            - shopping_service.py                     |
|  - wardrobe_service.py                  - context_service.py                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                               REPOSITORIES LAYER                                  |
|  - job_repository.py                    - wardrobe_repository.py                  |
|  - store_repository.py                   - user_repository.py                      |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                         DATABASE & STORAGE INFRASTRUCTURE                         |
|  - PostgreSQL 16 (Relational state)     - MinIO Object Storage (Claim-Check)      |
|  - Apache Kafka KRaft (Event log)       - Pinned GPU Memory (Tensors)             |
+-----------------------------------------------------------------------------------+
```

### 3.2 The Claim-Check Pattern
Publishing high-resolution image binaries directly to Apache Kafka causes broker memory bloat, high network saturation, and consumer buffer thrashing.

The system uses the Claim-Check pattern:
1. The gateway writes the payload (image bytes) directly to MinIO.
2. The gateway publishes only a lightweight claim reference (bucket name and object key) to Kafka.
3. Average Kafka message size remains below 500 bytes.
4. Kafka brokers sustain high message throughput without payload serialization overhead.

### 3.3 Dead-Letter Queue (DLQ) and Fault Tolerance
Failures during vision inference must not block the consumer group or drop work.

```
               +--------------------------------------+
               | Kafka Topic: image-processing-tasks  |
               +--------------------------------------+
                                  |
                                  v
                       +----------------------+
                       | GPU Worker Consumer  |
                       +----------------------+
                                  |
                   +--------------+--------------+
                   |                             |
             [Success]                       [Failure]
                   |                             |
                   v                             v
       +-----------------------+     +-----------------------+
       | Job Status: COMPLETED |     | Retry Counter < 3?    |
       +-----------------------+     +-----------------------+
                                        |                 |
                                      [Yes]              [No]
                                        |                 |
                                        v                 v
                          +-------------------+  +-------------------+
                          | Re-publish with   |  | Job: FAILED       |
                          | retry_count + 1   |  | Route to DLQ Topic|
                          +-------------------+  +-------------------+
```

1. If an unhandled exception occurs (for example: corrupted image encoding), the worker catches the error.
2. The worker increments the `retry_count` attribute in the event payload.
3. If `retry_count < 3`, the worker re-publishes the event to the processing topic with a 2-second delay.
4. If `retry_count >= 3`, the worker:
   - Sets the job status to `FAILED` in PostgreSQL.
   - Records the specific failure reason (`CORRUPTED_IMAGE`, `PROCESSING_TIMEOUT`, or `INFERENCE_CRASH`).
   - Routes the poisoned event to the dead-letter topic `image-processing-dlq`.
   - Commits the offset to allow the consumer pipeline to proceed.

### 3.4 PostgreSQL LISTEN/NOTIFY with Server-Sent Events
The system does not require client polling. When the worker writes the final state to PostgreSQL, a trigger fires `pg_notify`. An asynchronous connection in the API gateway catches this notification and streams the event to the client browser over HTTP/2 Server-Sent Events.

---

## 4. Model Design

The machine learning pipeline integrates two models with pre-computed semantic taxonomy embeddings.

```
===================================================================================================
STAGE 1: SINGLE GARMENT TAGGING
===================================================================================================
Input Crop (224x224x3) ---> [FashionCLIP Image Encoder] ---> Normalized Image Vector (1x512)
                                                                       |
  +--------------------------------------------------------------------+
  | Matrix Multiplication: Logits = Image_Vector @ Pinned_Text_Weights.T * (100.0 / 100.0)
  v
[Grouped Softmax per Facet Group] ---> Multi-Faceted Predictions
  - Category:    "blazer"      (0.96)
  - Color:       "navy"        (0.94)
  - Fabric:      "wool"        (0.88)
  - Pattern:     "solid"       (0.92)
  - Neckline:    "notched"     (0.85)
  - Sleeve:      "long sleeve" (0.91)
  - Fit:         "slim fit"    (0.89)
  v
[Domain Suppression Rules] ---> Suppress invalid attributes for lower body items

===================================================================================================
STAGE 2: MULTI-GARMENT OUTFIT PARSING
===================================================================================================
Full Outfit Image ---> [YOLO Person Detector] ---> Person Crops
                             |
                             v
                  [SegFormer-B4 Parser] ---> 18-Class Semantic Mask
                             |
                             v
           [Area Filtering & SAM Layer Splitter] ---> Garment Masks
                             |
                             v
         [Canvas Normalization (255,255,255)] ---> Clean Garment Patches
                             |
                             v
    [Batch Tensor Stack (N, 3, 224, 224)] ---> Batched Stage 1 Inference
```

### 4.1 Stage 1: Zero-Shot Grouped Softmax Tagging
Traditional classifiers use a single flat softmax output across thousands of mutually exclusive classes. That approach fails for fashion because a garment simultaneously possesses a category, a color, a fabric, and a pattern.

Stage 1 uses FashionCLIP (`patrickjohncyh/fashion-clip`) with Grouped Softmax:
1. **Cold-Start Pre-Computation:**
   When the worker boots, it reads `deepfashion_taxonomy.json`. It formats each label into a structured prompt (for example: `"a fashion photo of silk fabric"`). It passes all prompts through the FashionCLIP text encoder, normalizes the output vectors using the L2 norm, and pins the resulting matrices in GPU memory.
2. **Grouped Softmax Computation:**
   Given an image embedding tensor $I \in \mathbb{R}^{N \times D}$ and a pinned text weight matrix $W_f \in \mathbb{R}^{C_f \times D}$ for facet $f$:
   $$\text{Logits}_f = I \cdot W_f^T$$
   $$P_f = \text{Softmax}(\text{Logits}_f)$$
   The engine computes the probabilities independently for each facet $f \in \{\text{category, color, fabric, pattern, neckline, sleeve, fit}\}$.
3. **Conditional Suppression Rules:**
   Domain rules suppress attributes that do not apply to specific categories. If the system classifies a garment as trousers, shoes, or a handbag, it deletes the `neckline` and `sleeve` keys from the prediction dictionary.

### 4.2 Stage 2: Semantic Segmentation and Outfit Parsing
Stage 2 parses full-body outfit photographs:
1. **Person Localization:**
   The engine passes the image to a YOLO detector to locate human figures. This step prevents cross-person garment merging when multiple people appear in the frame.
2. **Semantic Human Parsing:**
   The engine resizes the person crop to 384x576 pixels and passes it to SegFormer-B4 (`mattmdjaga/segformer_b2_clothes`). The model predicts 18 semantic clothing classes.
3. **Threshold Filtering:**
   The engine calculates the pixel area of each segmented entity. If the mask area is smaller than 1.5% of the total canvas area, the engine discards the mask as noise.
4. **Upper-Body Layer Splitting:**
   Single masks often merge layered garments (such as an open blazer over a t-shirt). When the engine detects an upper-body mask with multimodal spatial distribution, it prompts the Segment Anything Model (SAM) to isolate the inner layer from the outer layer.
5. **Background Masking:**
   The engine isolates the garment pixels and pastes them onto a solid white background (`255, 255, 255`). This prevents background color bleed from biasing the FashionCLIP visual encoder.
6. **Batched Extraction:**
   The engine stacks all isolated garment patches into a single tensor batch of shape $(N, 3, 224, 224)$. It executes one forward pass through Stage 1, tagging all garments in parallel.

---

## 5. Future Suggested Improvements and Project Limitations

### 5.1 Project Limitations

#### 1. Cascading Error Propagation
The two-stage pipeline links models sequentially. If SegFormer fails to segment a garment border accurately, the resulting crop includes background clutter or parts of adjacent garments. FashionCLIP then receives a distorted image and outputs incorrect attribute tags. Stage 1 cannot correct errors introduced by Stage 2.

#### 2. Closed-Vocabulary Rigidity
The Grouped Softmax implementation relies on a static taxonomy file (`deepfashion_taxonomy.json`). The system cannot recognize concepts outside this file, such as novel subcultures, micro-patterns, or technical materials. Adding new vocabulary items requires reloading text matrices.

#### 3. Crop Context Loss
Isolating a clothing item on a flat white background removes critical context:
- Body proportion context is lost.
- Garment drape and tension lines disappear.
- Styling methods (such as tucked shirts or cuffed trousers) cannot be evaluated.

#### 4. Multi-Model Memory Overhead
The worker loads four separate deep neural networks concurrently:
- YOLOv8 (person detection)
- SegFormer-B4 (semantic segmentation)
- SAM (layer splitting)
- FashionCLIP (visual feature extraction and tagging)

This architecture requires significant GPU VRAM (approximately 8 GB) and increases worker cold-start initialization time.

#### 5. Heuristic Cold Ceiling
The recommendation engine uses deterministic rules for color harmony, pattern clash, and formality matching. These rules provide good baseline recommendations, but they cannot adapt to individual user preferences or shifting cultural trends.

### 5.2 Recommended Engineering Improvements

```
+-----------------------------------------------------------------------------------+
|                        PLANNED SYSTEM UPGRADES                                    |
+------------------------------+----------------------------------------------------+
| UPGRADE                      | TECHNICAL IMPLEMENTATION                           |
+------------------------------+----------------------------------------------------+
| TensorRT / ONNX Acceleration | Quantize models to FP16 and INT8 execution graphs.  |
| Vector Database Indexing     | Deploy PostgreSQL pgvector or Milvus for HNSW ANN. |
| Dynamic Inference Batching   | Deploy Triton Inference Server to aggregate jobs.  |
| Active User Feedback Loops   | Track item accept and reject signals for tuning.   |
+------------------------------+----------------------------------------------------+
```

1. **Model Quantization and Compilation:**
   Convert SegFormer and FashionCLIP PyTorch weights to ONNX and compile them with NVIDIA TensorRT. FP16 and INT8 quantization will decrease inference latency by 60% and reduce VRAM requirements by half.
2. **Vector Database Migration:**
   Store 512-dimensional garment embeddings directly in PostgreSQL using `pgvector` or in a Milvus cluster. This allows sub-millisecond Approximate Nearest Neighbor (ANN) search over millions of items.
3. **Dynamic Batching with Triton Inference Server:**
   Replace the custom worker execution loop with NVIDIA Triton Inference Server. Triton aggregates incoming inference requests across concurrent Kafka partitions into dynamic batches, maximizing GPU saturation.
4. **Active Learning Feedback Loop:**
   Record user overrides of incorrect tags. Periodically fine-tune FashionCLIP projection layers on these user corrections.

---

## 6. Alternative Architecture 1: Unified End-to-End Multimodal Model vs. Ensemble of Models

An alternative architecture replaces the multi-model ensemble (YOLO, SegFormer, SAM, and FashionCLIP) with a single unified Vision-Language Model (VLM).

```
ENSEMBLE PIPELINE (CURRENT):
Raw Image ---> [YOLO] ---> [SegFormer] ---> [SAM] ---> [Crop/Mask] ---> [FashionCLIP] ---> [Rules Engine]
(Lossy intermediate steps, discrete JSON bottlenecks, cascading error risk)

UNIFIED MULTIMODAL VLM (ALTERNATIVE):
Raw Image + Prompt ---> [Unified Vision-Language Transformer] ---> Direct Structured Outfit Plan
(Continuous joint attention across all garments, body context, and stylistic harmony)
```

### 6.1 The Value of Holistic Information Processing
Humans do not evaluate fashion by cropping garments onto white cards. Humans evaluate outfits holistically. A unified multimodal model processes visual information in the same way.

#### 1. Cross-Modal Joint Attention
In an ensemble pipeline, SegFormer and FashionCLIP operate independently. FashionCLIP never sees the complete person, and SegFormer never understands fashion style.

A unified model applies self-attention across image patches and text prompt tokens simultaneously. The model observes how a garment drapes over the body, how fabrics reflect light, and how items interact with each other. This eliminates the need for separate bounding boxes and crop masks.

#### 2. Elimination of Information Bottlenecks
The current system converts an image into a discrete JSON object:
`{"category": "blazer", "color": "navy", "fabric": "wool"}`

This conversion discards 99% of the visual information. Subtle details like weave texture, shoulder padding, lapel width, and wear patterns are lost. The recommendation engine must make decisions based solely on these text tags.

An end-to-end model preserves dense latent representations throughout the network. The model reasons about outfit compatibility directly from pixel patterns, resulting in more accurate styling decisions.

#### 3. Zero-Shot Open-World Reasoning
Unified VLMs (such as fine-tuned Qwen2-VL, InternVL, or LLaVA-NeXT) process open-ended fashion queries without fixed taxonomy limitations. A single prompt can request:
- Garment identification and attribute tagging
- Garment bounding coordinates in normalized JSON
- An evaluation of outfit balance and silhouette harmony
- Context-specific styling recommendations

### 6.2 Architectural Comparison

| Dimension | Multi-Model Ensemble Pipeline (Current) | Unified End-to-End Multimodal Model (VLM) |
| :--- | :--- | :--- |
| **P95 Latency** | Fast (150ms to 250ms on modern GPU) | Moderate to High (600ms to 1200ms) |
| **Infrastructure Cost** | Low (Small parameter models, ~1.5B total) | High (Requires 8B to 14B parameter models) |
| **Global Visual Context** | None (Garment crops are isolated on white) | Complete (Full image and background preserved) |
| **Error Propagation** | High (Segmentation errors corrupt tagging) | None (Single forward pass without steps) |
| **Taxonomy Flexibility** | Low (Requires pre-computed static JSON) | High (Open-vocabulary, understands any concept) |
| **Operational Simplicity** | Complex (Four models, multiple pipelines) | Simple (One model, one deployment container) |

---

## 7. Alternative Architecture 2: Learned ML Outfit Compatibility Models vs. Heuristics

The current `HeuristicRecommendationEngine` relies on manual rules for color harmony, pattern clash, and weather suitability. A production platform should replace these rules with trained machine learning models.

```
+-----------------------------------------------------------------------------------+
|               LEARNED MACHINE LEARNING RECOMMENDATION PIPELINE                    |
+-----------------------------------------------------------------------------------+
| 1. CANDIDATE RETRIEVAL                                                            |
|    Query user wardrobe using category slot filters and weather constraints.        |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 2. TYPE-AWARE METRIC LEARNING (Siamese Metric Space)                              |
|    Project garment vectors into a metric space. Calculate pairwise compatibility:  |
|    d_compat = || W_top * v_top - W_bottom * v_bottom ||_2                         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 3. HYPERGRAPH NEURAL NETWORK / SET TRANSFORMER                                    |
|    Model the outfit as an unordered graph of garment nodes. Condition on context  |
|    vectors (occasion, weather, time) to predict overall compatibility score.       |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| 4. TWO-TOWER PERSONALIZED RANKING & CONTEXTUAL BANDITS                            |
|    User Tower (wear history, brand affinity) x Outfit Candidate Tower.            |
|    Explore novel aesthetics with upper confidence bound exploration.               |
+-----------------------------------------------------------------------------------+
```

### 7.1 Type-Aware Compatibility Embedding Networks
Standard Euclidean distance between general CLIP embeddings does not correlate with fashion compatibility. A black t-shirt is visually dissimilar from blue jeans, yet they form a classic outfit combination.

The system should implement Type-Aware Metric Learning:
1. Each clothing slot has a dedicated learned projection matrix $W_{\text{slot}}$.
2. Garment embeddings $v_i$ are projected into a shared compatibility space:
   $$z_i = W_{\text{slot}(i)} \cdot v_i$$
3. The network trains on large outfit datasets (such as Polyvore Outfits and DeepFashion) using Triplet Margin Loss:
   $$\mathcal{L} = \max(0, D(z_{\text{top}}, z_{\text{bottom}}^{+}) - D(z_{\text{top}}, z_{\text{bottom}}^{-}) + m)$$
4. Items that match well have low distance scores in the projected metric space.

### 7.2 Outfit Hypergraph Neural Networks and Set Transformers
Outfits are sets of items, not ordered lists. Pairwise compatibility is not sufficient; an outfit needs global coherence across all items.

The system should use an Outfit Set Transformer:
1. Garment embeddings represent nodes in a fully connected hypergraph.
2. A context vector $c$ (encoding temperature, occasion, and style mood) is added as an input token.
3. Multi-Head Induced Self-Attention blocks process the item set in a permutation-invariant manner.
4. The model outputs a compatibility score between 0.0 and 1.0, capturing complex interactions across all items simultaneously.

### 7.3 Two-Tower Personalized Ranking and Contextual Bandits
A great outfit recommendation must align with an individual user's taste.
1. **User Representation Tower:**
   An encoder processes user history (past purchases, items worn, items skipped) into a dynamic user taste vector $u \in \mathbb{R}^D$.
2. **Outfit Candidate Tower:**
   The Set Transformer outputs an outfit embedding vector $o \in \mathbb{R}^D$.
3. **Scoring:**
   The final ranking score is the dot product of user taste and outfit embedding:
   $$\text{Score} = \sigma(u \cdot o)$$
4. **Contextual Bandit Exploration:**
   To prevent repetitive recommendations, a LinUCB (Linear Upper Confidence Bound) bandit algorithm introduces controlled exploration of new styles and color combinations.

---

## 8. Full System Integration with External Shopping Applications

To recommend commercial purchases, the platform requires integration with live retail systems.

```
+-----------------------------------------------------------------------------------+
|                      EXTERNAL SHOPPING INTEGRATION ARCHITECTURE                   |
+-----------------------------------------------------------------------------------+
                                         |
    +------------------------------------+-----------------------------------+
    |                                    |                                   |
    v                                    v                                   v
+-----------------------+    +-----------------------+    +-----------------------+
| Shopify Store Webhooks|    | Affiliate Product Feed|    | Merchant CSV / REST   |
+-----------------------+    +-----------------------+    +-----------------------+
    |                                    |                                   |
    +------------------------------------+-----------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| INGESTION WORKER: Download image -> Compute FashionCLIP embedding -> Extract tags|
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| VECTOR DATABASE: Store catalog with pgvector / Milvus (HNSW index on 512-d CLIP)  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| GAP FILLER SEARCH: Fast vector search for complementary items to user wardrobe.   |
| Objective: Maximize (Unlocked Outfits) / (Price USD)                              |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| GENERATIVE VIRTUAL TRY-ON (VTON): Diffusion model renders item on user silhouette.|
+-----------------------------------------------------------------------------------+
```

### 8.1 Real-Time Catalog Ingestion Pipeline
1. **Merchant Ingestion Interfaces:**
   The system ingests product catalogs from retail partners via Shopify App webhooks, merchant API feeds, and automated inventory synchronizers.
2. **Automated Vector Pipeline:**
   When a retailer adds a new product, an ingestion worker downloads the product photograph, extracts attribute tags using Stage 1 inference, generates a 512-dimensional FashionCLIP vector, and stores the record in the catalog database.
3. **Index Structure:**
   The catalog uses Hierarchical Navigable Small World (HNSW) indexing in `pgvector` or Milvus. This index structure enables sub-10ms nearest-neighbor queries across millions of retail items.

### 8.2 Fast Retrieval of Complementary Gap Fillers
The recommendation service finds store items that maximize wardrobe utility:
1. The system identifies empty slots in the user wardrobe for a target occasion or weather setting (for example: lack of formal footwear).
2. The system computes the centroid vector of the user's existing tops and trousers.
3. The system queries the vector index using the complementary metric space projection:
   $$v_{\text{query}} = W_{\text{footwear}} \cdot z_{\text{wardrobe\_centroid}}$$
4. The system ranks retrieved candidate items using an unlock optimization ratio:
   $$\text{Utility} = \frac{\Delta \text{Unlocked Outfits}}{\text{Price in USD}} \times \text{Average Outfit Score}$$
5. This formula surfaces affordable clothing items that unlock the highest number of coordinated outfits.

### 8.3 Generative Virtual Try-On (VTON) Pipeline
Recommending a retail item is more persuasive when the user can see how it looks on them.
1. The system stores an optional full-body reference photograph of the user.
2. When the user reviews a top-ranked store recommendation, the system calls a high-resolution diffusion try-on pipeline (such as IDM-VTON or TryOnDiffusion).
3. The model conditions on the user body pose, preserves the existing wardrobe items, and synthesizes the candidate store garment onto the user figure.
4. The application displays this photorealistic preview directly inside the lookbook card, creating a complete virtual shopping experience.

---

## 9. Summary of System Specifications

- **API Framework:** FastAPI on Python 3.11 with Uvicorn.
- **Message Broker:** Apache Kafka KRaft mode.
- **Primary Storage:** MinIO S3-compatible object store.
- **Relational Storage:** PostgreSQL 16 with asyncpg and SQLAlchemy.
- **Vision Models:** FashionCLIP (ViT-B/32), SegFormer-B4, YOLOv8, SAM.
- **Real-Time Notification:** PostgreSQL LISTEN/NOTIFY streamed via HTTP Server-Sent Events.
- **Interactive Showcase:** Streamlit with modular lookbook rendering.
- **Specification Compliance:** ASD-STE-100 Simplified Technical English.
