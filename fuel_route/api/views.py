import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import RouteRequestSerializer
from .services.routing import geocode, get_routes
from .services.stations import snap_stations_to_route, load_stations
from .services.algorithm import compute_min_fuel_cost

logger = logging.getLogger(__name__)

# ── Load stations once at startup into module-level variable ──────────────────
# This means the JSON file is read ONCE when Django starts, not on every request
try:
    ALL_STATIONS = load_stations()
    logger.info(f"Loaded {len(ALL_STATIONS)} stations into memory")
except FileNotFoundError:
    ALL_STATIONS = []
    logger.warning("stations.json not found. Run geocode_stations.py first.")


class RouteView(APIView):

    def post(self, request):
        # ── 1. Validate input ─────────────────────────────────────────────────
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start = serializer.validated_data['start']
        end = serializer.validated_data['end']

        # ── 2. Geocode start and end ──────────────────────────────────────────
        try:
            start_coords = geocode(start)   # [lng, lat]
            end_coords = geocode(end)       # [lng, lat]
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return Response(
                {'error': 'Geocoding service unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # ── 3. Get routes from ORS (1 API call) ───────────────────────────────
        try:
            routes = get_routes(start_coords, end_coords)
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return Response(
                {'error': 'Routing service unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        if not routes:
            return Response(
                {'error': 'No routes found between these locations'},
                status=status.HTTP_404_NOT_FOUND
            )

        # ── 4. For each route, snap stations + run DP ─────────────────────────
        best_route = None
        best_cost = float('inf')
        best_stops = []
        best_stations_on_route = []

        for route in routes:
            polyline = route['polyline']
            total_miles = route['distance_miles']

            # Find stations along this route
            stations_on_route = snap_stations_to_route(ALL_STATIONS, polyline)

            # Run DP optimizer
            cost, stops = compute_min_fuel_cost(stations_on_route, total_miles)
            print(f"DEBUG cost: {cost}, stops: {len(stops) if stops else 0}")
            # Skip infeasible routes (no stations within 500mi gap)
            if cost is None:
                continue

            if cost < best_cost:
                best_cost = cost
                best_route = route
                best_stops = stops
                best_stations_on_route = stations_on_route

        if best_route is None:
            return Response(
                {'error': 'No feasible route found. Stations may be too far apart.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        # ── 5. Build response ─────────────────────────────────────────────────
        total_gallons = best_route['distance_miles'] / 10  # 10 MPG

        response_data = {
            'summary': {
                'start': start,
                'end': end,
                'total_miles': best_route['distance_miles'],
                'total_gallons_used': round(total_gallons, 2),
                'total_fuel_cost_usd': best_cost,
                'number_of_stops': len(best_stops),
                'duration_hours': round(best_route['duration_seconds'] / 3600, 2),
            },
            'fuel_stops': [
                {
                    'order': i + 1,
                    'name': stop['name'],
                    'address': stop['address'],
                    'city': stop['city'],
                    'state': stop['state'],
                    'price_per_gallon': stop['price'],
                    'lat': stop['lat'],
                    'lng': stop['lng'],
                    'miles_from_start': stop['dist_from_start'],
                }
                for i, stop in enumerate(best_stops)
            ],
            'route': {
                'type': 'FeatureCollection',
                'features': [
                    {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': best_route['polyline'],
                        },
                        'properties': {
                            'distance_miles': best_route['distance_miles'],
                            'duration_hours': round(
                                best_route['duration_seconds'] / 3600, 2
                            ),
                        }
                    },
                    # Fuel stop markers as GeoJSON points
                    *[
                        {
                            'type': 'Feature',
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [stop['lng'], stop['lat']],
                            },
                            'properties': {
                                'name': stop['name'],
                                'price_per_gallon': stop['price'],
                                'city': stop['city'],
                                'state': stop['state'],
                                'order': i + 1,
                            }
                        }
                        for i, stop in enumerate(best_stops)
                    ]
                ]
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)