import cv2
import numpy as np
from datetime import datetime

GLOBAL_DB = {}

NEXT_ID = 1


def color_signature(frame, x1, y1, x2, y2):

    crop = frame[y1:y2, x1:x2]

    if crop.size == 0:
        return None

    small = cv2.resize(
        crop,
        (32,32)
    )

    mean_color = np.mean(
        small,
        axis=(0,1)
    )

    return mean_color


def dist(a,b):

    if a is None or b is None:
        return 99999

    return np.linalg.norm(a-b)


def assign_global_id(
    frame,
    x1,y1,x2,y2,
    timestamp
):

    global NEXT_ID

    sig = color_signature(
        frame,
        x1,y1,x2,y2
    )

    best=None
    best_d=99999

    for gid,data in GLOBAL_DB.items():

        d=dist(
            sig,
            data["sig"]
        )

        if d<best_d:

            best_d=d
            best=gid

    if best is not None and best_d<35:

        GLOBAL_DB[best]={
            "sig":sig,
            "ts":timestamp
        }

        return best

    gid=f"VIS_GLOBAL_{NEXT_ID:04d}"

    NEXT_ID+=1

    GLOBAL_DB[gid]={
        "sig":sig,
        "ts":timestamp
    }

    return gid