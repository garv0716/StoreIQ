# CHOICES.md — Three Key Engineering Decisions

## Decision 1: Detection Model — YOLOv8n + ByteTrack

### Options Considered
- **YOLOv8n** (chosen) — 6MB, 14 FPS on CPU, native ByteTrack integration via Ultralytics
- **YOLOv8m** — 15% better mAP, 50MB, 4 FPS on CPU — too slow for 20-minute clips
- **RT-DETR** — transformer-based, stronger on partial occlusion, no native tracking, requires separate tracker integration
- **MediaPipe Pose** — fast but no persistent tracking IDs, unsuitable for dwell time measurement

### What AI Suggested
The AI suggested RT-DETR for better handling of partial occlusion in the billing queue, citing its attention mechanism as superior to anchor-based detection in crowded scenes.

### What I Chose and Why
YOLOv8n with ByteTrack. I tested both on a 2-minute clip. RT-DETR detected 12% more partially-occluded persons but ran at 4 FPS vs YOLOv8n at 14 FPS — making 20-minute video processing impractical on CPU hardware within the challenge window. More importantly, ByteTrack is built into the Ultralytics library as a single parameter: `model.track(frame, persist=True)`. This tight integration means track IDs survive brief occlusion events, which is essential for accurate dwell time measurement.

### Trade-off Acknowledged
YOLOv8n struggles with severe occlusion in dense billing queues. Confidence scores are preserved in all events rather than suppressed, so consumers can apply their own confidence threshold filtering.

---

## Decision 2: Event Schema Design

### Options Considered
- **Flat JSON** — all fields at top level, simple but not extensible
- **Nested JSON with metadata block** (chosen) — typed metadata for queue_depth, sku_zone, session_seq
- **Apache Avro with schema registry** — production-grade schema evolution, requires separate registry service

### What AI Suggested
The AI suggested Avro for schema evolution guarantees and compatibility checking between producer and consumer versions.

### What I Chose and Why
JSON with a nested metadata block. Avro requires a schema registry service — a third Docker container and significant operational complexity for a 5-day challenge. Pydantic validation on the ingest endpoint achieves the same schema enforcement at ingestion time: invalid event_types are rejected with structured error responses, required fields are validated, and the endpoint returns per-event error details for partial batch failures.

The metadata block is intentionally extensible — new fields (e.g., basket_value, promo_id) can be added without breaking existing consumers. event_id is UUID v4 generated at emission time, ensuring global uniqueness across all cameras and sessions. The ingest endpoint is idempotent by event_id: calling it twice with the same payload produces accepted=0, duplicates=1 on the second call — safe for retry logic.

### Real Production Consideration
At 40 live stores with 3 cameras each, schema drift becomes a real risk. In that scenario, I would migrate to Avro with Confluent Schema Registry. The current JSON schema is designed to make that migration straightforward — the field names and types are stable.

---

## Decision 3: Storage Engine — SQLite over TimescaleDB

### Options Considered
- **SQLite** (chosen) — zero dependencies, file-based, full SQL support, compound indexes
- **TimescaleDB** — hypertable compression, continuous aggregates, purpose-built for time-series
- **Redis** — sub-millisecond reads, no complex query support, persistence requires configuration

### What AI Suggested
The AI recommended TimescaleDB, citing hypertable compression and continuous aggregates as valuable for the real-time metrics queries this API requires.

### What I Chose and Why
SQLite. The challenge FAQ explicitly states "SQLite is fine." More importantly, the acceptance gate requires docker compose up to start everything with no manual steps — every additional service is a potential failure point during judging. SQLite requires zero configuration and has no service to start.

SQLite fully supports all queries this API needs: GROUP BY zone_id for heatmap, COUNT DISTINCT visitor_id for funnel deduplication, MAX timestamp for health monitoring. With compound indexes on (store_id, event_type), (store_id, zone_id), and visitor_id, all queries return under 50ms on this event volume.

### What Would Make Me Change This Decision
40 live stores at 15 FPS = approximately 600 events per second sustained. SQLite's write lock becomes a bottleneck above 500 writes/second. At production scale, the migration path is: SQLite → TimescaleDB with pgBouncer connection pooling. The SQL queries in this codebase are standard ANSI SQL — no SQLite-specific syntax — making migration a connection string change.
