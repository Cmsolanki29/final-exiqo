"""Resilient reads from `users` when legacy DBs omit optional columns."""

from __future__ import annotations

import psycopg2.errors
from psycopg2.extensions import connection as PgConnection


def fetch_user_display_name_and_income(conn: PgConnection, user_id: int) -> tuple[str, float]:
    """
    Returns (display_name, monthly_income).

    Prefers non-empty name, then email; tolerates missing `name` or `monthly_income` columns.
    """
    attempts: tuple[str, ...] = (
        """
        SELECT COALESCE(
                 NULLIF(TRIM(BOTH FROM COALESCE(name, '')), ''),
                 NULLIF(TRIM(BOTH FROM COALESCE(email, '')), ''),
                 'Member'
               ),
               COALESCE(monthly_income, 0)::float
        FROM users
        WHERE id = %s;
        """,
        """
        SELECT COALESCE(NULLIF(TRIM(BOTH FROM COALESCE(email, '')), ''), 'Member'),
               COALESCE(monthly_income, 0)::float
        FROM users
        WHERE id = %s;
        """,
        """
        SELECT COALESCE(NULLIF(TRIM(BOTH FROM COALESCE(email, '')), ''), 'Member'),
               0::float
        FROM users
        WHERE id = %s;
        """,
    )
    cur = conn.cursor()
    try:
        last_exc: Exception | None = None
        for sql in attempts:
            try:
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError("User not found")
                return str(row[0]), float(row[1] or 0)
            except psycopg2.errors.UndefinedColumn as exc:
                last_exc = exc
                conn.rollback()
                cur = conn.cursor()
                continue
        if last_exc:
            raise last_exc
        raise ValueError("User not found")
    finally:
        cur.close()
