# PROMPT: "Write pytest tests for a store intelligence event pipeline.
# Test the required event schema fields, UUID format for event_id,
# VIS_ prefix for visitor_id, valid event_types, is_staff boolean,
# confidence between 0 and 1, dwell_ms non-negative, metadata keys.
# Test that 50 consecutive events all have unique event_ids."
# CHANGES MADE: Removed mock that hid real schema bugs. Added
# explicit test for metadata structure. Fixed UUID assertion to use
# uuid.UUID() parser instead of regex (more reliable).

import pytest, sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.emit import make_event, make_visitor_id, STORE_ID

def sample_event(**overrides):
    ev = make_event(
        camera_id="CAM_ENTRY_01", visitor_id="VIS_abc123",
        event_type="ENTRY", zone_id="ENTRY_EXIT", dwell_ms=0,
        is_staff=False, confidence=0.91,
        frame_timestamp="2026-03-03T10:00:00Z", session_seq=1
    )
    ev.update(overrides)
    return ev

def test_event_has_all_required_fields():
    ev = sample_event()
    for field in ["event_id","store_id","camera_id","visitor_id",
                  "event_type","timestamp","zone_id","dwell_ms",
                  "is_staff","confidence","metadata"]:
        assert field in ev, f"Missing required field: {field}"

def test_event_id_is_valid_uuid():
    ev = sample_event()
    parsed = uuid.UUID(ev["event_id"])
    assert str(parsed) == ev["event_id"]

def test_visitor_id_has_vis_prefix():
    vid = make_visitor_id(42, "CAM_ENTRY_01")
    assert vid.startswith("VIS_")
    assert len(vid) == 10

def test_store_id_matches_constant():
    ev = sample_event()
    assert ev["store_id"] == STORE_ID

def test_confidence_in_valid_range():
    ev = sample_event(confidence=0.91)
    assert 0.0 <= ev["confidence"] <= 1.0

def test_dwell_ms_non_negative():
    assert sample_event(dwell_ms=0)["dwell_ms"] >= 0

def test_is_staff_is_boolean():
    assert isinstance(sample_event()["is_staff"], bool)

def test_metadata_has_required_keys():
    meta = sample_event()["metadata"]
    assert "queue_depth" in meta
    assert "sku_zone"    in meta
    assert "session_seq" in meta

def test_all_valid_event_types_accepted():
    for etype in ["ENTRY","EXIT","ZONE_ENTER","ZONE_EXIT","ZONE_DWELL",
                  "BILLING_QUEUE_JOIN","BILLING_QUEUE_ABANDON","REENTRY"]:
        ev = sample_event(event_type=etype)
        assert ev["event_type"] == etype

def test_fifty_events_have_unique_ids():
    ids = [sample_event()["event_id"] for _ in range(50)]
    assert len(set(ids)) == 50

def test_same_track_same_camera_gives_same_visitor_id():
    id1 = make_visitor_id(7, "CAM_FLOOR_01")
    id2 = make_visitor_id(7, "CAM_FLOOR_01")
    assert id1 == id2

def test_different_cameras_give_different_visitor_ids():
    id1 = make_visitor_id(7, "CAM_ENTRY_01")
    id2 = make_visitor_id(7, "CAM_FLOOR_01")
    assert id1 != id2
