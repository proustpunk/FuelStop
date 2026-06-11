import csv
import json
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

CANADIAN_PROVINCES = {'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT'}

def load_stations(csv_path):
    """Load stations from CSV, deduplicate by OPIS ID keeping lowest price."""
    stations = {}
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['State'].strip() in CANADIAN_PROVINCES:
                continue
            opis_id = row['OPIS Truckstop ID'].strip()
            price = float(row['Retail Price'])
            if opis_id not in stations or price < stations[opis_id]['price']:
                stations[opis_id] = {
                    'id': opis_id,
                    'name': row['Truckstop Name'].strip(),
                    'address': row['Address'].strip(),
                    'city': row['City'].strip(),
                    'state': row['State'].strip(),
                    'price': price,
                }
    return list(stations.values())


def geocode_unique_cities(stations):
    """
    Instead of geocoding 6000 stations, geocode ~800 unique city/state combos.
    Then assign those coords to all stations in that city.
    ~15 minutes instead of ~2 hours.
    """
    geolocator = Nominatim(user_agent="fuel_route_app", timeout=10)

    # Find unique city+state combos
    unique_cities = list({(s['city'], s['state']) for s in stations})
    total = len(unique_cities)
    print(f"Unique city/state combos: {total}")

    city_coords = {}
    failed = []

    for i, (city, state) in enumerate(unique_cities):
        query = f"{city}, {state}, USA"
        key = f"{city}|{state}"
        try:
            location = geolocator.geocode(query)
            if location:
                city_coords[key] = {
                    'lat': location.latitude,
                    'lng': location.longitude
                }
            else:
                failed.append(key)

            if (i + 1) % 50 == 0:
                print(f"Progress: {i+1}/{total} | OK: {len(city_coords)} | Failed: {len(failed)}")

            time.sleep(1)  # Nominatim rate limit

        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Error on {query}: {e}")
            failed.append(key)
            time.sleep(2)

    print(f"\nGeocoding done. OK: {len(city_coords)} | Failed: {len(failed)}")
    return city_coords, failed


def assign_coords_to_stations(stations, city_coords):
    """Assign geocoded city coords to each station. Drop stations with no coords."""
    geocoded = []
    dropped = []
    for s in stations:
        key = f"{s['city']}|{s['state']}"
        if key in city_coords:
            s['lat'] = city_coords[key]['lat']
            s['lng'] = city_coords[key]['lng']
            geocoded.append(s)
        else:
            dropped.append(s)
    print(f"Assigned coords: {len(geocoded)} | Dropped (no coords): {len(dropped)}")
    return geocoded


if __name__ == '__main__':
    CSV_PATH = 'fuel-prices-for-be-assessment__1_.csv'

    print("Loading stations from CSV...")
    stations = load_stations(CSV_PATH)
    print(f"Loaded {len(stations)} unique US stations")

    print("\nGeocoding unique cities (this takes ~15 minutes)...")
    city_coords, failed_cities = geocode_unique_cities(stations)

    # Save city coords cache in case you need to rerun
    with open('city_coords_cache.json', 'w') as f:
        json.dump(city_coords, f)
    print("Saved city coords cache to city_coords_cache.json")

    print("\nAssigning coordinates to stations...")
    geocoded_stations = assign_coords_to_stations(stations, city_coords)

    with open('stations.json', 'w') as f:
        json.dump(geocoded_stations, f, indent=2)
    print(f"\nDone! Saved {len(geocoded_stations)} stations to stations.json")