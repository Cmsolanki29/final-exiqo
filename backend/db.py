"""Sync PostgreSQL access (psycopg2) for SmartSpend API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import psycopg2
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env", override=True)


def get_db_config() -> dict[str, str | int]:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "smartspend_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def get_connection():
    return psycopg2.connect(**get_db_config())


def get_db() -> Generator:
    """FastAPI dependency: one connection per request (commits on success)."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_db_connection() -> bool:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone()[0] == 1
    except Exception:
        return False
