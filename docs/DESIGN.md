```md
# DESIGN.md — Store Intelligence System

## Architecture Overview

Store Intelligence transforms raw retail CCTV footage into actionable business analytics. The system processes multi-camera video streams, generates structured retail events, performs visitor analytics, correlates activity with real POS transactions, and exposes insights through APIs, dashboards, and a natural-language retail copilot.

The architecture follows a decoupled, event-driven pipeline:

```text
Retail CCTV Cameras
        ↓
[ The Vision Layer ] (YOLOv8n + ByteTrack + ReID)
        ↓
[ The Ingestion Layer ] (Event Generation + SQLite)
        ↓
[ The Intelligence API ] (FastAPI + AI Copilot + POS Analytics)
        ↓
Dashboard & End-User Queries

```

Each layer is intentionally decoupled so detection, storage, analytics, and presentation can evolve independently.

---

## 1. The Vision Layer

This layer handles pixel-to-data translation.

### Detection & Tracking

Person detection is performed using **YOLOv8n** restricted to the person class (`classes=[0]`).
Tracking is handled by **ByteTrack** via Ultralytics persistent tracking (`model.track(..., persist=True)`).
This enables persistent identities across frames, occlusion recovery, dwell-time measurement, and visitor journey reconstruction.

### Topology & Zone Mapping

The store is modeled as logical retail zones based on camera field-of-view:

* **Entry Cameras:** Handle `ENTRY_EXIT` monitoring.
* **Floor Cameras:** Handle engagement zones (`SKINCARE`, `COSMETICS`, `FRAGRANCE`, etc.).
* **Billing Cameras:** Handle queue monitoring and checkout analytics.

### Cross-Camera Identity Stitching (ReID)

A lightweight Re-Identification (ReID) layer was implemented to track shoppers across multiple cameras. To preserve CPU-only deployment feasibility, I utilized a heuristic approach rather than deep OSNet embeddings:

1. Bounding-box crop extracted and resized to 32×32.
2. Mean RGB signature computed.
3. Euclidean distance matching gated by a similarity threshold.
4. Same-camera exclusion applied to prevent merging distinct concurrent tracks.

Matching uses lightweight mean-color appearance signatures, Euclidean distance thresholding, and same-camera exclusion to reduce false merges. The design intentionally prioritizes CPU feasibility over heavy deep-learning embeddings.

### Staff Detection

A lightweight heuristic identifies staff members without requiring custom model training. If an individual appears in >70% of a camera's frames, they are classified as staff. Detected staff are automatically excluded from conversion calculations, funnel metrics, and visitor counts.

---

## 2. The Ingestion & Storage Layer

### Event Generation

All analytics are built from structured events. Each event explicitly contains core identifiers (`event_id`, `store_id`, `camera_id`, `visitor_id`, `zone_id`), analytics fields (`event_type`, `confidence`, `is_staff`, `timestamp`), and an extensible metadata block:

```json
{
  "queue_depth": 4,
  "sku_zone": "COSMETICS",
  "session_seq": 12
}

```

This design supports future schema evolution (e.g., adding promo IDs or basket values) without breaking downstream consumers.

### Storage

Storage is implemented using **SQLite**.

* **Why:** Zero infrastructure dependencies, single-file deployment, and challenge-friendly `docker compose` setup.
* **Performance:** SQLite uses indexed querying on commonly filtered analytics fields such as store identifiers, visitor identifiers, zones, and event types. The schema intentionally avoids SQLite-specific syntax to simplify future migration to PostgreSQL / TimescaleDB.

---

## 3. The Intelligence API Layer

Implemented using **FastAPI** with **Pydantic validation**.

### Idempotent Event Ingestion (`POST /events/ingest`)

The ingestion API is replay-safe. Events are uniquely identified by a UUID v4 `event_id`. Duplicate ingestion attempts are safely ignored, guaranteeing retry safety and preventing duplicate analytics.

### Real POS Intelligence (`GET /real-pos`)

The platform combines shopper behavior with actual purchase outcomes from the provided POS data (`pos_transactions.csv`). It outputs total revenue, top brands, and top categories. This connects CCTV shopper behavior directly to the business bottom line.

### Security & Anomaly Detection (`GET /stores/{id}/anomalies`)

The system continuously evaluates operational anomalies like `QUEUE_SPIKE`, `DEAD_ZONE`, and `CONVERSION_DROP`. A replay-safe design compares event timestamps against the *latest observed event* rather than the system clock to prevent false alerts during video replays.

### AI Retail Copilot (`POST /ask`)

The platform includes a natural-language analytics assistant. It retrieves live operational context from the database and passes it to a **Groq-powered LLM inference layer**. Managers can ask *"Why is conversion rate low?"* and receive business-readable reasoning. A deterministic rule-based fallback ensures graceful degradation if API limits are hit.

### Dashboard Layer

Frontend dashboard implemented using:

* `dashboard/index.html`
* `dashboard/app.js`
* REST API fetch polling (5-second refresh)
* Chart.js visualizations

The dashboard consumes metrics, funnel, anomaly, security, POS analytics, cross-camera, and AI copilot endpoints.

---

## 4. AI-Assisted Decisions

In building this system, I used LLM tools including ChatGPT and Copilot as architecture and testing assistants. Here is how they shaped the design:

1. **Writing the Cross-Camera ReID Logic (Overrode & Agreed)**
* *Interaction:* I asked an LLM to design a cross-camera tracking pipeline. It immediately suggested implementing TorchReID with OSNet embeddings.
* *Decision:* I **overrode** the model suggestion because deep ReID is too computationally expensive for the CPU-only constraints of edge store deployments. However, I **agreed** with the AI's provided mathematical structure for computing and matching Euclidean distances, which I adapted into my lightweight mean-RGB heuristic.


2. **Staff Detection Implementation (Overrode)**
* *Interaction:* I prompted an LLM to solve the staff exclusion problem based on the prompt's edge cases. It suggested fine-tuning YOLOv8 on staff uniforms.
* *Decision:* I **overrode** this approach. Fine-tuning requires labeled data collection and reduces out-of-the-box generalization across unseen stores. Instead, I prompted the LLM to help me write a purely temporal, rule-based heuristic (tracking total presence duration across frames).


3. **Generating Edge-Case Tests (Agreed)**
* *Interaction:* I used LLM assistants to scaffold my `pytest` suite, specifically feeding it my anomaly detection thresholds and asking it to generate mock `events.jsonl` payloads that simulate a `DEAD_ZONE` or a `QUEUE_SPIKE`.
* *Decision:* I **agreed** with the generated test payloads, which helped me achieve 37/37 passing tests rapidly and ensured my API correctly handled partial occlusions and group entries mathematically.



---

## 5. Scalability & Repository Considerations

### Scalability Path

The architecture intentionally supports future evolution:

* YOLOv8n CPU inference → GPU-backed inference workers
* SQLite → PostgreSQL / TimescaleDB
* Replay / local ingestion → expanded production-grade event streaming using Redpanda/Kafka topics.

Because layers communicate exclusively through structured events, these upgrades can be introduced without rewriting business logic.

### Repository Structure Note

The API layer is intentionally consolidated inside `app/main.py`. For a single-developer challenge environment, this improves readability and reduces module complexity. Supporting functionality (ReID, tracking, POS insights) remains strictly separated in the `pipeline/` directory.

---

*Author: Garv Gupta | Purplle Tech Challenge 2026 Submission*

```

```