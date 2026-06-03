from dotenv import load_dotenv
from groq import Groq
import json, os, csv
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pipeline.pos_insights import pos_summary
from pipeline.real_pos import pos_analytics
import sys

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import init_db, insert_event, query

init_db()
app = FastAPI(title="Store Intelligence API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

VALID_TYPES = {"ENTRY","EXIT","ZONE_ENTER","ZONE_EXIT","ZONE_DWELL",
               "BILLING_QUEUE_JOIN","BILLING_QUEUE_ABANDON","REENTRY"}

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def load_pos():
    f = "data/pos_transactions.csv"
    if not os.path.exists(f): return []
    with open(f) as fh: return list(csv.DictReader(fh))
def load_layout():
    f = "data/store_layout.json"
    return json.load(open(f)) if os.path.exists(f) else {}

class Meta(BaseModel):
    queue_depth: Optional[int]=None; sku_zone: Optional[str]=None; session_seq: int=0
class Event(BaseModel):
    event_id:str; store_id:str; camera_id:str; visitor_id:str; event_type:str
    timestamp:str; zone_id:Optional[str]=None; dwell_ms:int=0
    is_staff:bool=False; confidence:float=0.0; metadata:Optional[Meta]=None
class IngestReq(BaseModel):
    events: List[Event]

@app.get("/health")
def health():
    rows = query("SELECT store_id, MAX(timestamp) as last FROM events GROUP BY store_id")
    stores = []
    for r in rows:
        stale = False
        if r["last"]:
            try:
                dt = datetime.fromisoformat(r["last"].replace("Z","+00:00"))
                stale = (datetime.now(timezone.utc)-dt).total_seconds()/60 > 10
            except: stale=True
        stores.append({"store_id":r["store_id"],"last_event_at":r["last"],
                        "feed_status":"STALE_FEED" if stale else "OK"})
    total = query("SELECT COUNT(*) as c FROM events")[0]["c"]
    return {"status":"healthy","api_version":"1.0.0","total_events":total,"stores":stores,"checked_at":now()}

@app.post("/events/ingest")
def ingest(body: IngestReq):
    if len(body.events)>500: raise HTTPException(422,"Max 500 events per batch")
    accepted=rejected=duplicate=0; errors=[]
    for ev in body.events:
        if ev.event_type not in VALID_TYPES:
            rejected+=1; errors.append({"event_id":ev.event_id,"error":f"Invalid event_type: {ev.event_type}"}); continue
        inserted = insert_event(ev.model_dump())
        if inserted: accepted+=1
        else: duplicate+=1
    return {"accepted":accepted,"duplicates":duplicate,"rejected":rejected,"errors":errors,"timestamp":now()}

@app.get("/stores/{store_id}/metrics")
def metrics(store_id: str):

    # Unique visitors entering store
    visitors = query(
        """SELECT COUNT(DISTINCT visitor_id) as c
        FROM events
        WHERE store_id=?
        AND is_staff=0
        AND event_type='ENTRY'""",
        (store_id,)
    )

    unique = visitors[0]["c"]

    # POS transactions
    txns = [t for t in load_pos() if t["store_id"] == store_id]

    # Visitors reaching billing zone
    billing = query(
        """SELECT COUNT(DISTINCT visitor_id) as c
        FROM events
        WHERE store_id=?
        AND is_staff=0
        AND zone_id='BILLING'""",
        (store_id,)
    )

    in_billing = billing[0]["c"]

    # Conversion rate
    conversion = round(
        min(len(txns), in_billing) / unique,
        4
    ) if unique > 0 else 0.0

    # Average dwell by zone
    dwell = query(
        """
        SELECT
            zone_id,
            ROUND(AVG(dwell_ms)/1000.0,2) as avg_dwell_sec,
            COUNT(*) as visits
        FROM events
        WHERE store_id=?
        AND is_staff=0
        AND event_type IN ('ZONE_EXIT','ZONE_DWELL')
        AND zone_id IS NOT NULL
        AND dwell_ms>0
        GROUP BY zone_id
        ORDER BY avg_dwell_sec DESC
        """,
        (store_id,)
    )

    # Latest queue depth
    queue = query(
        """
        SELECT queue_depth
        FROM events
        WHERE store_id=?
        AND zone_id='BILLING'
        AND queue_depth IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (store_id,)
    )

    # FIXED: distinct abandonment count
    abandon = query(
        """
        SELECT COUNT(DISTINCT visitor_id) as c
        FROM events
        WHERE store_id=?
        AND is_staff=0
        AND event_type='BILLING_QUEUE_ABANDON'
        """,
        (store_id,)
    )

    abandon_count = abandon[0]["c"]

    abandonment_rate = round(
        abandon_count / in_billing,
        4
    ) if in_billing > 0 else 0.0

    return {
        "store_id": store_id,
        "unique_visitors": unique,
        "conversion_rate": conversion,
        "avg_dwell_by_zone": dwell,
        "queue_depth": queue[0]["queue_depth"] if queue else 0,
        "abandonment_rate": abandonment_rate,
        "pos_transactions": len(txns),
        "timestamp": now()
    }

@app.get("/stores/{store_id}/funnel")
def funnel(store_id:str):
    def cnt(sql,p): return query(sql,p)[0]["c"]
    entered  = cnt("SELECT COUNT(DISTINCT visitor_id) as c FROM events WHERE store_id=? AND is_staff=0 AND event_type='ENTRY'",(store_id,))
    zvisited = cnt("SELECT COUNT(DISTINCT visitor_id) as c FROM events WHERE store_id=? AND is_staff=0 AND event_type='ZONE_ENTER'",(store_id,))
    billing  = cnt("SELECT COUNT(DISTINCT visitor_id) as c FROM events WHERE store_id=? AND is_staff=0 AND (event_type='BILLING_QUEUE_JOIN' OR zone_id='BILLING')",(store_id,))
    purchased= len([t for t in load_pos() if t["store_id"]==store_id])
    def drop(a,b): return round((1-b/a)*100,1) if a>0 else 0.0
    return {"store_id":store_id,"funnel":[
        {"stage":"Entry",         "count":entered,   "drop_off_pct":0.0},
        {"stage":"Zone Visit",    "count":zvisited,  "drop_off_pct":drop(entered,zvisited)},
        {"stage":"Billing Queue", "count":billing,   "drop_off_pct":drop(zvisited,billing)},
        {"stage":"Purchase",      "count":purchased, "drop_off_pct":drop(billing,purchased)},
    ],"timestamp":now()}

@app.get("/stores/{store_id}/heatmap")
def heatmap(store_id:str):
    rows = query("""SELECT zone_id, COUNT(DISTINCT visitor_id) as visits,
        ROUND(AVG(dwell_ms)/1000.0,2) as avg_dwell_sec
        FROM events WHERE store_id=? AND is_staff=0 AND zone_id IS NOT NULL
        GROUP BY zone_id""",(store_id,))
    max_v = max((r["visits"] for r in rows),default=1)
    sessions = query("SELECT COUNT(DISTINCT visitor_id) as c FROM events WHERE store_id=? AND is_staff=0 AND event_type='ENTRY'",(store_id,))[0]["c"]
    out = sorted([{"zone_id":r["zone_id"],"visits":r["visits"],"avg_dwell_sec":r["avg_dwell_sec"],
                   "intensity":round(r["visits"]/max_v*100,1),
                   "data_confidence":"LOW" if sessions<20 else "OK"} for r in rows],
                  key=lambda x:x["intensity"],reverse=True)
    return {"store_id":store_id,"heatmap":out,"total_sessions":sessions,"timestamp":now()}

@app.get("/stores/{store_id}/anomalies")
def anomalies(store_id: str):

    alerts = []

    layout = load_layout()
    m = metrics(store_id)

    # Billing queue spike detection
    q = query(
        """
        SELECT queue_depth
        FROM events
        WHERE store_id=?
        AND zone_id='BILLING'
        AND queue_depth IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        (store_id,)
    )

    if q and q[0]["queue_depth"] and q[0]["queue_depth"] > 5:

        alerts.append({
            "anomaly_type":"BILLING_QUEUE_SPIKE",
            "severity":"CRITICAL",
            "detail":f"Queue depth={q[0]['queue_depth']}",
            "suggested_action":"Open extra billing counter",
            "detected_at":now()
        })

    # ---------- FIXED DEAD ZONE LOGIC ----------

    latest = query(
        """
        SELECT MAX(timestamp) as t
        FROM events
        WHERE store_id=?
        """,
        (store_id,)
    )

    latest_ts = latest[0]["t"] if latest else None

    if latest_ts:

        latest_dt = datetime.fromisoformat(
            latest_ts.replace("Z","+00:00")
        )

        for z in [zn["zone_id"] for zn in layout.get("zones", [])]:

            last = query(
                """
                SELECT MAX(timestamp) as t
                FROM events
                WHERE store_id=?
                AND zone_id=?
                """,
                (store_id, z)
            )

            lt = last[0]["t"] if last else None

            if lt:

                try:

                    dt = datetime.fromisoformat(
                        lt.replace("Z","+00:00")
                    )

                    mins = (
                        latest_dt - dt
                    ).total_seconds()/60

                    if mins > 30:

                        alerts.append({
                            "anomaly_type":"DEAD_ZONE",
                            "severity":"WARN",
                            "zone_id":z,
                            "detail":f"No visits in {int(mins)} min",
                            "suggested_action":f"Check {z} signage",
                            "detected_at":now()
                        })

                except:
                    pass

    # High abandonment alert
    if m["abandonment_rate"] > 0.3:

        alerts.append({
            "anomaly_type":"HIGH_ABANDONMENT",
            "severity":"WARN",
            "detail":f"Rate={m['abandonment_rate']*100:.1f}%",
            "suggested_action":"Reduce queue time",
            "detected_at":now()
        })

    # Conversion drop alert
    if m["conversion_rate"] < 0.1 and m["unique_visitors"] > 5:

        alerts.append({
            "anomaly_type":"CONVERSION_DROP",
            "severity":"CRITICAL",
            "detail":f"Rate={m['conversion_rate']*100:.1f}%",
            "suggested_action":"Review product placement",
            "detected_at":now()
        })

    return {
        "store_id": store_id,
        "total_anomalies": len(alerts),
        "anomalies": alerts,
        "timestamp": now()
    }




class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask(req: AskRequest):

    store_id = "STORE_BLR_002"

    m = metrics(store_id)
    f = funnel(store_id)
    h = heatmap(store_id)
    a = anomalies(store_id)

    context = {

        "metrics":m,

        "funnel":f,

        "heatmap":h,

        "anomalies":a
    }

    prompt = f"""
You are a senior retail analytics consultant.

Use ONLY provided store analytics.

Analytics:
{json.dumps(context, indent=2)}

Question:
{req.question}

Provide MAX 120 words.

Format:

SUMMARY:
(2 sentences)

EVIDENCE:
• bullet points

ACTION:
• 2 practical recommendations

Be concise.
"""

    try:

        print(
            "\n===== CALLING GROQ =====\n"
        )

        completion = (

            client.chat.completions.create(

                model=
                "llama-3.3-70b-versatile",

                messages=[

                    {
                        "role":"system",

                        "content":
                        "You are a retail analytics expert."
                    },

                    {
                        "role":"user",

                        "content":prompt
                    }
                ]
            )
        )

        answer = (

            completion
            .choices[0]
            .message
            .content
        )

        source = "groq"

        print(
            "\n===== GROQ SUCCESS =====\n"
        )

    except Exception as e:

        print(
            "\n===== GROQ ERROR ====="
        )

        print(type(e))

        print(e)

        print(
            "=======================\n"
        )

        insights = []

        if m["conversion_rate"] < 0.10:

            insights.append(

                f"Conversion is low "
                f"({m['conversion_rate']*100:.1f}%)."
            )

        if m["abandonment_rate"] > 0.30:

            insights.append(

                f"Checkout abandonment "
                f"is high "
                f"({m['abandonment_rate']*100:.1f}%)."
            )

        if any(

            x["anomaly_type"]=="CONVERSION_DROP"

            for x in a["anomalies"]

        ):

            insights.append(

                "Significant funnel leakage "
                "detected before purchase."
            )

        answer = " ".join(

            insights
        )

        if not answer:

            answer = (

                "Store analytics "
                "appear stable."
            )

        source = "fallback"

    


    return {

        "question":req.question,

        "answer":answer,

        "source":source,

        "timestamp":now()
    }


@app.get("/security")

def security():

    import json
    import os

    path = "data/events.jsonl"

    if not os.path.exists(path):

        return {

            "status":"ERROR",

            "message":"events missing"

        }

    backroom_visitors = set()

    with open(path) as f:

        for line in f:

            ev = json.loads(line)

            if ev["camera_id"] == "CAM_BACKROOM_01":

                backroom_visitors.add(
                    ev["visitor_id"]
                )

    if len(backroom_visitors)==0:

        return {

            "status":"OK",

            "backroom_status":
            "No personnel activity detected.",

            "personnel_count":0
        }

    return {

        "status":"OK",

        "backroom_status":
        "Personnel detected",

        "personnel_count":
        len(backroom_visitors),

        "visitors":
        list(backroom_visitors)
    }

@app.get("/pos-insights")

def pos_insights():

    return pos_summary()


@app.get("/cross-camera")

def cross_camera():

    import json
    from collections import defaultdict

    cams = defaultdict(set)

    with open("data/events.jsonl") as f:

        for line in f:

            ev = json.loads(line)

            cams[
                ev["visitor_id"]
            ].add(
                ev["camera_id"]
            )

    stitched=[]

    for vid,c in cams.items():

        if len(c)>1:

            stitched.append({

                "visitor_id":vid,

                "cameras":list(c)
            })

    return {

        "stitched_visitors":
        len(stitched),

        "examples":
        stitched[:10]
    }

@app.get("/real-pos")

def real_pos():

    return pos_analytics()


@app.get("/")
def root():
    return {
        "project": "Store Intelligence System",
        "status": "running",
        "docs": "/docs"
    }