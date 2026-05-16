"""
Trip Planner › Places / attractions tool.

Uses free OpenStreetMap + Overpass — no API key required. Returns real
attractions, food spots, and "alternatives near you" categories for the
agent to weave into itineraries. Degrades gracefully if either service
is unreachable.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

_log = logging.getLogger(__name__)

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_USER_AGENT = "SmartSpend-TripPlanner/1.0 (https://smartspend.app)"


_CATEGORY_QUERIES: dict[str, str] = {
    # Tourism nodes within 5km
    "attractions": '(node["tourism"~"attraction|museum|viewpoint|artwork|gallery"](around:5000,{lat},{lon}););out 25;',
    # Restaurants within 3km
    "food": '(node["amenity"~"restaurant|cafe"](around:3000,{lat},{lon}););out 25;',
    # Outdoor / activity venues within 10km
    "activities": '(node["leisure"~"park|nature_reserve|water_park|sports_centre"](around:10000,{lat},{lon}););out 25;',
    # When asking for alternative destinations nearby, search a wider radius for
    # towns/villages that have at least some tourism tagging.
    "alternatives_nearby": '(node["place"~"city|town|village"](around:200000,{lat},{lon}););out 30;',
}


def _geocode(client: httpx.Client, location: str) -> dict[str, float] | None:
    try:
        res = client.get(
            _NOMINATIM_URL,
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": _USER_AGENT},
        )
        if res.status_code != 200:
            return None
        data = res.json() or []
        if not data:
            return None
        return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    except Exception as exc:  # noqa: BLE001
        _log.warning("[trip-planner.places] geocode failed for '%s': %s", location, exc)
        return None


def explore_places(
    location: str,
    category: str,
    user_city: str | None = None,
) -> dict[str, Any]:
    norm_category = (category or "attractions").strip().lower()
    if norm_category not in _CATEGORY_QUERIES:
        norm_category = "attractions"

    base_payload = {
        "location": location,
        "category": norm_category,
        "queried_at": datetime.utcnow().isoformat() + "Z",
    }

    # For alternatives_nearby, anchor on user's home city when provided.
    geocode_target = user_city if (norm_category == "alternatives_nearby" and user_city) else location

    try:
        with httpx.Client(timeout=15.0, headers={"User-Agent": _USER_AGENT}) as client:
            coords = _geocode(client, geocode_target)
            if not coords:
                return {
                    **base_payload,
                    "data_source": "openstreetmap_live",
                    "fallback": True,
                    "note": f"Could not geocode '{geocode_target}'. Use general knowledge.",
                }

            query = _CATEGORY_QUERIES[norm_category].format(lat=coords["lat"], lon=coords["lon"])
            res = client.get(_OVERPASS_URL, params={"data": f"[out:json];{query}"})
            if res.status_code != 200:
                return {
                    **base_payload,
                    "anchor": geocode_target,
                    "coordinates": coords,
                    "data_source": "openstreetmap_live",
                    "fallback": True,
                    "note": f"Overpass returned HTTP {res.status_code}.",
                }
            elements = (res.json() or {}).get("elements") or []
    except Exception as exc:  # noqa: BLE001
        _log.warning("[trip-planner.places] live call failed: %s", exc)
        return {
            **base_payload,
            "data_source": "general_knowledge",
            "fallback": True,
            "note": f"Places provider error ({type(exc).__name__}).",
        }

    places: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        item: dict[str, Any] = {
            "name": name,
            "lat": el.get("lat"),
            "lon": el.get("lon"),
        }
        if norm_category == "attractions":
            item["type"] = tags.get("tourism")
        elif norm_category == "food":
            item["type"] = tags.get("amenity")
            if tags.get("cuisine"):
                item["cuisine"] = tags["cuisine"]
        elif norm_category == "activities":
            item["type"] = tags.get("leisure")
        elif norm_category == "alternatives_nearby":
            item["type"] = tags.get("place")
        places.append(item)
        if len(places) >= 12:
            break

    return {
        **base_payload,
        "anchor": geocode_target,
        "coordinates": coords,
        "places": places,
        "data_source": "openstreetmap_live",
        "fallback": not places,
    }


__all__ = ["explore_places"]
