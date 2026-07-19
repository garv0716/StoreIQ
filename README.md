
# Store Intelligence System - Retail Analytics Platform

AI-powered retail analytics platform that converts CCTV footage into actionable business intelligence.

Built for **Purplle Tech Challenge 2026 — Round 2**

---

## Table of Contents

1. [What is Store Intelligence?](#1-what-is-store-intelligence)
2. [Project Overview](#2-project-overview)
3. [The Analytics Pipeline](#3-the-analytics-pipeline)
4. [API Endpoints & Features](#4-api-endpoints--features)
5. [Engineering Decisions](#5-engineering-decisions)
6. [Building and Running](#6-building-and-running)
7. [Understanding the Output](#7-understanding-the-output)
8. [Project Structure](#8-project-structure)

---

# Store Intelligence

## Live Demo

### Frontend
https://garv0716.github.io/store-intelligence/

### Backend API
https://store-intelligence-q9yn.onrender.com/docs



## 1. What is Store Intelligence?

Retail stores generate massive amounts of video data but extract very little actionable insight. Store managers often cannot answer basic questions about footfall, conversion drops, or underutilized zones.

**Store Intelligence** is an AI-powered system that uses computer vision to examine store visitors exactly like web analytics examines website visitors.

### Real-World Uses:
* **Store Managers:** Understand which zones (e.g., Cosmetics, Fragrances) attract the most shoppers.
* **Operations:** Detect if billing queues are causing checkout abandonment.
* **Sales Strategy:** Calculate exactly how many visitors actually convert to buyers.
* **Layout Optimization:** Identify "dead zones" where customers rarely go.

---

## 2. Project Overview

### Architecture Flow

```text
Retail CCTV Footage (.mp4)
      ↓
YOLOv8n + ByteTrack
      ↓
Cross-Camera ReID
      ↓
Event Generation
      ↓
SQLite Event Store
      ↓
FastAPI Analytics API
      ↓
Dashboard + AI Retail Copilot
```

The dashboard consumes API responses and refreshes automatically to provide near real-time visibility into store performance, visitor behavior, and operational anomalies.

### The Two Main Subsystems

| Component | Stack | Use Case |
| --- | --- | --- |
| **Detection Pipeline** | Python, YOLOv8n, OpenCV | Heavy lifting, frame processing, tracking |
| **Analytics API** | FastAPI, SQLite, Groq LLM | Fast querying, AI copilot, dashboard UI |

---

## 3. The Analytics Pipeline

### Step 1: Person Detection

YOLOv8n processes the incoming camera streams frame by frame.
*Output: Bounding Box, Confidence, Track ID, Camera ID, Timestamp*

### Step 2: Temporal Tracking

ByteTrack maintains persistent track identities across frames, enabling accurate dwell-time calculations within a single camera's view.

### Step 3: Identity Stitching (Lightweight Cross-Camera ReID)

Normally, ReID requires heavy, GPU-intensive deep learning models (like OSNet). Our system performs lightweight cross-camera identity stitching to preserve CPU deployment feasibility using:

1. Mean-color appearance signatures
2. Euclidean distance thresholding
3. Same-camera exclusion
4. Lightweight camera-aware matching

### Step 4: Event Generation

The pipeline translates pixel tracking into a structured, business-readable JSON event output to `data/events.jsonl`.

---

## 4. API Endpoints & Features

Once an event is generated, it flows into the backend architecture. To calculate conversion rates, the system merges video footfall with actual POS transaction data to automatically calculate Revenue, Top Brands, and Salespeople performance.

### Core API Endpoints

* **GET /health** - System health and STALE_FEED monitoring
* **POST /events/ingest** - Idempotent batch event ingestion
* **GET /stores/{id}/metrics** - Visitor, conversion and dwell analytics
* **GET /stores/{id}/funnel** - Entry → Purchase funnel metrics
* **GET /stores/{id}/anomalies** - Operational anomaly detection
* **GET /real-pos** - Revenue, brands, categories and salesperson insights
* **GET /cross-camera** - Cross-camera visitor stitching examples
* **GET /security** - Security monitoring analytics
* **POST /ask** - AI Retail Copilot

### Anomalies & AI Copilot

* **Anomaly Detection:** Continuously scans the event database to detect operational failures, such as `DEAD_ZONE` (0 footfall), `QUEUE_SPIKE`, and `CONVERSION_DROP`.
* **AI Copilot:** Users can query the `/ask` endpoint using natural language (e.g., *"Why is conversion rate low?"*). Powered by Groq, with a deterministic rule-based fallback to ensure high availability.

---

## 5. Engineering Decisions

* **Why YOLOv8n?** Chosen for its fast CPU inference and native ByteTrack support. It offers the best latency/accuracy tradeoff for edge deployments, performing efficiently on CPU-only hardware, including modern consumer laptops, without requiring bulky GPU rigs in the store.
* **Why SQLite?** Zero setup, highly reliable, and perfectly suited for the deployment constraints of this challenge.
* **Why Lightweight ReID?** Instead of heavy neural embeddings, the heuristic approach (mean-color signatures + distance thresholding + camera constraints) keeps the deployment CPU-friendly while still successfully enabling cross-camera tracking.

---

## 6. Building and Running

### Option 1 — Docker (Recommended)

```bash
git clone https://github.com/garv0716/store-intelligence.git
cd store-intelligence
docker compose up --build
```

Verified locally using:

```bash
docker compose up --build
```

- Health endpoint returns HTTP 200.
- Analytics endpoints load successfully.
- Dashboard loads and refreshes automatically.

This single command spins up the FastAPI backend, SQLite analytics layer, and Redpanda broker.

**Health Check:** `curl http://localhost:8000/health`

**Swagger Docs:** `http://localhost:8000/docs`

### Option 2 — Manual Setup

```bash
# 1. Install Dependencies
pip install fastapi uvicorn pydantic python-dotenv groq pandas numpy requests kafka-python ultralytics opencv-python pytest httpx

# 2. Run Detection Pipeline
python pipeline/detect.py

# 3. Start API
uvicorn app.main:app --reload

```

### Environment Setup

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

The AI Retail Copilot uses Groq for natural-language analytics. If the API key is not configured, AI responses may be unavailable and fallback behavior will be used where supported.

### Running Tests

To ensure system stability, complement manual validation with automated testing:

```bash
python -m pytest tests/ -v

```

*Current status: 37 / 37 tests passing.* Coverage includes event schema validation, idempotency checks, edge cases, and anomaly detection.

---

## 7. Understanding the Output

The system produces actionable intelligence:

**Store Metrics:**

```json
{
  "unique_visitors": 229,
  "conversion_rate": 0.0873,
  "transactions": 20
}

```

**Funnel Reconstruction:**

```text
Entry           229
Zone Visit      227
Billing Queue    33
Purchase         20

```

---

## 8. Project Structure

```text
store-intelligence/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── database.py
│
├── pipeline/
│   ├── __init__.py
│   ├── detect.py
│   ├── detector.py
│   ├── reid.py
│   ├── emit.py
│   ├── ingest_events.py
│   ├── producer.py
│   ├── pos_insights.py
│   ├── real_pos.py
│   ├── security_monitor.py
│   ├── zones.py
│   └── run.sh
│
├── data/
│   ├── Brigade_Bangalore_10_April_26.mp4
│   ├── store_layout.json
│   ├── pos_transactions.csv
│   └── events.jsonl
│
├── docs/
│   ├── DESIGN.md
│   └── CHOICES.md
│
├── tests/
│   ├── test_pipeline.py
│   ├── test_metrics.py
│   └── test_anomalies.py
│
├── app.js
├── docker-compose.yml
├── index.html
├── README.md
├── requirements.txt
└── style.css

```

---

*Author: Garv Gupta | Purplle Tech Challenge 2026 Submission*

```

```
