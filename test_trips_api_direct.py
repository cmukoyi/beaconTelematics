#!/usr/bin/env python3
"""Test MZone Trips API directly with the correct credentials and format"""

import requests
import json
from datetime import datetime

# Step 1: Get OAuth Token
print("=" * 60)
print("Step 1: Getting OAuth Token...")
print("=" * 60)

token_url = "https://login.mzoneweb.net/connect/token"
token_payload = {
    'client_id': 'mz-scopeuk',
    'client_secret': 'g_SkQ.B.z3TeBU$g#hVeP#c2',
    'username': 'ScopeUKAPI',
    'password': 'ScopeUKAPI01!',
    'scope': 'mz6-api.all mz_username',
    'grant_type': 'password',
    'response_type': 'code id token'
}

token_headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
}

try:
    token_response = requests.post(token_url, data=token_payload, headers=token_headers, timeout=10)
    token_response.raise_for_status()
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    
    if access_token:
        print(f"✅ Token obtained successfully")
        print(f"   Token (first 50 chars): {access_token[:50]}...")
    else:
        print(f"❌ Failed to get token. Response: {token_data}")
        exit(1)
except Exception as e:
    print(f"❌ Error getting token: {e}")
    exit(1)

# Step 2: Call Trips API with the token
print("\n" + "=" * 60)
print("Step 2: Calling Trips API with correct filter format...")
print("=" * 60)

# Test vehicle ID that has trips
vehicle_id = "88c45ad7-4054-40d8-b530-ed844e1c261a"
start_date = "2026-01-31T22:00:00Z"
end_date = "2026-03-11T21:59:59Z"

# Build the API URL - with required parameters as query params, NOT in filter
# The API requires utcStartDate, utcEndDate, and vehicle_Id as TOP-LEVEL query parameters
trips_url = (
    f"https://live.mzoneweb.net/mzone62.api/Trips?"
    f"utcStartDate={start_date}&"
    f"utcEndDate={end_date}&"
    f"vehicle_Id={vehicle_id}&"
    f"$format=json&"
    f"$count=true&"
    f"$select=vehicle_Description,duration,distance,startLocationDescription,startUtcTimestamp,"
    f"endLocationDescription,endUtcTimestamp,driver_Description,id,vehicle_Id,driverKeyCode&"
    f"$orderby=startUtcTimestamp%20desc&"
    f"$skip=0&"
    f"$top=50"
)

print(f"URL: {trips_url}\n")

trips_headers = {
    'Authorization': f'Bearer {access_token}'
}

try:
    trips_response = requests.get(trips_url, headers=trips_headers, timeout=10)
    trips_response.raise_for_status()
    
    trips_data = trips_response.json()
    value = trips_data.get('value', [])
    count = trips_data.get('@odata.count', 0)
    
    print(f"✅ API Call Successful!")
    print(f"   Total trips found: {count}")
    print(f"   Trips returned in response: {len(value)}")
    
    if value:
        print(f"\n   First trip details:")
        trip = value[0]
        print(f"   - Vehicle: {trip.get('vehicle_Description')}")
        print(f"   - Duration: {trip.get('duration')} seconds")
        print(f"   - Distance: {trip.get('distance')} km")
        print(f"   - From: {trip.get('startLocationDescription')}")
        print(f"   - To: {trip.get('endLocationDescription')}")
        print(f"   - Driver: {trip.get('driver_Description')}")
        print(f"\n   Full response (first trip):")
        print(json.dumps(trip, indent=2, default=str))
    else:
        print(f"⚠️  No trips found for vehicle {vehicle_id} in the date range")
        
except Exception as e:
    print(f"❌ Error calling trips API: {e}")
    if hasattr(e, 'response'):
        print(f"   Response status: {e.response.status_code}")
        print(f"   Response text: {e.response.text}")
    exit(1)

print("\n" + "=" * 60)
print("Test Complete!")
print("=" * 60)
