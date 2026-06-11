import requests

key = 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjU5ODhlMzY0YWM4NTQzNGNhMTNmYmRiMjQ1NTBiZDVjIiwiaCI6Im11cm11cjY0In0='

url = 'https://api.openrouteservice.org/v2/directions/driving-car/geojson'
headers = {
    'Authorization': key,
    'Content-Type': 'application/json',
}
body = {
    'coordinates': [[-74.005974, 40.712776], [-118.243683, 34.052235]],
    'alternative_routes': {
        'target_count': 3,
        'weight_factor': 1.6,
        'share_factor': 0.6,
    },
    'geometry': True,
}
r = requests.post(url, json=body, headers=headers, timeout=30)
print('Status:', r.status_code)
print('Response:', r.json())