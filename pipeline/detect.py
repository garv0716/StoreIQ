"""
detect.py — Processes all 5 CAM files and emits structured events.
Run: python pipeline/detect.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from datetime import datetime, timezone, timedelta
from ultralytics import YOLO
from pipeline.emit import make_visitor_id, make_event, emit, flush, STORE_ID

LAYOUT_PATH     = "data/store_layout.json"
EVENTS_OUT      = "data/events.jsonl"
STAFF_THRESHOLD = 0.70
VIDEO_BASE_TIME = datetime(2026, 3, 3, 10, 0, 0, tzinfo=timezone.utc)

with open(LAYOUT_PATH) as f:
    LAYOUT = json.load(f)

ZONE_BY_ID = {z["zone_id"]: z for z in LAYOUT["zones"]}
model = YOLO("yolov8n.pt")

def get_zone(cx, cy, width, height, cam_type, cam_id):
    if cam_type == "billing":   return "BILLING", None
    if cam_type == "entry":     return "ENTRY_EXIT", None
    if cam_type == "main_floor":
        z = ("SKINCARE" if cx < width//2 else "COSMETICS") if cam_id == "CAM_FLOOR_01" \
            else ("HAIRCARE" if cx < width//2 else "FRAGRANCE")
        return z, ZONE_BY_ID.get(z, {}).get("sku_zone")
    return "UNKNOWN", None

def ts(frame_num, fps, base):
    return (base + timedelta(seconds=frame_num/fps)).strftime("%Y-%m-%dT%H:%M:%SZ")

class Person:
    def __init__(self, track_id, cam_id):
        self.track_id    = track_id
        self.visitor_id  = make_visitor_id(track_id, cam_id)
        self.is_staff    = False
        self.current_zone      = None
        self.zone_entry_frame  = None
        self.session_seq       = 0
        self.frames_seen       = 0
        self.last_dwell_ms     = 0

def process_camera(cam_file, cam_info, all_events, hour_offset=0):
    cam_id   = cam_info["camera_id"]
    cam_type = cam_info["type"]
    path     = f"data/{cam_file}"
    base     = VIDEO_BASE_TIME + timedelta(hours=hour_offset)

    if not os.path.exists(path):
        print(f"SKIP: {path} not found"); return

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"ERROR opening {path}"); return

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = int(cap.get(cv2.CAP_PROP_FPS)) or 15
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"\n{'='*55}\nCamera: {cam_id} ({cam_type}) | {W}x{H}@{fps}fps | {total} frames\n{'='*55}")

    persons, exited_ids, frame_counts, cam_events = {}, set(), {}, []
    frame_num = 0

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame_num += 1
        now = ts(frame_num, fps, base)
        results = model.track(frame, classes=[0], persist=True, verbose=False)
        active = set()
        billing_count = 0

        if results[0].boxes is not None:
            for box in results[0].boxes:
                if box.id is None: continue
                tid  = int(box.id[0])
                conf = float(box.conf[0])
                if conf < 0.4: continue
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                cx,cy = (x1+x2)//2, (y1+y2)//2
                active.add(tid)
                frame_counts[tid] = frame_counts.get(tid,0)+1
                zone_id, sku = get_zone(cx, cy, W, H, cam_type, cam_id)
                if zone_id == "BILLING": billing_count += 1

                if tid not in persons:
                    p = Person(tid, cam_id)
                    persons[tid] = p
                    etype = "REENTRY" if p.visitor_id in exited_ids else "ENTRY"
                    p.session_seq += 1
                    ev = make_event(cam_id, p.visitor_id, etype,
                        "ENTRY_EXIT" if cam_type=="entry" else zone_id,
                        0, False, conf, now, p.session_seq)
                    emit(ev); cam_events.append(ev)

                p = persons[tid]
                p.frames_seen += 1

                if p.current_zone is None:
                    p.current_zone = zone_id
                    p.zone_entry_frame = frame_num
                    p.session_seq += 1
                    ev = make_event(cam_id,p.visitor_id,"ZONE_ENTER",zone_id,0,p.is_staff,conf,now,p.session_seq,sku_zone=sku)
                    emit(ev); cam_events.append(ev)

                elif zone_id != p.current_zone:
                    dwell = int(((frame_num - p.zone_entry_frame)/fps)*1000)
                    old_sku = ZONE_BY_ID.get(p.current_zone,{}).get("sku_zone")
                    p.session_seq += 1
                    ev = make_event(cam_id,p.visitor_id,"ZONE_EXIT",p.current_zone,dwell,p.is_staff,conf,now,p.session_seq,sku_zone=old_sku)
                    emit(ev); cam_events.append(ev)
                    if zone_id=="BILLING" and billing_count>1:
                        p.session_seq += 1
                        ev = make_event(cam_id,p.visitor_id,"BILLING_QUEUE_JOIN","BILLING",0,p.is_staff,conf,now,p.session_seq,queue_depth=billing_count)
                        emit(ev); cam_events.append(ev)
                    p.session_seq += 1
                    ev = make_event(cam_id,p.visitor_id,"ZONE_ENTER",zone_id,0,p.is_staff,conf,now,p.session_seq,sku_zone=sku)
                    emit(ev); cam_events.append(ev)
                    p.current_zone = zone_id
                    p.zone_entry_frame = frame_num
                    p.last_dwell_ms = 0

                else:
                    dwell = int(((frame_num - p.zone_entry_frame)/fps)*1000)
                    if dwell >= 30000 and (dwell - p.last_dwell_ms) >= 30000:
                        p.session_seq += 1
                        ev = make_event(cam_id,p.visitor_id,"ZONE_DWELL",zone_id,dwell,p.is_staff,conf,now,p.session_seq,sku_zone=sku)
                        emit(ev); cam_events.append(ev)
                        p.last_dwell_ms = dwell

        for tid in list(persons.keys()):
            if tid not in active:
                p = persons[tid]
                now_exit = ts(frame_num, fps, base)
                if p.current_zone:
                    dwell = int(((frame_num - p.zone_entry_frame)/fps)*1000)
                    p.session_seq += 1
                    etype = "BILLING_QUEUE_ABANDON" if p.current_zone=="BILLING" else "ZONE_EXIT"
                    ev = make_event(cam_id,p.visitor_id,etype,p.current_zone,dwell,p.is_staff,0.5,now_exit,p.session_seq)
                    emit(ev); cam_events.append(ev)
                p.session_seq += 1
                ev = make_event(cam_id,p.visitor_id,"EXIT","ENTRY_EXIT" if cam_type=="entry" else None,0,p.is_staff,0.5,now_exit,p.session_seq)
                emit(ev); cam_events.append(ev)
                exited_ids.add(p.visitor_id)
                del persons[tid]

        if frame_num % 100 == 0:
            print(f"  Frame {frame_num}/{total} | Active: {len(persons)} | Events so far: {len(cam_events)}")

    cap.release()

    # Staff detection: present in >70% of frames = staff
    staff_vids = {make_visitor_id(tid,cam_id) for tid,cnt in frame_counts.items()
                  if total>0 and cnt/total > STAFF_THRESHOLD}
    if staff_vids:
        print(f"  Staff visitor_ids detected: {staff_vids}")
        for ev in cam_events:
            if ev["visitor_id"] in staff_vids:
                ev["is_staff"] = True

    all_events.extend(cam_events)
    print(f"  DONE | Events: {len(cam_events)} | Staff flagged: {len(staff_vids)}")

if __name__ == "__main__":
    all_events = []
    for i, cam in enumerate(LAYOUT["cameras"]):
        process_camera(cam["file"], cam, all_events, hour_offset=i)
    flush()
    os.makedirs("data", exist_ok=True)
    with open(EVENTS_OUT, "w") as f:
        for ev in all_events:
            f.write(json.dumps(ev)+"\n")
    print(f"\n{'='*55}")
    print(f"PIPELINE COMPLETE")
    print(f"Total events : {len(all_events)}")
    print(f"Output file  : {EVENTS_OUT}")
    print(f"{'='*55}")
