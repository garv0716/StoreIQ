# DESIGN.md — Store Intelligence System

## Architecture Overview

This system processes raw CCTV footage from a 5-camera retail store and produces a live analytics API. The pipeline has four stages: Detection, Event Streaming, Intelligence API, and Dashboard.
## Stage 1 — Detection Layer

YOLOv8n processes each video frame-by-frame with class filter `classes=[0]` (person only). ByteTrack assigns persistent track IDs across frames using Kalman filter prediction — so Person 7 in frame 30 is the same Person 7 in frame 300, even when briefly occluded.

Each camera maps to a zone topology:
- Entry cameras (CAM 1, CAM 5) → ENTRY_EXIT zone, ENTRY/EXIT events
- Floor cameras (CAM 2, CAM 3) → left/right zone split (SKINCARE/COSMETICS, HAIRCARE/FRAGRANCE)
- Billing camera (CAM 4) → BILLING zone, queue depth counting

## Stage 2 — Event Schema

Every event carries: UUID v4 event_id (globally unique, generated at emission), store_id, camera_id, visitor_id (VIS_xxxxxx format via MD5 hash of camera_id + track_id), event_type from a fixed 8-type catalogue, ISO-8601 UTC timestamp derived from frame number + base time offset, dwell_ms, is_staff boolean, confidence score, and a metadata block with queue_depth, sku_zone, and session_seq.

Event types emitted: ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, BILLING_QUEUE_JOIN, BILLING_QUEUE_ABANDON, REENTRY.

## Stage 3 — Intelligence API

FastAPI with Pydantic validation on all ingest events. POST /events/ingest is idempotent by event_id — SQLite PRIMARY KEY constraint handles deduplication silently. All customer-facing endpoints filter out is_staff=1 events.

Storage: SQLite with compound indexes on store_id, visitor_id, event_type, and zone_id. Zero external dependencies — the entire stack runs from a single docker compose up.

## Stage 4 — AI Retail Analyst

POST /ask accepts a natural language question, aggregates live metrics from all endpoints, and generates a business-language answer. Primary implementation uses Gemini API. A deterministic rule-based fallback activates automatically when the LLM is unavailable — ensuring the feature never returns a 500 error.

## Staff Detection

Heuristic: any track_id present in more than 70% of a camera's total frames is classified as staff. Customers enter, browse, and exit — staff are continuously present throughout the clip. All events for detected staff are retroactively marked is_staff=true and excluded from customer metrics. Accuracy: approximately 85% on these clips.

## Replay-Safe Anomaly Detection

The anomaly detection compares zone timestamps against the latest event timestamp in the database rather than the system clock. This prevents false DEAD_ZONE alerts caused by comparing synthetic 2026-03-03 replay timestamps against the real laptop clock (which would show every zone as dead for 60,000+ minutes).

## Cross-Camera Identity (Experimental)

A cross-camera deduplication prototype was built using a global visitor_id memory map with camera transition validation (ENTRY → FLOOR → BILLING) and a time window. Testing showed it improved identity continuity on clear single-person transitions but introduced overcounting in dense scenes, raising unique_visitors from 227 to 678. The stable per-camera hashing is used for the scored submission. The prototype is retained as a documented innovation.

## AI-Assisted Decisions

### 1. Staff Detection Method
The AI suggested using OSNet/torchreid for uniform-based staff classification. After evaluating the trade-off — 2GB additional model weight, no face/uniform data available due to anonymisation blur — I chose the frame-presence heuristic. It requires zero additional dependencies and achieves sufficient accuracy on these clips. The limitation (staff who step out briefly would be misclassified) is documented.

### 2. Storage Engine
The AI initially recommended TimescaleDB for time-series storage. I disagreed: TimescaleDB requires a Postgres service, adds Docker complexity, and the challenge FAQ explicitly states SQLite is acceptable. SQLite with indexed queries handles all required GROUP BY and window operations under 50ms with this event volume.

### 3. Anomaly Detection Approach
The AI suggested Isolation Forest on rolling footfall data for ML-based anomaly detection. I chose rule-based detection instead — the system has no historical baseline (single session replay), making statistical anomaly detection unreliable. Rule-based thresholds are fully explainable and directly map to business actions, which matters for the follow-up questions.


## Repository Structure Note
All API logic is consolidated in `app/main.py` rather than split across separate module files. This is intentional — for a single-store single-developer deployment, file consolidation reduces import complexity and makes the codebase easier to follow end-to-end. The PDF structure is a suggestion; this deviation is documented here per the guidelines.
