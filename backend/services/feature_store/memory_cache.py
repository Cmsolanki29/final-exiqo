"""Process-local feature cache used when Redis is unavailable."""

from __future__ import annotations

import json
import time
from typing import Any

_store: dict[str, tuple[dict[str, Any], float]] = {}
_DEFAULT_TTL_SEC = 86400


def _key(entity_type: str, entity_id: str) -> str:
    return f"{entity_type}:{entity_id}"


def get(entity_type: str, entity_id: str) -> dict[str, Any] | None:
    entry = _store.get(_key(entity_type, entity_id))
    if entry is None:
        return None
    features, expires_at = entry
    if time.time() > expires_at:
        _store.pop(_key(entity_type, entity_id), None)
        return None
    return dict(features)


def set(
    entity_type: str,
    entity_id: str,
    features: dict[str, Any],
    ttl_sec: int = _DEFAULT_TTL_SEC,
) -> None:
    _store[_key(entity_type, entity_id)] = (
        dict(features),
        time.time() + max(ttl_sec, 60),
    )


def merge(
    entity_type: str,
    entity_id: str,
    features: dict[str, Any],
    ttl_sec: int = _DEFAULT_TTL_SEC,
) -> None:
    existing = get(entity_type, entity_id) or {}
    set(entity_type, entity_id, {**existing, **features}, ttl_sec=ttl_sec)


def delete(entity_type: str, entity_id: str) -> None:
    _store.pop(_key(entity_type, entity_id), None)
