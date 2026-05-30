# Store Intelligence System
AI-powered retail store analytics from CCTV footage.
Purplle Tech Challenge 2026 — Round 2

## Setup in 5 Commands
```bash
git clone <your-repo-url>
cd store-intelligence
pip install ultralytics fastapi uvicorn pydantic kafka-python pytest httpx google-generativeai
python pipeline/detect.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## How to Run the Detection Pipeline
Place CAM 1.mp4 through CAM 5.mp4 in the `data/` folder, then:
```bash
python pipeline/detect.py
# Processes all 5 cameras → outputs data/events.jsonl
# Takes ~10 minutes for 20-min clips on CPU
```

## Ingest Events into API
```bash
# With API running in another terminal:
python pipeline/ingest_events.py
# Ingests events in batches of 100, idempotent — safe to run twice
```

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Service status, STALE_FEED detection |
| POST | /events/ingest | Batch ingest up to 500 events, idempotent by event_id |
| GET | /stores/STORE_BLR_002/metrics | Unique visitors, conversion rate, dwell per zone |
| GET | /stores/STORE_BLR_002/funnel | Entry → Zone → Billing → Purchase with drop-off % |
| GET | /stores/STORE_BLR_002/heatmap | Zone intensity 0–100 with data_confidence flag |
| GET | /stores/STORE_BLR_002/anomalies | QUEUE_SPIKE, DEAD_ZONE, CONVERSION_DROP, HIGH_ABANDONMENT |
| POST | /ask | Natural language retail analytics (AI + rule-based fallback) |

## Quick Test
```bash
curl http://localhost:8000/health
curl http://localhost:8000/stores/STORE_BLR_002/metrics
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is conversion rate low?"}'
```

## Run Tests
```bash
python -m pytest tests/ -v
# 37 tests — pipeline schema, API correctness, anomaly structure, edge cases
```

## Docker
```bash
docker compose up
# Starts Redpanda (Kafka) + API on port 8000
# No manual steps beyond this
```

## Architecture
- **Detection**: YOLOv8n + ByteTrack — person detection and persistent tracking
- **Staff detection**: Frame-presence heuristic (>70% of frames = staff, excluded from metrics)
- **Storage**: SQLite with compound indexes — zero external dependencies
- **Streaming**: Kafka (Redpanda) for real-time event emission
- **AI layer**: Gemini API with deterministic rule-based fallback

See `docs/DESIGN.md` for full architecture and AI-assisted decisions.
See `docs/CHOICES.md` for three key engineering decisions with trade-off reasoning.

## Project Structure
store-intelligence/
├── pipeline/
│   ├── detect.py          # Main detection + tracking + event emission
│   ├── emit.py            # Event schema (required format)
│   └── ingest_events.py   # Loads JSONL events into API
├── app/
│   ├── main.py            # FastAPI — all 6 endpoints
│   └── database.py        # SQLite layer
├── tests/
│   ├── test_pipeline.py   # Event schema tests
│   ├── test_metrics.py    # API endpoint tests
│   └── test_anomalies.py  # Anomaly detection tests
├── data/
│   ├── store_layout.json  # Zone definitions, camera mapping
│   └── pos_transactions.csv
├── docs/
│   ├── DESIGN.md          # Architecture + AI-assisted decisions
│   └── CHOICES.md         # 3 decisions with full reasoning
├── docker-compose.yml
└── README.md
