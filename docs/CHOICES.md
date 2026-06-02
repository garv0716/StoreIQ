# CHOICES.md — Three Key Engineering Decisions

---

# Decision 1: Detection Pipeline — YOLOv8n + ByteTrack

## Options Considered

### **YOLOv8n (Chosen)**

* ~6 MB model size
* ~14 FPS on CPU during testing
* Native ByteTrack integration through Ultralytics
* Simple deployment and minimal dependencies

### **YOLOv8m**

* ~15% higher mAP than YOLOv8n
* ~50 MB model size
* ~4 FPS on CPU
* Higher accuracy but impractical latency for 20-minute video processing

### **RT-DETR**

* Transformer-based detector
* Stronger performance on partial occlusion and crowded scenes
* Requires separate tracking integration
* Computationally heavier on CPU-only hardware

### **MediaPipe Pose**

* Lightweight and fast
* Good for skeletal tracking
* No persistent identity tracking
* Unsuitable for dwell analytics and visitor journey reconstruction

---

## What AI Suggested

The AI recommended **RT-DETR**, highlighting its attention-based architecture as better suited for partial occlusion in crowded retail environments, particularly billing queues.

---

## What I Chose and Why

I selected **YOLOv8n + ByteTrack**.

I benchmarked both approaches on a 2-minute retail clip. RT-DETR recovered roughly **12% more partially-occluded detections**, but processed video at **~4 FPS** compared to **~14 FPS for YOLOv8n** on CPU hardware.

For this challenge, end-to-end throughput mattered more than incremental detection accuracy.

An important practical advantage is Ultralytics' native tracking interface:

```python
model.track(frame, persist=True)
```

ByteTrack integration is effectively one parameter instead of a multi-component tracking pipeline.

Persistent track IDs survive brief occlusions and temporary detector instability, which is essential for:

* dwell time computation
* queue analytics
* funnel stage attribution
* cross-camera identity stitching

The chosen stack optimized **engineering simplicity, runtime feasibility, and stable tracking behavior**.

---

## Trade-off Acknowledged

YOLOv8n underperforms under severe crowding and dense billing-queue occlusion.

Instead of aggressively suppressing uncertain detections, the pipeline preserves confidence scores in emitted events so downstream consumers can apply workload-specific filtering policies.

In a production deployment with GPU availability, I would reevaluate stronger detectors such as RT-DETR or YOLOv8m.

---

# Decision 2: Event Schema Design

## Options Considered

### **Flat JSON**

* Minimal structure
* Easy debugging
* Limited extensibility
* Increasing risk of schema clutter over time

### **Nested JSON with Metadata Block (Chosen)**

* Clear separation of core fields and auxiliary attributes
* Extensible without breaking consumers
* Compatible with validation tooling

### **Apache Avro + Schema Registry**

* Strong schema evolution guarantees
* Versioned contracts
* Consumer compatibility checking
* Operationally heavier

---

## What AI Suggested

The AI recommended **Apache Avro**, emphasizing schema evolution guarantees, version compatibility, and safer producer-consumer evolution.

---

## What I Chose and Why

I chose **JSON with a nested metadata block**.

Avro would introduce an additional infrastructure dependency (Schema Registry service), increasing operational complexity for a short-duration challenge.

Instead, schema enforcement occurs at the API boundary through **Pydantic validation**.

The ingest endpoint validates:

* required fields
* event types
* payload structure
* field typing

Invalid events are rejected with structured validation errors, while partial batch failures remain observable.

The metadata section is intentionally extensible:

```json
"metadata": {
  "queue_depth": 3,
  "sku_zone": "COSMETICS",
  "session_seq": 14
}
```

Future fields such as:

* basket_value
* promo_id
* staff_interaction
* campaign_source

can be added without modifying the core event contract.

Each event receives a **UUIDv4 event_id** at emission time, guaranteeing uniqueness across:

* cameras
* sessions
* stores

The ingestion API is also **idempotent by event_id**, allowing safe retries without duplicate amplification.

---

## Real Production Consideration

At scale (e.g., **40 stores × 3 cameras per store**), schema drift becomes a legitimate operational concern.

Under those conditions, I would migrate toward:

**JSON → Avro → Confluent Schema Registry**

The current schema intentionally uses stable naming and typing conventions to make that migration low-friction.

---

# Decision 3: Storage Layer — SQLite over TimescaleDB

## Options Considered

### **SQLite (Chosen)**

* Zero setup
* File-based deployment
* Full SQL support
* No service orchestration required

### **TimescaleDB**

* Purpose-built for time-series analytics
* Hypertables
* Compression
* Continuous aggregates
* Operational overhead

### **Redis**

* Extremely low latency
* Excellent cache performance
* Weak analytical query capabilities
* Additional persistence configuration required

---

## What AI Suggested

The AI recommended **TimescaleDB**, citing its suitability for real-time analytical workloads and efficient handling of time-series event streams.

---

## What I Chose and Why

I selected **SQLite**.

The challenge explicitly permits SQLite, and the deployment requirement prioritizes:

```bash
docker compose up
```

with minimal manual setup.

Every additional service increases:

* configuration complexity
* startup failure risk
* judging friction

SQLite satisfies all required analytical workloads.

The API depends primarily on:

```sql
GROUP BY zone_id
COUNT(DISTINCT visitor_id)
MAX(timestamp)
```

Using compound indexes on:

```text
(store_id, event_type)
(store_id, zone_id)
(visitor_id)
```

all tested queries complete comfortably under **50 ms** on current event volume.

For a challenge-scale deployment, SQLite maximizes **reliability, portability, and operational simplicity**.

---

## When I Would Change This Decision

At production scale:

```text
40 live stores
3 cameras/store
15 FPS sustained ingestion
≈ 600+ events/sec
```

SQLite's write locking becomes a bottleneck.

The migration path would be:

```text
SQLite
↓
TimescaleDB
↓
pgBouncer connection pooling
```

The codebase intentionally uses standard ANSI SQL rather than SQLite-specific syntax, minimizing migration effort to largely a connection-layer change.

The current decision optimizes for **challenge constraints**, not permanent infrastructure commitment.
