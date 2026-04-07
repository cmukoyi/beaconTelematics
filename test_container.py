import requests, os

cid = os.environ.get('MZONE_CLIENT_ID', '')
csec = os.environ.get('MZONE_CLIENT_SECRET', '')
user = os.environ.get('MZONE_USERNAME', '')
pwd = os.environ.get('MZONE_PASSWORD', '')
gid = os.environ.get('MZONE_VEHICLE_GROUP_ID', '')

print('client_id:', cid)
print('username:', user)
print('group_id:', gid)
print()

r = requests.post(
    'https://login.mzoneweb.net/connect/token',
    data={
        'client_id': cid,
        'client_secret': csec,
        'username': user,
        'password': pwd,
        'scope': 'mz6-api.all mz_username',
        'grant_type': 'password'
    },
    timeout=15
)
print('Token status:', r.status_code)

if r.status_code != 200:
    print('Token error:', r.text[:500])
    exit(1)

token = r.json().get('access_token', '')
print('Token obtained:', bool(token))
print()

params = {
    'utcStartDate': '2026-03-17T22:00:00Z',
    'utcEndDate': '2026-03-18T21:59:59Z',
    'vehicle_Id': 'dc169f12-4b87-4327-8d4c-500f6faa2d47',
    'vehicleGroup_Id': gid,
    '$format': 'json',
    '$count': 'true',
    '$top': '5',
    '$select': 'id,vehicle_Id,vehicle_Description,duration,distance,startUtcTimestamp,endUtcTimestamp'
}

print('Calling Trips API...')
tr = requests.get(
    'https://live.mzoneweb.net/mzone62.api/Trips',
    headers={'Authorization': 'Bearer ' + token},
    params=params,
    timeout=30
)
print('Trips status:', tr.status_code)
print('Trips response:', tr.text[:800])
