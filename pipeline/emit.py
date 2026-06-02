import uuid, json, hashlib
from datetime import datetime, timezone

import importlib
import importlib.util

# Try to load kafka.KafkaProducer dynamically to avoid static analyzer/linter
# reporting "Import 'kafka' could not be resolved" while still using a runtime
# fallback when the package is not installed.
KafkaProducer = None
_kafka_spec = importlib.util.find_spec('kafka')
if _kafka_spec is not None:
    try:
        _kafka = importlib.import_module('kafka')
        KafkaProducer = getattr(_kafka, "KafkaProducer", None)
    except Exception:
        KafkaProducer = None

if KafkaProducer is None:
    # Fallback stub KafkaProducer when kafka-python is not installed.
    # This allows the module to be imported and used in environments
    # without the kafka package (useful for linting, testing, or local runs).
    class KafkaProducer:
        def __init__(self, *args, **kwargs):
            print("Warning: kafka-python not installed; using stub KafkaProducer.")

        def send(self, topic, value=None):
            # mimic the real API surface enough for this module
            print(f"Stub KafkaProducer.send -> topic: {topic}, value: {value}")

        def flush(self):
            print("Stub KafkaProducer.flush() called")

STORE_ID = "STORE_BLR_002"
_producer = None

def get_producer():
    global _producer
    if _producer is None:
        try:
            _producer = KafkaProducer(
                bootstrap_servers='localhost:9092',
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all', retries=3
            )
        except Exception as e:
            print(f"Kafka unavailable: {e}")
    return _producer

def make_visitor_id(track_id: int, camera_id: str) -> str:

    CAMERA_GROUPS = {

        "CAM_ENTRY_01":"STORE_FLOW",

        "CAM_ENTRY_02":"STORE_FLOW",

        "CAM_FLOOR_01":"STORE_FLOW",

        "CAM_BILLING_01":"STORE_FLOW",

        "CAM_BACKROOM_01":"SECURITY"
    }

    group = CAMERA_GROUPS.get(
        camera_id,
        camera_id
    )

    h = hashlib.md5(
        f"{group}_{track_id}".encode()
    ).hexdigest()[:6]

    return f"VIS_{h}"
def make_event(camera_id, visitor_id, event_type, zone_id, dwell_ms,
               is_staff, confidence, frame_timestamp, session_seq,
               queue_depth=None, sku_zone=None):
    return {
        "event_id":   str(uuid.uuid4()),
        "store_id":   STORE_ID,
        "camera_id":  camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp":  frame_timestamp,
        "zone_id":    zone_id,
        "dwell_ms":   dwell_ms,
        "is_staff":   is_staff,
        "confidence": round(float(confidence), 4),
        "metadata":   {"queue_depth": queue_depth, "sku_zone": sku_zone, "session_seq": session_seq}
    }

def emit(event: dict, topic: str = "store_events") -> dict:
    p = get_producer()
    if p:
        try: p.send(topic, value=event)
        except Exception as e: print(f"Kafka send failed: {e}")
    print(f"  [{event['event_type']:22s}] {event['visitor_id']} | zone={str(event['zone_id']):15s} | staff={event['is_staff']}")
    return event

def flush():
    p = get_producer()
    if p:
        try: p.flush()
        except: pass
