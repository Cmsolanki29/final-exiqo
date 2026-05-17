"""
Verify document upload data chain and integrity.

Usage:
  cd backend
  python -m scripts.verify_upload_integrity
  python -m scripts.verify_upload_integrity --user-id 1
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND.parent / ".env")
load_dotenv(_BACKEND / ".env")


def _connect():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "smartspend_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument(
        "--fix-visible",
        action="store_true",
        help="Set is_visible_on_dashboard=true for upload sources that have transactions",
    )
    args = parser.parse_args()

    conn = _connect()
    issues: list[str] = []

    if args.fix_visible:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE connected_sources cs
                SET is_visible_on_dashboard = TRUE
                WHERE COALESCE(cs.is_visible_on_dashboard, false) = false
                  AND cs.added_via IN ('settings_upload', 'onboarding_upload')
                  AND EXISTS (
                    SELECT 1 FROM transactions t WHERE t.connected_source_id = cs.id
                  )
                """
            )
            fixed = cur.rowcount
        conn.commit()
        print(f"Fixed visibility on {fixed} upload-connected source(s).")

    with conn.cursor() as cur:
        # Issue 1: orphaned transactions
        _print_section("Issue 1: Orphaned transactions")
        cur.execute(
            """
            SELECT COUNT(*) FROM transactions t
            WHERE t.connected_source_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM connected_sources cs WHERE cs.id = t.connected_source_id
              )
            """
        )
        orphan_src = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM transactions WHERE connected_source_id IS NULL"
        )
        null_src = cur.fetchone()[0]
        print(f"  Invalid connected_source_id: {orphan_src}")
        print(f"  NULL connected_source_id: {null_src}")
        if orphan_src:
            issues.append(f"{orphan_src} transactions with invalid connected_source_id")

        # Issue 2: invisible sources with transactions
        _print_section("Issue 2: Hidden sources with transactions")
        cur.execute(
            """
            SELECT cs.id, cs.institution_name, cs.is_visible_on_dashboard, COUNT(t.id)
            FROM connected_sources cs
            JOIN transactions t ON t.connected_source_id = cs.id
            WHERE COALESCE(cs.is_visible_on_dashboard, false) = false
            GROUP BY cs.id, cs.institution_name, cs.is_visible_on_dashboard
            """
        )
        hidden = cur.fetchall()
        for row in hidden:
            print(f"  source {row[0]} {row[1]}: hidden, {row[3]} txns")
        if hidden:
            issues.append(f"{len(hidden)} hidden source(s) still have transactions")

        # Issue 3: duplicate sources
        _print_section("Issue 3: Duplicate institution+type per user")
        cur.execute(
            """
            SELECT user_id, institution_name, source_type, COUNT(*)
            FROM connected_sources
            GROUP BY user_id, institution_name, source_type
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT 20
            """
        )
        dupes = cur.fetchall()
        for row in dupes:
            print(f"  user {row[0]} {row[1]} ({row[2]}): {row[3]} sources")
        if dupes:
            issues.append(f"{len(dupes)} duplicate source groups (may be OK if constraint merges)")

        # Issue 4: uploads without extraction_results
        _print_section("Issue 4: Uploads missing extraction_results (old pipeline)")
        where_parts = ["er.id IS NULL"]
        params: list = []
        if args.user_id:
            where_parts.insert(0, "ud.user_id = %s")
            params.append(args.user_id)
        where_sql = "WHERE " + " AND ".join(where_parts)
        cur.execute(
            f"""
            SELECT ud.id, ud.file_name, ud.extraction_status, ud.uploaded_at
            FROM uploaded_documents ud
            LEFT JOIN extraction_results er ON er.uploaded_document_id = ud.id
            {where_sql}
            ORDER BY ud.uploaded_at DESC NULLS LAST
            LIMIT 20
            """,
            tuple(params),
        )
        missing_er = cur.fetchall()
        for row in missing_er:
            print(f"  doc {row[0]} {row[1]} status={row[2]} at {row[3]}")
        if missing_er:
            issues.append(f"{len(missing_er)} uploads without extraction_results")

        # Issue 5: data_origin breakdown
        _print_section("Issue 5: data_origin distribution")
        if args.user_id:
            cur.execute(
                "SELECT COALESCE(data_origin, 'null'), COUNT(*) FROM transactions WHERE user_id = %s GROUP BY 1 ORDER BY 2 DESC",
                (args.user_id,),
            )
        else:
            cur.execute(
                "SELECT COALESCE(data_origin, 'null'), COUNT(*) FROM transactions GROUP BY 1 ORDER BY 2 DESC LIMIT 15"
            )
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")

        # Chain verification for latest upload(s)
        _print_section("Chain 1–5: Latest upload per user")
        if args.user_id:
            user_ids = [args.user_id]
        else:
            cur.execute(
                "SELECT DISTINCT user_id FROM uploaded_documents ORDER BY user_id DESC LIMIT 5"
            )
            user_ids = [r[0] for r in cur.fetchall()]

        for uid in user_ids:
            print(f"\n--- user_id={uid} ---")
            cur.execute(
                """
                SELECT cs.id, cs.institution_name, cs.source_type, cs.is_visible_on_dashboard, cs.added_via
                FROM connected_sources cs
                WHERE cs.user_id = %s
                ORDER BY cs.id DESC LIMIT 3
                """,
                (uid,),
            )
            print("  connected_sources (latest 3):")
            for row in cur.fetchall():
                print(f"    {row}")

            cur.execute(
                """
                SELECT ud.id, ud.connected_source_id, ud.file_name, ud.file_size_kb,
                       ud.rows_extracted, ud.rows_imported, ud.extraction_status
                FROM uploaded_documents ud
                WHERE ud.user_id = %s
                ORDER BY ud.uploaded_at DESC NULLS LAST, ud.id DESC
                LIMIT 1
                """,
                (uid,),
            )
            doc = cur.fetchone()
            if not doc:
                print("  No uploads for user")
                continue
            print(f"  uploaded_documents: doc_id={doc[0]} source={doc[1]} file={doc[2]} status={doc[6]} extracted={doc[4]} imported={doc[5]}")

            cur.execute(
                """
                SELECT id, attempt_number, extraction_method, quality_score, status,
                       LENGTH(COALESCE(raw_extracted_text, '')) AS text_len,
                       transactions_extracted, transactions_stored
                FROM extraction_results
                WHERE uploaded_document_id = %s
                ORDER BY attempt_number
                """,
                (doc[0],),
            )
            attempts = cur.fetchall()
            print(f"  extraction_results ({len(attempts)} attempts):")
            for row in attempts:
                print(f"    attempt {row[1]}: method={row[2]} score={row[3]} status={row[4]} text_len={row[5]} txns={row[6]}/{row[7]}")
            if not attempts:
                issues.append(f"user {uid} latest doc {doc[0]} has no extraction_results")

            if doc[1]:
                cur.execute(
                    """
                    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date),
                           SUM(CASE WHEN type='DEBIT' THEN amount ELSE 0 END)
                    FROM transactions
                    WHERE user_id = %s AND connected_source_id = %s
                    """,
                    (uid, doc[1]),
                )
                txn = cur.fetchone()
                print(f"  transactions for source {doc[1]}: count={txn[0]} range={txn[1]}..{txn[2]} debit_sum={txn[3]}")

    conn.close()

    _print_section("Summary")
    if issues:
        print("ISSUES FOUND:")
        for i in issues:
            print(f"  - {i}")
        return 1
    print("All integrity checks passed (or only informational warnings above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
