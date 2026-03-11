#!/usr/bin/env python3
"""
Direct test of Trips API using secure token authentication
IMEI: 868695060773007 (rhw.cheng@gmail.com)
"""

import requests
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

# Configuration
BASE_URL = "https://live.mzoneweb.net/mzone62.api"
AUTH_URL = "https://login.mzoneweb.net/connect/token"

# MZone OAuth credentials
CLIENT_ID = "mz-scopeuk"
CLIENT_SECRET = "g_SkQ.B.z3TeBU$g#hVeP#c2"
USERNAME = "ScopeUKAPI"
PASSWORD = "ScopeUKAPI01!"

# User vehicle ID (you'll need to replace this with actual vehicle_id for rhw.cheng@gmail.com)
# This is the GUID that maps to IMEI 868695060773007
VEHICLE_ID = "88c45ad7-4054-40d8-b530-ed844e1c261a"  # Example - update with actual GUID

# Vehicle group ID (for scoping)
VEHICLE_GROUP_ID = "e7042dff-f0d8-42ec-9324-c4b730cf177d"

# Date range
START_DATE = (datetime.now() - timedelta(days=30)).isoformat().split('.')[0] + 'Z'
END_DATE = datetime.now().isoformat().split('.')[0] + 'Z'

print("=" * 80)
print("Testing MZone Trips API Directly")
print("=" * 80)
print()

# Step 1: Get OAuth Token
print("Step 1: Getting OAuth token from MZone...")
print(f"  Auth URL: {AUTH_URL}")
print()

token_response = requests.post(
    AUTH_URL,
    headers={'Content-Type': 'application/x-www-form-urlencoded'},
    data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": USERNAME,
        "password": PASSWORD,
        "scope": "mz6-api.all mz_username",
        "grant_type": "password",
        "response_type": "code id_token"
    },
    timeout=10
)

print(f"  Status Code: {token_response.status_code}")

if token_response.status_code != 200:
    print(f"  ❌ Failed to get token")
    print(f"  Response: {token_response.text}")
    exit(1)

token_data = token_response.json()
access_token = token_data.get('access_token')
token_type = token_data.get('token_type', 'Bearer')
expires_in = token_data.get('expires_in')

print(f"  ✅ Got token")
print(f"  Token type: {token_type}")
print(f"  Expires in: {expires_in} seconds")
print(f"  Token (first 50 chars): {access_token[:50]}...")
print()

# Step 2: Call Trips API
print("Step 2: Calling Trips API...")
print()

params = {
    '$format': 'json',
    '$count': 'true',
    '$select': 'vehicle_Description,duration,distance,startLocationDescription,startUtcTimestamp,endLocationDescription,endUtcTimestamp,driver_Description,id,vehicle_Id,driverKeyCode',
    '$orderby': 'startUtcTimestamp desc',
    '$skip': '0',
    '$top': '50',
    'utcStartDate': START_DATE,
    'utcEndDate': END_DATE,
    'vehicleGroup_Id': VEHICLE_GROUP_ID,
    '$filter': f'(vehicle_Id eq {VEHICLE_ID})'
}

api_url = f'{BASE_URL}/Trips?{urlencode(params)}'

print(f"  API URL (truncated): {api_url[:100]}...")
print(f"  Vehicle ID: {VEHICLE_ID}")
print(f"  Vehicle Group ID: {VEHICLE_GROUP_ID}")
print(f"  Date Range: {START_DATE} to {END_DATE}")
print()

headers = {
    'Authorization': f'{token_type} {access_token}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

trips_response = requests.get(api_url, headers=headers, timeout=30)

print(f"  Status Code: {trips_response.status_code}")
print()

# Step 3: Display Response
print("=" * 80)
print("Response from Trips API")
print("=" * 80)
print()

if trips_response.status_code != 200:
    print(f"❌ API Error {trips_response.status_code}")
    print()
    print("Response Text:")
    print(trips_response.text)
    exit(1)

trips_data = trips_response.json()

print(f"✅ Success!")
print()

# Count
odata_count = trips_data.get('@odata.count', 0)
trips = trips_data.get('value', [])

print(f"Total trips available: {odata_count}")
print(f"Trips in this response: {len(trips)}")
print()

if not trips:
    print("⚠️ No trips found for this vehicle and date range")
    print()
    print("Possible reasons:")
    print("  1. Wrong vehicle_id GUID")
    print("  2. Date range has no trip data")
    print("  3. Vehicle group ID mismatch")
    print()
    print("Full response:")
    print(json.dumps(trips_data, indent=2))
else:
    print(f"Showing first {min(10, len(trips))} trips:")
    print()
    
    for i, trip in enumerate(trips[:10], 1):
        print(f"Trip #{i}:")
        print(f"  ID: {trip.get('id')}")
        print(f"  Vehicle: {trip.get('vehicle_Description', 'N/A')}")
        print(f"  Driver: {trip.get('driver_Description', 'N/A')}")
        print(f"  Start: {trip.get('startUtcTimestamp')} at {trip.get('startLocationDescription', 'Unknown')}")
        print(f"  End:   {trip.get('endUtcTimestamp')} at {trip.get('endLocationDescription', 'Unknown')}")
        print(f"  Distance: {trip.get('distance', 0):.2f} km | Duration: {trip.get('duration', 0)} sec")
        print()

# Save full response to file
output_file = "trips_api_response.json"
with open(output_file, 'w') as f:
    json.dump(trips_data, f, indent=2)

print(f"Full response saved to: {output_file}")
