```md
# Store Intelligence System

AI-powered retail analytics platform that converts CCTV footage into actionable business intelligence.

Built for **Purplle Tech Challenge 2026 — Round 2**

---

# Problem Statement

Retail stores generate large amounts of video data but very little actionable insight.

Store managers often cannot answer questions such as:

* Which zones attract the most shoppers?
* Where are customers dropping off before purchase?
* How many visitors actually convert?
* Which areas of the store are underutilized?
* Are billing queues causing abandonment?
* What is the relationship between footfall and revenue?

This project transforms raw CCTV footage into structured retail intelligence.

---

# Key Features
s
### Multi-Camera Visitor Tracking

* YOLOv8n person detection
* ByteTrack persistent tracking
* Cross-camera identity stitching
* Visitor journey reconstruction

### Retail Analytics

* Unique visitors
* Conversion rate
* Zone dwell time
* Billing queue analysis
* Funnel analytics
* Heatmap generation

### Real POS Integration

Uses actual Brigade Road store transactions to calculate:

* Revenue
* Top brands
* Top categories
* Top salespeople

### Anomaly Detection

Detects:

* DEAD_ZONE
* QUEUE_SPIKE
* HIGH_ABANDONMENT
* CONVERSION_DROP
* STALE_FEED

### AI Retail Copilot

Ask business questions in natural language:

```text
Why is conversion rate low?

Which zone has highest engagement?

Summarize today's performance.

```

Powered by Groq LLM. If the LLM is unavailable, a deterministic rule-based fallback automatically activates to avoid failed responses.

---

# System Architecture

```text
CCTV Cameras
      ↓
YOLOv8n + ByteTrack
      ↓
Lightweight Cross-Camera ReID
      ↓
Structured Event Generation
      ↓
SQLite Event Store
      ↓
FastAPI Analytics API
      ↓
Dashboard + AI Retail Copilot

```

### Dashboard Architecture

The dashboard is API-driven and continuously refreshes live analytics.

```text
dashboard/index.html
        ↓
dashboard/app.js
        ↓
HTTP fetch()
FastAPI API
        ↓
SQLite + POS Analytics
        ↓
JSON responses
        ↓
DOM updates + Chart.js rendering

```

Dashboard refreshes every 5 seconds using frontend polling.

---

# Detection Pipeline

## Step 1 — Person Detection

YOLOv8n processes all camera streams and detects people.

Output:

```text
Bounding Box
Confidence
Track ID
Camera ID
Timestamp

```

---

## Step 2 — Tracking

ByteTrack maintains identities across frames.

Example:

```text
Frame 30  → Person #7
Frame 300 → Person #7

```

This enables accurate dwell-time calculations.

---

## Step 3 — Cross-Camera ReID

The system performs lightweight heuristic cross-camera identity stitching using appearance signatures, temporal constraints, and camera-aware matching.

Example:

```text
CAM_ENTRY_01
      ↓
CAM_FLOOR_01
      ↓
CAM_BILLING_01

VIS_GLOBAL_0016

```

This allows multi-camera visitor journey analytics.

---

## Step 4 — Event Generation

Each observation becomes a structured event.

Example:

```json
{
  "event_id":"uuid",
  "visitor_id":"VIS_GLOBAL_0016",
  "camera_id":"CAM_FLOOR_01",
  "zone_id":"COSMETICS",
  "event_type":"ZONE_ENTER",
  "timestamp":"2026-03-03T14:01:21Z"
}

```

---

# API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | /health | System health and feed status |
| POST | /events/ingest | Batch event ingestion |
| GET | /stores/{id}/metrics | Visitor and conversion metrics |
| GET | /stores/{id}/funnel | Entry → Purchase funnel |
| GET | /stores/{id}/heatmap | Zone intensity analytics |
| GET | /stores/{id}/anomalies | Operational anomalies |
| GET | /cross-camera | Cross-camera stitched visitors |
| GET | /real-pos | Revenue and POS analytics |
| GET | /security | Security alerts and monitoring insights |
| POST | /ask | AI Retail Copilot |

---

# Example Analytics

### Store Metrics

```json
{
  "unique_visitors":229,
  "conversion_rate":0.0873,
  "transactions":20
}

