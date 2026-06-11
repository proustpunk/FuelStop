import requests
from django.conf import settings


ORS_BASE = 'https://api.openrouteservice.org'


def geocode(place_name):
    """Convert place name to [lng, lat]."""
    url = f"{ORS_BASE}/geocode/search"
    params = {
        'api_key': settings.ORS_API_KEY,
        'text': f"{place_name}, USA",
        'size': 1,
        'boundary.country': 'US',
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    features = r.json().get('features', [])
    if not features:
        raise ValueError(f"Could not geocode: {place_name}")
    coords = features[0]['geometry']['coordinates']  # [lng, lat]
    return coords

def get_routes(start_coords, end_coords):
    """
    Get the best route from ORS.
    Note: alternative_routes only works for <100km on free tier.
    We get 1 optimal route and run our fuel DP on it.
    """
    url = f"{ORS_BASE}/v2/directions/driving-car/geojson"
    headers = {
        'Authorization': settings.ORS_API_KEY,
        'Content-Type': 'application/json',
    }
    body = {
        'coordinates': [start_coords, end_coords],
        'geometry': True,
    }
    r = requests.post(url, json=body, headers=headers, timeout=30)
    r.raise_for_status()

    data = r.json()
    routes = []
    for feature in data.get('features', []):
        props = feature['properties']['summary']
        coords = feature['geometry']['coordinates']
        distance_meters = props['distance']
        routes.append({
            'polyline': coords,
            'distance_miles': round(distance_meters * 0.000621371, 2),
            'duration_seconds': props['duration'],
        })
    return routes