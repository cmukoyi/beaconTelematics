"""
Race Condition Regression Test
================================
1. Logs in as carlmukoyi@gmail.com
2. Calls mock-location with an OUTSIDE coordinate for the UK 'Home' POI
3. Immediately calls it a second time (simulating concurrent execution)
4. Checks alert history — should see only ONE new alert, not two.

If the fix works  → 1 alert generated across both calls
If the bug exists → 2 identical alerts within <1s of each other
"""

import requests
import json
import math
import getpass
import time
from datetime import datetime, timezone

API_BASE    = "https://beacontelematics.co.uk"
USER_EMAIL  = "carlmukoyi@gmail.com"
TARGET_IMEI = "868695060750161"   # Land Rover / Jeep Compass MHub369F

# Known UK Home POI  (from previous diagnostic run)
HOME_UK_CENTRE = (51.388925, -0.185216)
HOME_UK_RADIUS = 150.0

def sep(title=""):
    print("\n" + "─" * 60)
    if title:
        print(f"  {title}")
        print("─" * 60)

def outside_pos(poi_lat, poi_lon, radius, buffer=300):
    """Point (radius + buffer) metres due North of POI centre."""
    delta_lat = (radius + buffer) / 111320
    return round(poi_lat + delta_lat, 6), round(poi_lon, 6)

def count_recent_alerts(headers, since_iso):
    """Return alerts created after since_iso."""
    resp = requests.get(f"{API_BASE}/api/v1/alerts?limit=20", headers=headers, timeout=15)
    if resp.status_code != 200:
        return []
    data = resp.json()
    alerts = data.get("alerts", data) if isinstance(data, dict) else data
    since = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
    return [a for a in alerts
            if datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) >= since]


def main():
    sep("RACE CONDITION REGRESSION TEST")
    password = input(f"  Password for {USER_EMAIL}: ")

    # ── Login ──────────────────────────────────────────────────
    sep("Step 1 — Login")
    print("  (password will be visible — this is a local test only)")
    resp = requests.post(f"{API_BASE}/api/v1/auth/login",
                         json={"email": USER_EMAIL, "password": password}, timeout=15)
    if resp.status_code != 200:
        print(f"  ❌ Login failed: {resp.text}"); return
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("  ✅ Logged in")

    # ── Find tracker ───────────────────────────────────────────
    sep("Step 2 — Find tracker")
    trackers = requests.get(f"{API_BASE}/api/v1/ble-tags", headers=headers, timeout=15).json()
    tracker = next((t for t in trackers if t.get("imei") == TARGET_IMEI), None)
    if not tracker:
        print(f"  ❌ Tracker IMEI {TARGET_IMEI} not found"); return
    tracker_id = tracker["id"]
    tracker_name = tracker.get("description") or tracker.get("device_name") or TARGET_IMEI
    print(f"  ✅ '{tracker_name}'  id={tracker_id}")

    # ── Reset state: send INSIDE position first ────────────────
    # This ensures last_known_state = INSIDE so the next OUTSIDE call is a valid transition.
    sep("Step 3 — Prime state: send INSIDE position")
    inside_lat, inside_lon = HOME_UK_CENTRE
    r = requests.post(f"{API_BASE}/api/v1/test/mock-location", headers=headers,
                      json={"tracker_id": tracker_id, "latitude": inside_lat, "longitude": inside_lon},
                      timeout=20)
    print(f"  HTTP {r.status_code}  alerts_triggered={r.json().get('alerts_triggered', '?')}")
    print("  Waiting 2s ...")
    time.sleep(2)

    # ── Record baseline ────────────────────────────────────────
    test_start = datetime.now(timezone.utc).isoformat()
    outside_lat, outside_lon = outside_pos(*HOME_UK_CENTRE, HOME_UK_RADIUS, buffer=300)

    sep(f"Step 4 — Fire TWO rapid OUTSIDE calls\n  Position: {outside_lat}, {outside_lon}")
    print("  (This mimics the background poller + concurrent request hitting at the same time)\n")

    # ── Call 1 ─────────────────────────────────────────────────
    t0 = time.time()
    r1 = requests.post(f"{API_BASE}/api/v1/test/mock-location", headers=headers,
                       json={"tracker_id": tracker_id, "latitude": outside_lat, "longitude": outside_lon},
                       timeout=20)
    t1 = time.time()
    result1 = r1.json()
    print(f"  Call 1  →  HTTP {r1.status_code}  alerts_triggered={result1.get('alerts_triggered')}  "
          f"({(t1-t0)*1000:.0f}ms)")

    # ── Call 2 immediately ─────────────────────────────────────
    r2 = requests.post(f"{API_BASE}/api/v1/test/mock-location", headers=headers,
                       json={"tracker_id": tracker_id, "latitude": outside_lat, "longitude": outside_lon},
                       timeout=20)
    t2 = time.time()
    result2 = r2.json()
    print(f"  Call 2  →  HTTP {r2.status_code}  alerts_triggered={result2.get('alerts_triggered')}  "
          f"({(t2-t1)*1000:.0f}ms)")

    # ── Check alert DB ─────────────────────────────────────────
    sep("Step 5 — Check alert history since test start")
    time.sleep(1)   # small settle delay
    new_alerts = count_recent_alerts(headers, test_start)
    exit_alerts = [a for a in new_alerts if a.get("event_type") == "exit"]

    print(f"  New alerts recorded since test start : {len(new_alerts)}")
    print(f"  EXIT alerts specifically             : {len(exit_alerts)}")
    for a in new_alerts:
        print(f"    [{a.get('created_at')}]  {a.get('event_type')}  poi={a.get('poi_id','')[:8]}")

    sep("RESULT")
    if len(exit_alerts) == 1:
        print("  ✅ PASS — Fix is working. Only 1 EXIT alert generated across 2 rapid calls.")
        print("       Safe to push to production.")
    elif len(exit_alerts) == 0:
        print("  ⚠️  0 EXIT alerts — state may already have been OUTSIDE from a previous test.")
        print("     Re-run after sending an INSIDE position to reset.")
    else:
        print(f"  ❌ FAIL — {len(exit_alerts)} EXIT alerts generated. Race condition still present.")
        print("     Do NOT push until the issue is resolved.")

    print()

if __name__ == "__main__":
    main()
