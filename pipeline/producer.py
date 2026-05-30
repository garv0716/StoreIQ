from kafka import KafkaProducer
import json
from datetime import datetime

# Connect to Kafka running in Docker
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def send_zone_event(person_id, zone, entry_time, exit_time, dwell_seconds):
    """Send a zone visit event to Kafka"""
    event = {
        "event_id":      f"{person_id}_{zone}_{int(entry_time)}",
        "event_type":    "zone_visit",
        "timestamp":     datetime.now().isoformat(),
        "person_id":     person_id,
        "zone":          zone,
        "entry_time":    entry_time,
        "exit_time":     exit_time,
        "dwell_seconds": dwell_seconds
    }
    producer.send('zone_events', value=event)
    print(f"  KAFKA → Person {person_id} | {zone} | {dwell_seconds}s dwell")
    return event

def send_anomaly_event(person_id, zone, anomaly_type, dwell_seconds):
    """Send an anomaly alert event to Kafka"""
    event = {
        "event_id":      f"anomaly_{person_id}_{int(dwell_seconds)}",
        "event_type":    "anomaly",
        "timestamp":     datetime.now().isoformat(),
        "person_id":     person_id,
        "zone":          zone,
        "anomaly_type":  anomaly_type,
        "dwell_seconds": dwell_seconds,
        "severity":      "HIGH" if dwell_seconds > 30 else "MEDIUM"
    }
    producer.send('anomaly_events', value=event)
    print(f"  ANOMALY ALERT → Person {person_id} loitering in {zone} for {dwell_seconds}s")
    return event

def flush():
    """Make sure all messages are sent"""
    producer.flush()
