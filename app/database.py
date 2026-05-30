import sqlite3, os

DB_PATH = "data/events.db"

def get_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, store_id TEXT, camera_id TEXT,
            visitor_id TEXT, event_type TEXT, timestamp TEXT,
            zone_id TEXT, dwell_ms INTEGER DEFAULT 0, is_staff INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0, queue_depth INTEGER,
            sku_zone TEXT, session_seq INTEGER DEFAULT 0
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_store   ON events(store_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_visitor ON events(visitor_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_type    ON events(event_type)")
    conn.commit(); conn.close()
    print("DB ready:", DB_PATH)

def insert_event(ev: dict) -> bool:
    conn = get_db()
    try:
        m = ev.get("metadata") or {}
        conn.execute("""INSERT INTO events
            (event_id,store_id,camera_id,visitor_id,event_type,timestamp,
             zone_id,dwell_ms,is_staff,confidence,queue_depth,sku_zone,session_seq)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ev["event_id"],ev["store_id"],ev["camera_id"],ev["visitor_id"],
             ev["event_type"],ev["timestamp"],ev.get("zone_id"),
             ev.get("dwell_ms",0), 1 if ev.get("is_staff") else 0,
             ev.get("confidence",0), m.get("queue_depth"),
             m.get("sku_zone"), m.get("session_seq",0)))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def query(sql, params=()):
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
