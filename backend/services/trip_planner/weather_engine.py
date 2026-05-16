"""
Trip Planner › Weather tool.

Live weather via OpenWeatherMap when OPENWEATHERMAP_API_KEY is set. Degrades
gracefully when the key is missing or the destination cannot be geocoded —
returning a `fallback: true` flag so the LLM uses general seasonal knowledge
instead of hardcoded fake data.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx

_log = logging.getLogger(__name__)

_OWM_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
_OWM_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
_OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def _india_seasonal_hint(destination: str, month: str | None) -> dict[str, Any]:
    """Compact season metadata for India — gives the LLM context, not numbers."""
    return {
        "regional_calendar": "indian",
        "seasons": {
            "winter": "Nov–Feb (cool, peak for hill stations south of Manali; northern hills snow Dec–Feb)",
            "summer": "Mar–May (hot in plains, ideal for high-altitude trips like Ladakh, Spiti, Kashmir)",
            "monsoon": "Jun–Sep (heavy rain in Western Ghats, Kerala, NE India; avoid trekking)",
            "post_monsoon": "Oct–Nov (best overall window for most Indian destinations)",
        },
        "queried_month": month,
        "queried_destination": destination,
        "note": "Use these patterns plus general knowledge to recommend the best month.",
    }


def get_weather_for_destination(destination: str, month: str | None = None) -> dict[str, Any]:
    api_key = (os.getenv("OPENWEATHERMAP_API_KEY") or "").strip()

    if not api_key:
        return {
            "destination": destination,
            "queried_at": datetime.utcnow().isoformat() + "Z",
            "data_source": "general_knowledge",
            "fallback": True,
            "note": "Live weather provider not configured. Use general seasonal knowledge.",
            "seasonal_hint": _india_seasonal_hint(destination, month),
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            # 1) Geocode
            geo_res = client.get(
                _OWM_GEO_URL,
                params={"q": destination, "limit": 1, "appid": api_key},
            )
            geo_res.raise_for_status()
            geo = geo_res.json()
            if not geo:
                return {
                    "destination": destination,
                    "error": "location_not_found",
                    "fallback": True,
                    "data_source": "openweathermap_live",
                    "seasonal_hint": _india_seasonal_hint(destination, month),
                }
            place = geo[0]
            lat, lon = float(place["lat"]), float(place["lon"])
            resolved_name = place.get("name") or destination
            country = place.get("country")

            # 2) Current weather
            wx_res = client.get(
                _OWM_WEATHER_URL,
                params={"lat": lat, "lon": lon, "units": "metric", "appid": api_key},
            )
            wx_res.raise_for_status()
            wx = wx_res.json()

            # 3) 5-day / 3-hour forecast — summarise into temp range
            fc_res = client.get(
                _OWM_FORECAST_URL,
                params={"lat": lat, "lon": lon, "units": "metric", "appid": api_key, "cnt": 8 * 5},
            )
            forecast_summary: dict[str, Any] = {}
            if fc_res.status_code == 200:
                fc = fc_res.json()
                temps = [
                    float(item["main"]["temp"])
                    for item in (fc.get("list") or [])
                    if isinstance(item, dict) and item.get("main")
                ]
                if temps:
                    forecast_summary = {
                        "next_5_days_min_c": round(min(temps), 1),
                        "next_5_days_max_c": round(max(temps), 1),
                        "next_5_days_avg_c": round(sum(temps) / len(temps), 1),
                    }

    except Exception as exc:  # noqa: BLE001
        _log.warning("[trip-planner.weather] live call failed for '%s': %s", destination, exc)
        return {
            "destination": destination,
            "error": str(exc)[:120],
            "fallback": True,
            "data_source": "openweathermap_live",
            "seasonal_hint": _india_seasonal_hint(destination, month),
        }

    main = wx.get("main") or {}
    weather_arr = wx.get("weather") or [{}]
    wind = wx.get("wind") or {}

    return {
        "destination": resolved_name,
        "country": country,
        "coordinates": {"lat": lat, "lon": lon},
        "current": {
            "temp_c": main.get("temp"),
            "feels_like_c": main.get("feels_like"),
            "humidity_pct": main.get("humidity"),
            "condition": (weather_arr[0] or {}).get("description"),
            "wind_kmh": round(float(wind.get("speed") or 0) * 3.6, 1),
        },
        "forecast": forecast_summary,
        "queried_month": month,
        "queried_at": datetime.utcnow().isoformat() + "Z",
        "data_source": "openweathermap_live",
        "seasonal_hint": _india_seasonal_hint(resolved_name, month),
    }


__all__ = ["get_weather_for_destination"]
