"""
Apply subscription-intelligence DDL when the DB is behind migrations.

Replays 021, 022, then 023 (categories + savings + usage helper) idempotently.
SIMULATED boundary comments live in migration files for mobile SDK areas.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from psycopg2.extensions import connection as PgConnection

logger = logging.getLogger(__name__)

_BOOT_LOCK = threading.Lock()
_SCHEMA_OK = False

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
_M021 = _MIGRATIONS_DIR / "021_subscription_intelligence.sql"
_M022 = _MIGRATIONS_DIR / "022_subscription_intelligence_platform.sql"
_M023 = _MIGRATIONS_DIR / "023_subscription_intelligence_categories_savings.sql"


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
    return cur.fetchone() is not None


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


def _platform_022_ready(cur) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'connected_apps'
        LIMIT 1;
        """
    )
    return cur.fetchone() is not None


def _platform_023_ready(cur) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'subscription_categories'
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


def _apply_file_if_exists(cur: PgConnection, path: Path) -> bool:
    if not path.is_file():
        logger.warning("Migration file missing: %s", path)
        return False
    _run_migration_statements(cur, path.read_text(encoding="utf-8"))
    return True


def _apply_file_whole(cur: PgConnection, path: Path) -> bool:
    """Run migration as one script (required when file contains PL/pgSQL $$ blocks)."""
    if not path.is_file():
        logger.warning("Migration file missing: %s", path)
        return False
    cur.execute(path.read_text(encoding="utf-8"))
    return True


def ensure_subscription_intelligence_schema(conn: PgConnection) -> None:
    """Apply 021 + 022 + 023 when needed; commit once if any DDL ran."""
    global _SCHEMA_OK
    if _SCHEMA_OK:
        return

    with _BOOT_LOCK:
        if _SCHEMA_OK:
            return

        cur = conn.cursor()
        try:
            need_021 = not (_intel_schema_ready(cur) and _device_links_table_ready(cur))
            need_022 = not _platform_022_ready(cur)
            need_023 = not _platform_023_ready(cur)
            if not need_021 and not need_022 and not need_023:
                _SCHEMA_OK = True
                return

            if need_021:
                if not _apply_file_if_exists(cur, _M021):
                    raise FileNotFoundError(
                        f"Missing {_M021.name}. Run: cd backend && python -m scripts.apply_migrations"
                    )
                logger.info("Applied subscription intelligence migration 021.")

            if need_022:
                if not _apply_file_if_exists(cur, _M022):
                    raise FileNotFoundError(
                        f"Missing {_M022.name}. Run: cd backend && python -m scripts.apply_migrations"
                    )
                logger.info("Applied subscription intelligence migration 022.")

            if need_023:
                if not (_intel_schema_ready(cur) and _device_links_table_ready(cur) and _platform_022_ready(cur)):
                    raise RuntimeError(
                        "Migration 023 requires 021+022 to be applied first (app_usage_signals, reminder_outcomes)."
                    )
                if not _apply_file_whole(cur, _M023):
                    raise FileNotFoundError(
                        f"Missing {_M023.name}. Run: cd backend && python -m scripts.apply_migrations"
                    )
                logger.info("Applied subscription intelligence migration 023.")

            conn.commit()

            cur2 = conn.cursor()
            try:
                _SCHEMA_OK = (
                    _intel_schema_ready(cur2)
                    and _device_links_table_ready(cur2)
                    and _platform_022_ready(cur2)
                    and _platform_023_ready(cur2)
                )
            finally:
                cur2.close()

            if _SCHEMA_OK:
                logger.info("Subscription intelligence schema (021+022+023) verified.")
        except Exception:
            conn.rollback()
            logger.exception("Failed to bootstrap subscription intelligence schema")
            raise
        finally:
            cur.close()
