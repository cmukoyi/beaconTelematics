"""
Geofence Double-Alert Diagnostic Script
========================================
Logs into the production API as a given user, retrieves the tracker and POI state,
simulates a position OUTSIDE the home POI, and traces exactly why (or why not)
two alerts would be generated.

Usage:
    python debug_geofence.py

You will be prompted for your password. The email and IMEI are pre-set below.
"""

import requests
import json
import math
import getpass
from datetime import datetime

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
API_BASE    = "https://beacontelematics.co.uk"
USER_EMAIL  = "carlmukoyi@gmail.com"
TARGET_IMEI = "868695060750161"   # Land Rover

# How far outside the fence to simulate (metres beyond the radius boundary)
OUTSIDE_BUFFER_METRES = 200
# ──────────────────────────────────────────────


def sep(title=""):
    print("\n" + "─" * 60)
    if title:
        print(f"  {title}")
        print("─" * 60)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ  = math.radians(lat2 - lat1)
    dλ  = math.radians(lon2 - lon1)
    a   = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def point_outside_poi(poi_lat, poi_lon, radius_m, buffer_m=200):
    """
    Returns coordinates that are (radius + buffer) metres due North of the POI centre.
    """
    total_dist = radius_m + buffer_m
    # 1 degree latitude ≈ 111,320 m
    delta_lat = total_dist / 111320
    return poi_lat + delta_lat, poi_lon


def simulate_check(tracker_id, tracker_name, poi, sim_lat, sim_lon, last_known_state, last_alert):
    """
    Replicate the _check_single_poi decision tree locally and explain every branch taken.
    """
    sep(f"Simulating _check_single_poi for POI '{poi['name']}'")

    dist = haversine(sim_lat, sim_lon, poi["latitude"], poi["longitude"])
    radius = poi["radius"]
    is_inside = dist <= radius
    current_state = "inside" if is_inside else "outside"

    print(f"  POI centre     : {poi['latitude']}, {poi['longitude']}")
    print(f"  POI radius     : {radius} m")
    print(f"  Simulated pos  : {sim_lat:.6f}, {sim_lon:.6f}")
    print(f"  Distance       : {dist:.1f} m  →  {'INSIDE ✅' if is_inside else 'OUTSIDE ❌'}")
    print(f"  last_known_state (DB) : {last_known_state}")
    print(f"  current_state (sim)   : {current_state}")

    sep("Strict Pairing Decision Tree")

    should_alert = False
    event_type   = None

    if last_known_state == "unknown":
        print("  ⚠️  last_known_state = UNKNOWN")
        print("      → Will update state to current_state but NO alert generated.")
        print("      → This is a safe first-run state.")

    elif last_known_state == "inside" and current_state == "outside":
        should_alert = True
        event_type   = "EXIT"
        print("  ✅ Transition: INSIDE → OUTSIDE")
        print("     → Should generate EXIT alert ('🔴 is Outside')")

    elif last_known_state == "outside" and current_state == "inside":
        should_alert = True
        event_type   = "ENTRY"
        print("  ✅ Transition: OUTSIDE → INSIDE")
        print("     → Should generate ENTRY alert ('🟢 is Inside')")

    elif last_known_state == "inside" and current_state == "inside":
        print("  ⏸  No change: still INSIDE → no alert (waiting for EXIT)")

    elif last_known_state == "outside" and current_state == "outside":
        print("  ⏸  No change: still OUTSIDE → no alert (waiting for ENTRY)")

    sep("Debounce Check")
    DEBOUNCE_SECONDS = 300   # route POI uses 60s, single POI has NO current debounce
    if should_alert and last_alert:
        try:
            last_ts_str = last_alert.get("created_at", "")
            # Try to parse ISO format
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
            now = datetime.now(last_ts.tzinfo)
            elapsed = (now - last_ts).total_seconds()
            print(f"  Last alert     : {last_ts_str}  ({elapsed:.0f}s ago)")
            print(f"  Last event     : {last_alert.get('event_type')}")
            print(f"  Current event  : {event_type}")
            print()
            if elapsed < DEBOUNCE_SECONDS:
                print(f"  ⚠️  DEBOUNCE WOULD FIRE (if it existed for single POIs)")
                print(f"     Elapsed {elapsed:.0f}s < {DEBOUNCE_SECONDS}s minimum")
                print(f"     ‼️  THIS IS THE BUG: single POIs have NO debounce,")
                print(f"        so rapid oscillation at the geofence boundary")
                print(f"        fires both ENTRY and EXIT within seconds.")
            else:
                print(f"  ✅ Debounce OK: {elapsed:.0f}s ≥ {DEBOUNCE_SECONDS}s")
        except Exception as e:
            print(f"  (Could not parse last alert timestamp: {e})")
    elif should_alert and not last_alert:
        print("  No previous alerts — debounce not applicable for first alert.")
    else:
        print("  No alert to debounce (should_alert = False).")

    sep("Conclusion")
    if should_alert:
        print(f"  📧 ALERT WOULD BE SENT: {event_type}  ('{tracker_name}' at '{poi['name']}')")
    else:
        print(f"  🔕 No alert for this simulation run.")
    print()
    return should_alert, event_type


