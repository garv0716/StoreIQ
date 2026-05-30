from ultralytics import YOLO
import cv2
import json
from producer import send_zone_event, send_anomaly_event, flush

model = YOLO("yolov8n.pt")

ZONES = {
    "Entrance":      [0,   0,   192, 216],
    "Cosmetics":     [192, 0,   384, 216],
    "Skincare":      [384, 0,   576, 216],
    "Billing":       [576, 0,   768, 216],
    "General Floor": [0,   216, 768, 432],
}

ZONE_COLORS = {
    "Entrance":      (0,   200, 150),
    "Cosmetics":     (150, 0,   200),
    "Skincare":      (0,   100, 255),
    "Billing":       (0,   165, 255),
    "General Floor": (200, 200, 0  ),
}

LOITER_THRESHOLD = 5.0

person_data = {}
zone_visits = []

def get_zone(cx, cy):
    for zone_name, (x1, y1, x2, y2) in ZONES.items():
        if x1 <= cx <= x2 and y1 <= cy <= y2:
            return zone_name
    return "Unknown"

def draw_zones(frame):
    for zone_name, (x1, y1, x2, y2) in ZONES.items():
        color = ZONE_COLORS[zone_name]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, zone_name, (x1 + 5, y1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return frame

cap = cv2.VideoCapture("people-detection.mp4")
width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps    = int(cap.get(cv2.CAP_PROP_FPS))

out = cv2.VideoWriter("output_zones.mp4",
                      cv2.VideoWriter_fourcc(*"mp4v"),
                      fps, (width, height))

print(f"Video: {width}x{height} at {fps} FPS")
print("Processing with Kafka event streaming...")

frame_number  = 0
all_events    = []

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_number += 1
    current_time  = frame_number / fps

    frame = draw_zones(frame)

    results = model.track(frame, classes=[0], persist=True, verbose=False)

    zone_counts = {zone: 0 for zone in ZONES}

    if results[0].boxes is not None:
        for box in results[0].boxes:
            if box.id is None:
                continue

            track_id = int(box.id[0])
            conf     = float(box.conf[0])
            if conf < 0.5:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            current_zone = get_zone(cx, cy)

            if track_id not in person_data:
                person_data[track_id] = {
                    "id":              track_id,
                    "current_zone":    current_zone,
                    "zone_entry_time": current_time,
                    "zones_visited":   []
                }
            else:
                prev_zone  = person_data[track_id]["current_zone"]
                entry_time = person_data[track_id]["zone_entry_time"]
                dwell_time = round(current_time - entry_time, 2)

                if current_zone != prev_zone:
                    # Send zone visit event to Kafka
                    event = send_zone_event(
                        track_id, prev_zone,
                        entry_time, current_time, dwell_time
                    )
                    all_events.append(event)
                    zone_visits.append(event)

                    # Check for loitering anomaly
                    if dwell_time > LOITER_THRESHOLD:
                        send_anomaly_event(
                            track_id, prev_zone,
                            "loitering", dwell_time
                        )

                    person_data[track_id]["current_zone"]    = current_zone
                    person_data[track_id]["zone_entry_time"] = current_time
                    person_data[track_id]["zones_visited"].append(prev_zone)

                # Check ongoing loitering even without zone change
                elif dwell_time > LOITER_THRESHOLD:
                    if not person_data[track_id].get("loiter_alerted"):
                        send_anomaly_event(
                            track_id, current_zone,
                            "loitering", dwell_time
                        )
                        person_data[track_id]["loiter_alerted"] = True

            if current_zone in zone_counts:
                zone_counts[current_zone] += 1

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"P{track_id} | {current_zone}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            cv2.circle(frame, (cx, cy), 4, (0, 255, 0), -1)

    y_pos = height - 90
    cv2.rectangle(frame, (0, y_pos - 10), (width, height), (0, 0, 0), -1)
    cv2.putText(frame, "Live zone occupancy:", (10, y_pos + 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    x_offset = 10
    for zone_name, count in zone_counts.items():
        color = ZONE_COLORS.get(zone_name, (255, 255, 255))
        cv2.putText(frame, f"{zone_name}:{count}", (x_offset, y_pos + 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        x_offset += 150

    out.write(frame)

    if frame_number % 60 == 0:
        print(f"Frame {frame_number} | Zones: {zone_counts}")

cap.release()
out.release()
flush()

with open("zone_visits.json", "w") as f:
    json.dump(zone_visits, f, indent=2)

print("\n===== SUMMARY =====")
print(f"Frames processed : {frame_number}")
print(f"People tracked   : {len(person_data)}")
print(f"Events sent      : {len(all_events)}")
print(f"Kafka topics     : zone_events, anomaly_events")
print("Output saved to  : output_zones.mp4")
