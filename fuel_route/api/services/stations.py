import json
import os
import math
from django.conf import settings


def load_stations():
    """Load stations from JSON file into memory at startup."""
    base_dir = settings.BASE_DIR
    path = os.path.join(base_dir, 'stations.json')
    with open(path, 'r') as f:
        return json.load(f)


# --- Haversine distance between two lat/lng points in miles ---
def haversine(lat1, lng1, lat2, lng2):
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def distance_along_route(point_lat, point_lng, polyline):
    """
    Find the closest point on the polyline to the station.
    Returns (min_distance_from_route, distance_from_start_miles).
    polyline is a list of [lng, lat] from ORS.
    """
    min_dist = float('inf')
    best_dist_from_start = 0
    cumulative = 0.0

    for i in range(len(polyline) - 1):
        seg_lat1, seg_lng1 = polyline[i][1], polyline[i][0]
        seg_lat2, seg_lng2 = polyline[i+1][1], polyline[i+1][0]

        # Distance from station to this segment's start point
        d = haversine(point_lat, point_lng, seg_lat1, seg_lng1)

        if d < min_dist:
            min_dist = d
            best_dist_from_start = cumulative + haversine(
                seg_lat1, seg_lng1, point_lat, point_lng
            )

        cumulative += haversine(seg_lat1, seg_lng1, seg_lat2, seg_lng2)

    return min_dist, best_dist_from_start

def get_route_bounding_box(polyline, padding_degrees=0.5):
    """Get bounding box of route with padding."""
    lngs = [p[0] for p in polyline]
    lats = [p[1] for p in polyline]
    return {
        'min_lat': min(lats) - padding_degrees,
        'max_lat': max(lats) + padding_degrees,
        'min_lng': min(lngs) - padding_degrees,
        'max_lng': max(lngs) + padding_degrees,
    }


def filter_stations_by_bbox(stations, bbox):
    """Fast pre-filter using bounding box before expensive haversine."""
    return [
        s for s in stations
        if bbox['min_lat'] <= s['lat'] <= bbox['max_lat']
        and bbox['min_lng'] <= s['lng'] <= bbox['max_lng']
    ]


def snap_stations_to_route(all_stations, polyline, threshold_miles=None):
    """
    Filter stations within threshold_miles of the route polyline.
    Uses bounding box pre-filter for speed.
    Returns stations sorted by distance from start.
    """
    if threshold_miles is None:
        threshold_miles = settings.STATION_SNAP_THRESHOLD_MILES

    # Step 1: Fast bounding box filter (reduces 6624 → ~300 stations)
    bbox = get_route_bounding_box(polyline, padding_degrees=0.5)
    candidate_stations = filter_stations_by_bbox(all_stations, bbox)

    # Step 2: Precise haversine filter on candidates only
    # Also reduce polyline resolution for speed - check every 10th point
    reduced_polyline = polyline[::10]

    snapped = []
    for station in candidate_stations:
        dist_from_route, dist_from_start = distance_along_route(
            station['lat'], station['lng'], reduced_polyline
        )
        if dist_from_route <= threshold_miles:
            snapped.append({
                **station,
                'dist_from_route': round(dist_from_route, 2),
                'dist_from_start': round(dist_from_start, 2),
            })

    snapped.sort(key=lambda s: s['dist_from_start'])
    return snapped