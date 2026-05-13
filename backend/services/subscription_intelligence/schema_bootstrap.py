"""
Apply subscription-intelligence DDL when the DB is behind migrations.

Local/demo DBs sometimes skip `python -m scripts.apply_migrations`; missing columns
then surface as psycopg2.errors.UndefinedColumn on /subscription-intelligence/* routes.
This module replays migration 021 idempotently (ADD COLUMN IF NOT EXISTS, CREATE IF NOT EXISTS).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from psycopg2.extensions import connection as PgConnection

logger = logging.getLogger(__name__)

_BOOT_LOCK = threading.Lock()
_SCHEMA_OK = False

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "database" / "migrations" / "021_subscription_intelligence.sql"
)


def _intel_schema_ready(cur) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'subscriptions'
          AND column_name = 'intelligence_category'
        LIMIT 1;
        """
    )
    if cur.fetchone():
        return True
    return False


def _device_links_table_ready(cur) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'device_links'
        LIMIT 1;
        """
    )
    return cur.fetchone() is not None


def _run_migration_statements(cur, sql_text: str) -> None:
    lines: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    for part in cleaned.split(";"):
        stmt = part.strip()
        if not stmt:
            continue
        cur.execute(stmt + ";")


def ensure_subscription_intelligence_schema(conn: PgConnection) -> None:
    """No-op when schema already matches migration 021; otherwise apply 021 DDL and commit."""
    global _SCHEMA_OK
    if _SCHEMA_OK:
        return

    with _BOOT_LOCK:
        if _SCHEMA_OK:
            return

        cur = conn.cursor()
        try:
            if _intel_schema_ready(cur) and _device_links_table_ready(cur):
                _SCHEMA_OK = True
                return

            if not _MIGRATION_PATH.is_file():
                raise FileNotFoundError(
                    f"Subscription intelligence migration missing at {_MIGRATION_PATH}. "
                    "Run: cd backend && python -m scripts.apply_migrations"
                )

            sql_text = _MIGRATION_PATH.read_text(encoding="utf-8")
            # psycopg2 does not reliably accept multi-statement strings; apply one statement at a time.
            _run_migration_statements(cur, sql_text)

            conn.commit()
            _SCHEMA_OK = True
            logger.info("Subscription intelligence schema (021) ensured on database.")
        except Exception:
            conn.rollback()
            logger.exception("Failed to bootstrap subscription intelligence schema")
            raise
        finally:
            cur.close()