def main():
    sep("GEOFENCE DOUBLE-ALERT DIAGNOSTIC")
    print(f"  User  : {USER_EMAIL}")
    print(f"  IMEI  : {TARGET_IMEI} (Land Rover)")
    print(f"  API   : {API_BASE}")

    # ── 1. LOGIN ──────────────────────────────────────────
    sep("Step 1 — Login")
    password = getpass.getpass(f"  Password for {USER_EMAIL}: ")

    resp = requests.post(f"{API_BASE}/api/v1/auth/login",
                         json={"email": USER_EMAIL, "password": password},
                         timeout=15)
    if resp.status_code != 200:
        print(f"  ❌ Login failed ({resp.status_code}): {resp.text}")
        return
    token = resp.json().get("access_token")
    print("  ✅ Login successful")

    headers = {"Authorization": f"Bearer {token}"}

    # ── 2. FIND TRACKER ───────────────────────────────────────
    sep("Step 2 — Find Land Rover tracker")
    resp = requests.get(f"{API_BASE}/api/v1/ble-tags", headers=headers, timeout=15)
    trackers = resp.json()
    tracker = next((t for t in trackers if t.get("imei") == TARGET_IMEI), None)
    if not tracker:
        print(f"  ❌ Could not find tracker with IMEI {TARGET_IMEI}")
        print(f"     Available IMEIs: {[t.get('imei') for t in trackers]}")
        return

    tracker_id   = tracker["id"]
    tracker_name = tracker.get("description") or tracker.get("device_name") or TARGET_IMEI[-4:]
    curr_lat     = float(tracker.get("latitude") or 0)
    curr_lon     = float(tracker.get("longitude") or 0)

    print(f"  ✅ Found: '{tracker_name}'")
    print(f"     ID       : {tracker_id}")
    print(f"     Location : {curr_lat}, {curr_lon}")
    print(f"     Last seen: {tracker.get('last_seen')}")

    # ── 3. GET POIs ───────────────────────────────────────────
    sep("Step 3 — POIs armed to this tracker")
    resp = requests.get(f"{API_BASE}/api/v1/pois", headers=headers, timeout=15)
    all_pois = resp.json()
    armed_pois = [p for p in all_pois if tracker_id in p.get("armed_trackers", [])]

    if not armed_pois:
        print("  ⚠️  No POIs are currently armed to this tracker.")
        print("     Cannot test geofence — arm a POI first.")
        return

    print(f"  Found {len(armed_pois)} armed POI(s):")
    for p in armed_pois:
        dist = haversine(curr_lat, curr_lon, p["latitude"], p["longitude"]) if curr_lat else 0
        print(f"    • '{p['name']}' (type={p['poi_type']})")
        print(f"      Centre : {p['latitude']}, {p['longitude']},  radius={p['radius']}m")
        print(f"      Currently {dist:.0f}m from tracker  →  {'INSIDE ✅' if dist <= p['radius'] else 'OUTSIDE ❌'}")

    # ── 4. GET RECENT ALERTS ──────────────────────────────────
    sep("Step 4 — Recent alert history (last 5)")
    resp = requests.get(f"{API_BASE}/api/v1/alerts?limit=5", headers=headers, timeout=15)
    recent_alerts = []
    if resp.status_code == 200:
        data = resp.json()
        recent_alerts = data.get("alerts", data) if isinstance(data, dict) else data
        for a in recent_alerts[:5]:
            print(f"    [{a.get('created_at','?')}]  {a.get('event_type','?')}  POI={a.get('poi_id','?')}")
    else:
        print(f"  (Could not fetch alerts: {resp.status_code})")

    # ── 5. GET poi-tracker link state (via mock-location with current pos) ──
    # Instead of querying the internal DB, infer last_known_state from the
    # most recent alert for each POI — the alert type tells us what state
    # the link will be in now.
    sep("Step 5 — Infer last_known_state from alert history")
    poi_last_alert = {}
    for a in reversed(recent_alerts):   # oldest first so last wins
        poi_id = a.get("poi_id")
        if poi_id:
            poi_last_alert[poi_id] = a

    for p in armed_pois:
        last_a = poi_last_alert.get(p["id"])
        if last_a:
            # After an ENTRY alert, state is INSIDE.  After EXIT, state is OUTSIDE.
            inferred = "inside" if last_a.get("event_type") == "entry" else "outside"
            print(f"  '{p['name']}': last alert was {last_a.get('event_type').upper()} "
                  f"at {last_a.get('created_at')}  → inferred last_known_state = {inferred}")
        else:
            inferred = "unknown"
            print(f"  '{p['name']}': no alert history → last_known_state likely = unknown or initial arm state")
        p["_inferred_state"] = inferred
        p["_last_alert"] = last_a

    # ── 6. SIMULATE OUTSIDE POSITION ─────────────────────────
    sep("Step 6 — Simulate position OUTSIDE home POI")
    for p in armed_pois:
        if p.get("poi_type") != "single":
            print(f"  Skipping route POI '{p['name']}' (different logic)")
            continue

        sim_lat, sim_lon = point_outside_poi(p["latitude"], p["longitude"],
                                             p["radius"], OUTSIDE_BUFFER_METRES)
        print(f"\n  Generated outside position for '{p['name']}':")
        print(f"  ({sim_lat:.6f}, {sim_lon:.6f})  — {OUTSIDE_BUFFER_METRES}m beyond fence boundary")

        simulate_check(
            tracker_id,
            tracker_name,
            p,
            sim_lat, sim_lon,
            p.get("_inferred_state", "unknown"),
            p.get("_last_alert")
        )

    # ── 7. CALL REAL mock-location API ────────────────────────
    sep("Step 7 — Hit /api/v1/test/mock-location with outside coordinates")
    print("  ⚠️  This will send a REAL email if alert fires!")
    confirm = input("  Proceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("  Skipped.")
        sep("DONE — simulation only (no real API call made)")
        return

    single_pois = [p for p in armed_pois if p.get("poi_type") == "single"]
    if not single_pois:
        print("  No single POIs to test.")
        return

    # Use the first single POI's outside coordinates
    p = single_pois[0]
    sim_lat, sim_lon = point_outside_poi(p["latitude"], p["longitude"],
                                         p["radius"], OUTSIDE_BUFFER_METRES)

    payload = {"tracker_id": tracker_id, "latitude": sim_lat, "longitude": sim_lon}
    print(f"\n  Calling mock-location with {payload} ...")
    resp = requests.post(f"{API_BASE}/api/v1/test/mock-location",
                         headers={**headers, "Content-Type": "application/json"},
                         json=payload, timeout=20)

    print(f"\n  HTTP {resp.status_code}")
    try:
        result = resp.json()
        print(json.dumps(result, indent=4))
        n = result.get("alerts_triggered", 0)
        print(f"\n  {'⚠️  ' + str(n) + ' alert(s) triggered — check email' if n else '✅ No alerts triggered'}")
    except Exception:
        print(resp.text)

    sep("DONE")


if __name__ == "__main__":
    main()
