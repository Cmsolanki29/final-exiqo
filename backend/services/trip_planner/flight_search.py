"""
Trip Planner › Flight search tool.

Uses Amadeus Self-Service API (test env) when AMADEUS_API_KEY + secret are set.
Token is cached for ~25 minutes in-process. Without credentials, returns a
`fallback: true` payload so the LLM may estimate with general knowledge.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from typing import Any

import httpx

_log = logging.getLogger(__name__)

_AMA_BASE = "https://test.api.amadeus.com"
_TOKEN_URL = f"{_AMA_BASE}/v1/security/oauth2/token"
_LOC_URL = f"{_AMA_BASE}/v1/reference-data/locations"
_OFFERS_URL = f"{_AMA_BASE}/v2/shopping/flight-offers"

_token_lock = threading.Lock()
_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}
_iata_cache: dict[str, str] = {}


def _get_token(client: httpx.Client, key: str, secret: str) -> str | None:
    with _token_lock:
        now = time.time()
        if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
            return _token_cache["token"]
        try:
            res = client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": key,
                    "client_secret": secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            res.raise_for_status()
            payload = res.json()
            token = payload.get("access_token")
            ttl = int(payload.get("expires_in") or 1700)
            if token:
                _token_cache["token"] = token
                _token_cache["expires_at"] = now + ttl
            return token
        except Exception as exc:  # noqa: BLE001
            _log.warning("[trip-planner.flights] token fetch failed: %s", exc)
            return None


def _resolve_iata(client: httpx.Client, token: str, city: str) -> str | None:
    key = city.strip().lower()
    if not key:
        return None
    if key in _iata_cache:
        return _iata_cache[key]

    try:
        res = client.get(
            _LOC_URL,
            params={
                "subType": "CITY,AIRPORT",
                "keyword": city,
                "page[limit]": 5,
                "view": "LIGHT",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if res.status_code != 200:
            return None
        data = (res.json() or {}).get("data") or []
        for item in data:
            iata = item.get("iataCode")
            if iata and len(iata) == 3:
                _iata_cache[key] = iata
                return iata
    except Exception as exc:  # noqa: BLE001
        _log.warning("[trip-planner.flights] IATA resolve failed for '%s': %s", city, exc)
    return None


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    travelers: int = 1,
) -> dict[str, Any]:
    api_key = (os.getenv("AMADEUS_API_KEY") or "").strip()
    api_secret = (os.getenv("AMADEUS_API_SECRET") or "").strip()

    base_payload = {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "travelers": travelers,
        "queried_at": datetime.utcnow().isoformat() + "Z",
    }

    if not api_key or not api_secret:
        return {
            **base_payload,
            "data_source": "general_estimate",
            "fallback": True,
            "note": "Live flight provider not configured. Estimate using general market knowledge for this route.",
        }

    try:
        with httpx.Client(timeout=15.0) as client:
            token = _get_token(client, api_key, api_secret)
            if not token:
                return {
                    **base_payload,
                    "data_source": "general_estimate",
                    "fallback": True,
                    "note": "Amadeus auth failed. Estimate using general market knowledge.",
                }

            origin_iata = _resolve_iata(client, token, origin)
            dest_iata = _resolve_iata(client, token, destination)
            if not origin_iata or not dest_iata:
                return {
                    **base_payload,
                    "data_source": "amadeus_live",
                    "fallback": True,
                    "note": "Could not resolve IATA airport codes. Estimate using general market knowledge.",
                    "resolved_origin_iata": origin_iata,
                    "resolved_destination_iata": dest_iata,
                }

            res = client.get(
                _OFFERS_URL,
                params={
                    "originLocationCode": origin_iata,
                    "destinationLocationCode": dest_iata,
                    "departureDate": departure_date,
                    "adults": max(1, int(travelers)),
                    "currencyCode": "INR",
                    "max": 5,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            if res.status_code != 200:
                return {
                    **base_payload,
                    "data_source": "amadeus_live",
                    "fallback": True,
                    "note": f"Amadeus returned HTTP {res.status_code}. Estimate using general market knowledge.",
                }

            offers_raw = (res.json() or {}).get("data") or []

    except Exception as exc:  # noqa: BLE001
        _log.warning("[trip-planner.flights] live call failed: %s", exc)
        return {
            **base_payload,
            "data_source": "general_estimate",
            "fallback": True,
            "note": f"Flight provider error ({type(exc).__name__}). Estimate using general market knowledge.",
        }

    offers: list[dict[str, Any]] = []
    for offer in offers_raw[:5]:
        try:
            price_total = float((offer.get("price") or {}).get("total") or 0.0)
            itineraries = offer.get("itineraries") or []
            first = itineraries[0] if itineraries else {}
            segments = first.get("segments") or []
            airline = (offer.get("validatingAirlineCodes") or [None])[0]
            duration = first.get("duration")
            offers.append(
                {
                    "price_inr": round(price_total, 2),
                    "airline": airline,
                    "duration_iso8601": duration,
                    "stops": max(0, len(segments) - 1),
                }
            )
        except Exception:
            continue

    cheapest = min((o["price_inr"] for o in offers), default=None)
    return {
        **base_payload,
        "resolved_origin_iata": origin_iata,
        "resolved_destination_iata": dest_iata,
        "offers": offers,
        "cheapest_inr": cheapest,
        "data_source": "amadeus_live",
        "fallback": cheapest is None,
    }


__all__ = ["search_flights"]
