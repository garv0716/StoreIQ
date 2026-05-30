"""
After running detect.py, run this to load all events into the API.
"""
import json, requests, sys

EVENTS_FILE = "data/events.jsonl"
API_URL     = "http://localhost:8000/events/ingest"
BATCH_SIZE  = 100

with open(EVENTS_FILE) as f:
    events = [json.loads(line) for line in f if line.strip()]

print(f"Loaded {len(events)} events from {EVENTS_FILE}")
total_accepted = 0

for i in range(0, len(events), BATCH_SIZE):
    batch = events[i:i+BATCH_SIZE]
    try:
        r = requests.post(API_URL, json={"events": batch})
        data = r.json()
        total_accepted += data.get("accepted", 0)
        print(f"  Batch {i//BATCH_SIZE+1}: accepted={data['accepted']} duplicates={data['duplicates']} rejected={data['rejected']}")
    except Exception as e:
        print(f"  Batch {i//BATCH_SIZE+1} FAILED: {e}")

print(f"\nDone! Total accepted: {total_accepted}/{len(events)}")
