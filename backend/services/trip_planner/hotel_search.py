"""
Trip Planner › Hotel search tool.

Uses Booking.com via RapidAPI when RAPIDAPI_KEY is set. Falls back to a
graceful general-knowledge payload otherwise. We never invent prices in
the fallback path — we simply tell the LLM it must reason from general
market tiers.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

_log = logging.getLogger(__name__)

_BOOKING_HOST = "booking-com.p.rapidapi.com"
_LOCATIONS_URL = f"https://{_BOOKING_HOST}/v1/hotels/locations"
_SEARCH_URL = f"https://{_BOOKING_HOST}/v1/hotels/search"


def _classify_tier(per_night_inr: float) -> str:
    if per_night_inr <= 0:
        return "unknown"
    if per_night_inr < 2500:
        return "budget"
    if per_night_inr < 7000:
        return "mid"
    return "luxury"


def _add_days(check_in_str: str, nights: int) -> str:
    dt = datetime.strptime(check_in_str, "%Y-%m-%d").date()
    return (dt + timedelta(days=max(1, int(nights)))).isoformat()


def search_hotels(
    destination: str,
    check_in: str,
    nights: int,
    guests: int = 2,
) -> dict[str, Any]:
    api_key = (os.getenv("RAPIDAPI_KEY") or "").strip()

    base_payload = {
        "destination": destination,
        "check_in": check_in,
        "nights": nights,
        "guests": guests,
        "queried_at": datetime.utcnow().isoformat() + "Z",
    }

    if not api_key:
        return {
            **base_payload,
            "data_source": "general_estimate",
            "fallback": True,
            "note": "Live hotel provider not configured. Estimate using general market knowledge "
                    "(budget < ₹2,500/night, mid ₹2,500–7,000, luxury > ₹7,000).",
        }

    try:
        check_out = _add_days(check_in, nights)
    except Exception:
        return {
            **base_payload,
            "data_source": "general_estimate",
            "fallback": True,
            "note": "Invalid check-in date format. Expecting YYYY-MM-DD.",
        }

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": _BOOKING_HOST,
    }

    try:
        with httpx.Client(timeout=15.0, headers=headers) as client:
            # 1) Resolve destination id
            loc_res = client.get(
                _LOCATIONS_URL,
                params={"name": destination, "locale": "en-gb"},
            )
            if loc_res.status_code != 200:
                return {
                    **base_payload,
                    "data_source": "general_estimate",
                    "fallback": True,
                    "note": f"Hotel locations lookup HTTP {loc_res.status_code}.",
                }
            locations = loc_res.json() or []
            dest_record = next((loc for loc in locations if loc.get("dest_type") == "city"), None) \
                or (locations[0] if locations else None)
            if not dest_record:
                return {
                    **base_payload,
                    "data_source": "booking_live",
                    "fallback": True,
                    "note": "Could not resolve destination for hotel search.",
                }

            # 2) Search
            search_res = client.get(
                _SEARCH_URL,
                params={
                    "dest_id": dest_record.get("dest_id"),
                    "dest_type": dest_record.get("dest_type"),
                    "checkin_date": check_in,
                    "checkout_date": check_out,
                    "adults_number": max(1, int(guests)),
                    "room_number": 1,
                    "order_by": "popularity",
                    "filter_by_currency": "INR",
                    "locale": "en-gb",
                    "units": "metric",
                },
            )
            if search_res.status_code != 200:
                return {
                    **base_payload,
                    "data_source": "booking_live",
                    "fallback": True,
                    "note": f"Hotel search HTTP {search_res.status_code}.",
                }
            search_data = search_res.json() or {}

    except Exception as exc:  # noqa: BLE001
        _log.warning("[trip-planner.hotels] live call failed: %s", exc)
        return {
            **base_payload,
            "data_source": "general_estimate",
            "fallback": True,
            "note": f"Hotel provider error ({type(exc).__name__}). Estimate using general market knowledge.",
        }

    hotels: list[dict[str, Any]] = []
    results = search_data.get("result") or []
    n_nights = max(1, int(nights))
    for h in results[:10]:
        try:
            min_total = float(h.get("min_total_price") or 0)
            per_night = round(min_total / n_nights, 2) if min_total else 0.0
            hotels.append(
                {
                    "name": h.get("hotel_name"),
                    "price_per_night_inr": per_night,
                    "rating": h.get("review_score"),
                    "tier": _classify_tier(per_night),
                    "city": h.get("city"),
                }
            )
        except Exception:
            continue

    return {
        **base_payload,
        "hotels": hotels[:5],
        "tier_summary": {
            "budget": [h for h in hotels if h["tier"] == "budget"][:3],
            "mid": [h for h in hotels if h["tier"] == "mid"][:3],
            "luxury": [h for h in hotels if h["tier"] == "luxury"][:3],
        },
        "data_source": "booking_live",
        "fallback": not hotels,
    }


__all__ = ["search_hotels"]
