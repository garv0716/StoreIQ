import numpy as np
import time

try:
    import cv2
except Exception:

    class _CV2Stub:

        @staticmethod
        def resize(img,dsize):

            if img is None:
                return None

            if getattr(img,"size",0)==0:
                return img

            tw,th=dsize

            h,w=img.shape[:2]

            if h==th and w==tw:
                return img.copy()

            row_idx=np.linspace(
                0,
                h-1,
                th
            ).astype(int)

            col_idx=np.linspace(
                0,
                w-1,
                tw
            ).astype(int)

            return img.take(
                row_idx,
                axis=0
            ).take(
                col_idx,
                axis=1
            )

    cv2=_CV2Stub()


GLOBAL_DB={}

NEXT_ID=1

MATCH_THRESHOLD=15

MAX_AGE_SEC=60


VALID_TRANSITIONS={

    "CAM_ENTRY_01":[
        "CAM_FLOOR_01"
    ],

    "CAM_FLOOR_01":[
        "CAM_ENTRY_01",
        "CAM_BILLING_01"
    ],

    "CAM_BILLING_01":[
        "CAM_FLOOR_01"
    ]
}


def color_signature(
    frame,
    x1,y1,x2,y2
):

    crop=frame[y1:y2,x1:x2]

    if crop.size==0:
        return None

    small=cv2.resize(
        crop,
        (32,32)
    )

    return np.mean(
        small,
        axis=(0,1)
    )


def dist(a,b):

    if a is None or b is None:
        return 99999

    return np.linalg.norm(a-b)


def cleanup_db():

    now=time.time()

    dead=[]

    for gid,data in GLOBAL_DB.items():

        age=now-data["ts"]

        if age>MAX_AGE_SEC:
            dead.append(gid)

    for gid in dead:
        del GLOBAL_DB[gid]


def assign_global_id(
    frame,
    x1,y1,x2,y2,
    timestamp,
    camera_id=None
):

    global NEXT_ID

    cleanup_db()

    sig=color_signature(
        frame,
        x1,y1,x2,y2
    )

    best=None
    best_d=99999

    for gid,data in GLOBAL_DB.items():

        old_cam=data.get(
            "camera"
        )

        age=time.time()-data["ts"]

        # ---------- SAME CAMERA ----------
        if old_cam==camera_id:

            if age<5:

                d=dist(
                    sig,
                    data["sig"]
                )

                if d<best_d:

                    best_d=d
                    best=gid

            continue

        # ---------- CAMERA GRAPH ----------

        allowed=VALID_TRANSITIONS.get(
            old_cam,
            []
        )

        if camera_id not in allowed:
            continue

        # ---------- CROSS CAMERA MATCH ----------

        d=dist(
            sig,
            data["sig"]
        )

        if d<best_d:

            best_d=d
            best=gid

    # ---------- MATCH FOUND ----------

    if best is not None and best_d<MATCH_THRESHOLD:

        print(
            f"[MATCH] {best} | "
            f"dist={best_d:.2f} | "
            f"{GLOBAL_DB[best]['camera']} -> {camera_id}"
        )

        GLOBAL_DB[best]={

            "sig":sig,

            "ts":time.time(),

            "camera":camera_id
        }

        return best

    # ---------- NEW GLOBAL ID ----------

    gid=f"VIS_GLOBAL_{NEXT_ID:04d}"

    NEXT_ID+=1

    GLOBAL_DB[gid]={

        "sig":sig,

        "ts":time.time(),

        "camera":camera_id
    }

    print(
        f"[REID] {gid} | "
        f"DB={len(GLOBAL_DB)} | "
        f"cam={camera_id}"
    )

    return gid