```

### Funnel

```text
Entry           229
Zone Visit      227
Billing Queue    33
Purchase         20

```

### POS Intelligence

```text
Revenue: ₹34,331.71

Top Brand:
Faces Canada

Top Category:
Makeup

```

---

# Running the Project

## Option 1 — Docker (Recommended)

Recommended setup:

```bash
git clone <repo-url>
cd store-intelligence
docker compose up --build

```

This starts:

* FastAPI backend
* SQLite analytics layer
* Redpanda Kafka-compatible broker

Verified locally using:

```bash
docker compose up --build

```

Health endpoint returns HTTP 200.

Swagger Docs:

```text
http://localhost:8000/docs

```

Health Check:

```bash
curl http://localhost:8000/health

```

## Option 2 — Manual Setup

### Install Dependencies

```bash
pip install \
fastapi \
uvicorn \
pydantic \
python-dotenv \
groq \
pandas \
numpy \
requests \
kafka-python \
ultralytics \
opencv-python \
pytest \
httpx

```

### Run Detection Pipeline

```bash
python pipeline/detect.py

```

Output:

```text
data/events.jsonl

```

---

### Start API

```bash
uvicorn app.main:app --reload

```

---

### Open Dashboard

```text
dashboard/index.html

```

---

# Running Tests

```bash
python -m pytest tests/ -v

```

Current status:

```text
37 / 37 tests passing

```

Coverage includes:

* Event schema validation
* API correctness
* Anomaly detection
* Idempotency checks
* Edge cases

---

# Engineering Decisions

### Why YOLOv8n?

* Fast CPU inference
* Native ByteTrack support
* Best latency/accuracy tradeoff

### Why SQLite?

* Zero setup
* Reliable
* Challenge-friendly deployment

### Why Lightweight ReID?

Instead of heavy ReID models, the system uses:

* appearance signatures
* temporal constraints
* camera-aware matching

This keeps deployment CPU-friendly while still enabling cross-camera tracking.

---

# Project Structure

```text
store-intelligence/
├── docker-compose.yml     # Docker orchestration
├── requirements.txt       # Python dependencies
├── README.md              # Documentation
├── app/
│   ├── main.py
│   └── database.py
│
├── pipeline/
│   ├── detect.py          # Main pipeline orchestrator
│   ├── detector.py        # YOLOv8 detection + ByteTrack
│   ├── reid.py            # Cross-camera visitor stitching
│   ├── emit.py            # Event schema generation
│   ├── ingest_events.py   # Event ingestion utility
│   ├── pos_insights.py    # POS analytics
│   ├── real_pos.py        # Revenue & sales insights
│   ├── security_monitor.py
│   ├── producer.py
│   └── zones.py
│
├── data/
│   ├── CCTV videos
│   ├── store_layout.json
│   ├── events.jsonl
│   └── POS transactions
│
├── tests/
│   ├── test_pipeline.py
│   ├── test_metrics.py
│   └── test_anomalies.py
│
├── docs/
│   ├── DESIGN.md
│   └── CHOICES.md
│
├── dashboard/
│   ├── index.html         # Store analytics dashboard
│   ├── app.js             # Frontend API integration
│   └── styles.css         # Dashboard styling

```

---

# Future Improvements

* OSNet / TorchReID appearance embeddings
* Multi-store deployment
* Real-time RTSP camera ingestion
* TimescaleDB production backend
* Predictive conversion analytics
* Demand forecasting / staffing recommendations

---

# Author

Garv Gupta

Purplle Tech Challenge 2026 Submission

```

```