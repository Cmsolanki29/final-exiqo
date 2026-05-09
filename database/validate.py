import importlib.util
import sys
from pathlib import Path


def _load_db_module():
    db_path = Path(__file__).resolve().parent / "db.py"
    spec = importlib.util.spec_from_file_location("_smartspend_db", db_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load database helper from {db_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


_db = _load_db_module()
get_db_connection = _db.get_db_connection


def print_table_counts(cur) -> None:
    print("\n📦 Table row counts")
    print("-" * 50)
    for table_name in ["users", "transactions", "alerts", "monthly_summary", "spending_patterns"]:
        cur.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cur.fetchone()[0]
        print(f"{table_name:<20} {count:>8}")


def print_sample_transactions(cur) -> None:
    print("\n🧾 Sample transactions (5 rows)")
    print("-" * 110)
    cur.execute(
        """
        SELECT
            u.name,
            t.transaction_date,
            t.transaction_time,
            t.type,
            t.amount,
            t.category,
            t.subcategory,
            t.merchant,
            t.payment_method,
            t.location,
            t.anomaly_flag,
            t.risk_level,
            t.anomaly_reason
        FROM transactions t
        JOIN users u ON u.id = t.user_id
        ORDER BY t.transaction_date DESC, t.transaction_time DESC
        LIMIT 5;
        """
    )
    rows = cur.fetchall()
    for row in rows:
        anomaly_text = row[12] if row[12] else "-"
        print(
            f"{row[0]:<14} | {row[1]} {str(row[2])[:8]} | {row[3]:<6} | ₹{float(row[4]):>10,.2f} | "
            f"{row[5]:<18} | {row[7]:<20} | {row[8]:<11} | {row[10]} | {row[11]:<8} | {anomaly_text}"
        )


def print_anomaly_distribution(cur) -> None:
    print("\n🚨 Anomaly distribution")
    print("-" * 50)
    cur.execute(
        """
        SELECT
            COALESCE(NULLIF(split_part(anomaly_reason, ':', 1), ''), 'UNSPECIFIED') AS anomaly_type,
            COUNT(*) AS cnt
        FROM transactions
        WHERE anomaly_flag = TRUE
        GROUP BY anomaly_type
        ORDER BY cnt DESC, anomaly_type;
        """
    )
    rows = cur.fetchall()
    for row in rows:
        print(f"{row[0]:<20} {row[1]:>6}")


def print_monthly_summary(cur) -> None:
    print("\n📅 Monthly summary snapshot")
    print("-" * 80)
    cur.execute(
        """
        SELECT
            u.name,
            ms.year,
            ms.month,
            ms.total_income,
            ms.total_expense,
            ms.total_saved,
            ms.savings_rate,
            ms.health_score,
            ms.anomaly_count,
            ms.high_risk_count,
            ms.top_category
        FROM monthly_summary ms
        JOIN users u ON u.id = ms.user_id
        ORDER BY u.name, ms.year, ms.month;
        """
    )
    rows = cur.fetchall()
    current_user = None
    for row in rows:
        if current_user != row[0]:
            current_user = row[0]
            print(f"\n{current_user}")
        print(
            f"  {row[1]}-{row[2]:02d} | Income ₹{float(row[3]):>10,.2f} | Expense ₹{float(row[4]):>10,.2f} | "
            f"Saved ₹{float(row[5]):>9,.2f} | Savings {float(row[6]):>6.2f}% | "
            f"Health {row[7]:>3} | Anom {row[8]:>2} | HighRisk {row[9]:>2} | Top {row[10]}"
        )


def print_user1_category_spend(cur) -> None:
    print("\n🍛 User 1 spending by category")
    print("-" * 50)
    cur.execute(
        """
        SELECT
            t.category,
            COUNT(*) AS txn_count,
            SUM(t.amount) AS total_spent,
            ROUND(AVG(t.amount), 2) AS avg_spent
        FROM transactions t
        WHERE t.user_id = 1
          AND t.type = 'DEBIT'
        GROUP BY t.category
        ORDER BY total_spent DESC;
        """
    )
    for row in cur.fetchall():
        print(
            f"{row[0]:<20} txns={row[1]:>4} | total=₹{float(row[2]):>11,.2f} | avg=₹{float(row[3]):>8,.2f}"
        )


def confirm_indexes(cur) -> None:
    expected_indexes = [
        "idx_txn_user_date",
        "idx_txn_category",
        "idx_txn_anomaly",
        "idx_txn_ml_processed",
        "idx_txn_date",
        "idx_alerts_user_unread",
    ]
    cur.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = ANY(%s)
        ORDER BY indexname;
        """,
        (expected_indexes,),
    )
    found = {row[0] for row in cur.fetchall()}
    print("\n🧩 Index verification")
    print("-" * 50)
    for index_name in expected_indexes:
        status = "✅" if index_name in found else "❌"
        print(f"{status} {index_name}")
    missing = [idx for idx in expected_indexes if idx not in found]
    if missing:
        print(f"⚠️ Missing indexes: {', '.join(missing)}")


def main() -> None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            print("🔎 Validating SmartSpend Phase 1 database setup...")
            print_table_counts(cur)
            print_sample_transactions(cur)
            print_anomaly_distribution(cur)
            print_monthly_summary(cur)
            print_user1_category_spend(cur)
            confirm_indexes(cur)
            print("\n✅ Phase 1 Complete — Database ready for ML pipeline")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
