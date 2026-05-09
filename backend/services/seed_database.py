"""
Database seeding script
Loads all bank CSV files into PostgreSQL (SmartSpend schema).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from bank_parser import parse_bank_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "smartspend_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}


def _txn_features(txn_date: date, txn_time: time) -> tuple[int, int, bool, bool]:
    dt = datetime.combine(txn_date, txn_time)
    dow = int(dt.weekday())
    hour = int(txn_time.hour)
    is_weekend = dow >= 5
    is_night = hour >= 23 or hour < 5
    return hour, dow, is_weekend, is_night


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def ensure_bank_name_column(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS bank_name VARCHAR(30);
            """
        )
    conn.commit()
    logger.info("Ensured transactions.bank_name column exists")


def create_user_if_not_exists(conn, user_id: int = 1) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, name, email, monthly_income)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (user_id, "Demo User", "demo@smartspend.com", 85000),
        )
    conn.commit()
    logger.info("User %s ready", user_id)


def clear_bank_seeded_transactions(conn, user_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM transactions WHERE user_id = %s AND bank_name IS NOT NULL",
            (user_id,),
        )
    conn.commit()
    logger.info("Cleared prior bank CSV seed rows for user %s", user_id)


def bulk_insert_transactions(conn, transactions: list, user_id: int) -> None:
    values = []
    for t in transactions:
        hod, dow, is_we, is_ni = _txn_features(t["transaction_date"], t["transaction_time"])
        values.append(
            (
                user_id,
                t["transaction_date"],
                t["transaction_time"],
                t["amount"],
                t["type"],
                t["description"],
                t["merchant"],
                t["category"],
                t["transaction_mode"],
                t["location"],
                t["balance_after"],
                t["bank_name"],
                hod,
                dow,
                is_we,
                is_ni,
            )
        )
    sql = """
        INSERT INTO transactions (
            user_id, transaction_date, transaction_time, amount, type,
            description, merchant, category, payment_method, location, balance_after,
            bank_name,
            hour_of_day, day_of_week, is_weekend, is_night_txn,
            anomaly_flag, risk_score, risk_level, ml_processed
        ) VALUES %s
    """
    template = "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,FALSE,0,'LOW',FALSE)"
    with conn.cursor() as cur:
        execute_values(cur, sql, values, template=template, page_size=500)
    conn.commit()
    logger.info("Inserted %s transactions", len(transactions))


def seed_bank_csv(conn, csv_path: str, user_id: int = 1) -> int:
    logger.info("%s", "\n" + "=" * 60)
    logger.info("Processing: %s", csv_path)
    logger.info("%s", "=" * 60)
    try:
        result = parse_bank_csv(csv_path)
        logger.info(
            "Parsed %s - %s transactions, %s",
            result["bank_name"],
            result["total_count"],
            result["date_range"],
        )
        bulk_insert_transactions(conn, result["transactions"], user_id)
        logger.info("%s completed successfully\n", result["bank_name"])
        return int(result["total_count"])
    except Exception as exc:  # noqa: BLE001
        logger.error("Error processing %s: %s", csv_path, exc)
        return 0


def seed_all_banks(user_id: int = 1, clear_first: bool = True) -> None:
    csv_dir = Path(__file__).resolve().parent.parent / "data" / "sample_csvs"
    csv_files = [
        "hdfc_statement.csv",
        "sbi_statement.csv",
        "icici_statement.csv",
        "axis_statement.csv",
        "kotak_statement.csv",
    ]
    logger.info("\n%s", "=" * 60)
    logger.info("SMARTSPEND DATABASE SEEDING (bank CSV samples)")
    logger.info("%s\n", "=" * 60)
    conn = get_db_connection()
    logger.info("Connected to database %s@%s", DB_CONFIG["dbname"], DB_CONFIG["host"])
    try:
        ensure_bank_name_column(conn)
        create_user_if_not_exists(conn, user_id)
        if clear_first:
            clear_bank_seeded_transactions(conn, user_id)
        total_imported = 0
        for csv_file in csv_files:
            csv_path = csv_dir / csv_file
            if csv_path.exists():
                total_imported += seed_bank_csv(conn, str(csv_path), user_id)
            else:
                logger.warning("File not found: %s", csv_path)
        logger.info("\n%s", "=" * 60)
        logger.info("SEEDING COMPLETE - total transactions imported: %s", total_imported)
        logger.info("%s\n", "=" * 60)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    clear = os.getenv("SEED_BANK_CLEAR", "1").strip() not in ("0", "false", "False")
    uid = int(os.getenv("SEED_BANK_USER_ID", "1"))
    seed_all_banks(user_id=uid, clear_first=clear)
