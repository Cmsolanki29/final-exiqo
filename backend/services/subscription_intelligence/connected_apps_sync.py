"""Normalize device-linked packages into `connected_apps` (one row per user per package)."""
from __future__ import annotations

import json
from typing import Any

from psycopg2.extensions import connection as PgConnection


def _label_from_package(pkg: str) -> str:
    """Humanize package id; prefer explicit map so chips stay distinct (avoids duplicate 'Android' / 'Music')."""
    p = (pkg or "").strip()
    if not p:
        return "App"
    known = {
        "com.netflix.mediaclient": "Netflix",
        "com.spotify.music": "Spotify",
        "com.google.android.youtube": "YouTube Premium",
        "com.linkedin.android": "LinkedIn",
        "in.startv.hotstar": "Hotstar",
        "in.amazon.mShop.android.shopping": "Amazon / Prime",
        "com.openai.chatgpt": "ChatGPT",
        "com.notion.android": "Notion",
        "com.canva.editor": "Canva",
        "com.adobe.reader": "Adobe Reader",
        "com.gaana": "Gaana",
        "com.apple.android.music": "Apple Music",
        "com.google.android.apps.youtube.music": "YouTube Music",
        "com.android.vending": "Play Store",
        "com.google.android.gms": "Google Play services",
    }
    if p in known:
        return known[p]
    parts = p.lower().split(".")
    if len(parts) >= 2 and parts[-1] == "android" and parts[-2] not in ("google", "android"):
        seg = parts[-2].replace("_", " ")
        if seg:
            return seg[:1].upper() + seg[1:]
    tail = p.split(".")[-1].replace("_", " ")
    if not tail:
        return p
    return tail[:1].upper() + tail[1:]


def sync_connected_apps_for_user(conn: PgConnection, user_id: int) -> list[dict[str, Any]]:
    """
    Upsert rows from `device_links.apps_linked` and mark packages no longer selected as revoked.
    SIMULATED: production syncs from Android companion SDK registration events.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, apps_linked
            FROM device_links
            WHERE user_id = %s AND link_status = 'active'
            ORDER BY linked_at DESC
            LIMIT 1;
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                UPDATE connected_apps SET link_status = 'revoked', updated_at = NOW()
                WHERE user_id = %s AND link_status = 'active';
                """,
                (user_id,),
            )
            return []

        device_link_id, raw_apps = int(row[0]), row[1]
        if isinstance(raw_apps, str):
            apps = json.loads(raw_apps) if raw_apps else []
        else:
            apps = list(raw_apps or [])
        pkgs = [str(p).strip() for p in apps if str(p).strip()]
        if not pkgs:
            cur.execute(
                """
                UPDATE connected_apps SET link_status = 'revoked', updated_at = NOW()
                WHERE user_id = %s AND link_status = 'active';
                """,
                (user_id,),
            )
            return []

        for pkg in pkgs:
            label = _label_from_package(pkg)
            cur.execute(
                """
                INSERT INTO connected_apps (
                  user_id, app_package, display_label, link_status, device_link_id, metadata, updated_at
                ) VALUES (%s, %s, %s, 'active', %s, '{}'::jsonb, NOW())
                ON CONFLICT (user_id, app_package) DO UPDATE SET
                  display_label = COALESCE(EXCLUDED.display_label, connected_apps.display_label),
                  link_status = 'active',
                  device_link_id = EXCLUDED.device_link_id,
                  updated_at = NOW();
                """,
                (user_id, pkg, label, device_link_id),
            )

        cur.execute(
            """
            UPDATE connected_apps SET link_status = 'revoked', updated_at = NOW()
            WHERE user_id = %s
              AND link_status = 'active'
              AND NOT (app_package = ANY(%s::varchar[]));
            """,
            (user_id, pkgs),
        )

        cur.execute(
            """
            SELECT app_package, display_label, link_status, updated_at
            FROM connected_apps
            WHERE user_id = %s AND link_status = 'active'
            ORDER BY display_label NULLS LAST, app_package;
            """,
            (user_id,),
        )
        out = []
        for r in cur.fetchall():
            out.append(
                {
                    "app_package": r[0],
                    "display_label": r[1] or _label_from_package(str(r[0])),
                    "link_status": r[2],
                    "updated_at": r[3].isoformat() if r[3] else None,
                }
            )
        return out
    finally:
        cur.close()


def log_subscription_event(
    conn: PgConnection,
    user_id: int,
    event_type: str,
    *,
    subscription_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO subscription_events (user_id, subscription_id, event_type, payload)
            VALUES (%s, %s, %s, %s::jsonb);
            """,
            (
                user_id,
                subscription_id,
                event_type,
                json.dumps(payload or {}),
            ),
        )
    finally:
        cur.close()
