import json
import os

ENTRY_CAMERAS = {
    "CAM_ENTRY_02"
}

BACKROOM_CAMERA = "CAM_BACKROOM_01"

EVENT_FILE = "data/events.jsonl"


def load_events():

    events = []

    if not os.path.exists(EVENT_FILE):
        return events

    with open(EVENT_FILE) as f:

        for line in f:

            if line.strip():

                events.append(
                    json.loads(line)
                )

    return events


events = load_events()

print(
    f"\nLoaded {len(events)} events"
)

backroom_visitors = set()

for ev in events:

    if ev["camera_id"] == BACKROOM_CAMERA:

        backroom_visitors.add(
            ev["visitor_id"]
        )


print("\n==============================")
print("BACKROOM STATUS")
print("==============================\n")

if len(backroom_visitors) == 0:

    print(
        "No personnel activity detected."
    )

else:

    print(
        "Authorized / Detected Personnel:\n"
    )

    print(backroom_visitors)

    print(
        f"\nTOTAL: {len(backroom_visitors)}"
    )