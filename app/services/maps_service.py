import math

import httpx

from app.core.config import get_settings

# Seed coordinates so matching works locally without a Maps key.
NAIROBI_PLACES: dict[str, tuple[float, float]] = {
    "kileleshwa": (-1.2806, 36.7825),
    "kilimani": (-1.2916, 36.7870),
    "westlands": (-1.2674, 36.8110),
    "lavington": (-1.2760, 36.7750),
    "ngara": (-1.2745, 36.8290),
    "eastleigh": (-1.2730, 36.8470),
    "south b": (-1.3105, 36.8375),
    "south c": (-1.3180, 36.8280),
    "langata": (-1.3380, 36.7760),
    "karen": (-1.3197, 36.7114),
    "cbd": (-1.2864, 36.8172),
    "nairobi": (-1.2921, 36.8219),
    "parklands": (-1.2618, 36.8168),
    "hurlingham": (-1.2935, 36.7965),
    "riverside": (-1.2715, 36.8050),
}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return round(2 * radius * math.asin(math.sqrt(a)), 3)


def geocode(place: str) -> tuple[float, float] | None:
    if not place:
        return None
    key = place.strip().lower()
    for name, coords in NAIROBI_PLACES.items():
        if name in key or key in name:
            return coords

    settings = get_settings()
    if not settings.maps_configured:
        return None

    params = {
        "address": f"{place}, Nairobi, Kenya",
        "key": settings.google_maps_api_key,
    }
    try:
        response = httpx.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params=params,
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return None
        location = results[0]["geometry"]["location"]
        return float(location["lat"]), float(location["lng"])
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None


def distance_km(
    origin: tuple[float, float] | None,
    dest_lat: float | None,
    dest_lng: float | None,
) -> float | None:
    if origin is None or dest_lat is None or dest_lng is None:
        return None
    return haversine_km(origin[0], origin[1], dest_lat, dest_lng)
