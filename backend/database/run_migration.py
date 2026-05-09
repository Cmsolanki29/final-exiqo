"""
Run SQL migrations against PostgreSQL (uses project root .env).
Usage: python backend/database/run_migration.py
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_ROOT / ".env")


def get_db_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "smartspend_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def run_migration(file_path: Path) -> None:
    conn = psycopg2.connect(**get_db_config())
    conn.autocommit = True
    cur = conn.cursor()
    try:
        sql = file_path.read_text(encoding="utf-8")
        cur.execute(sql)
        print(f"[OK] Migration completed: {file_path}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    run_migration(migrations_dir / "001_add_authentication.sql")
    run_migration(migrations_dir / "002_bank_connections.sql")
    run_migration(migrations_dir / "003_user_important_days.sql")
