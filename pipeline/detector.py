from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt")

VIDEO_PATH = "people-detection.mp4"
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    print("ERROR: Could not open video.")
    exit()

width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps    = int(cap.get(cv2.CAP_PROP_FPS))

out = cv2.VideoWriter("output.mp4", cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

print(f"Video loaded: {width}x{height} at {fps} FPS")
print("Processing...")

frame_number = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame_number += 1
    results = model.track(frame, classes=[0], persist=True, verbose=False)
    person_count = 0
    if results[0].boxes is not None:
        for box in results[0].boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            track_id = int(box.id[0]) if box.id is not None else -1
            confidence = float(box.conf[0])
            if confidence > 0.5:
                person_count += 1
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"Person {track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, f"People: {person_count}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
    out.write(frame)
    if frame_number % 30 == 0:
        print(f"Frame {frame_number}: {person_count} people detected")

cap.release()
out.release()
print(f"Done! Processed {frame_number} frames. Output saved to output.mp4")
