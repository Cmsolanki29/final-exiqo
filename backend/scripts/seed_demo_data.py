"""
Seeds realistic fraud detection demo data for hackathon presentation.
Run: python scripts/seed_demo_data.py

Target user: abc@gmail.com (user_id = 5)
Targets:
  - 500 legitimate transactions
  - 47 confirmed fraud transactions  
  - 47 fraud_alerts (with severity)
  - Money saved: ~Rs 12-18 lakh
  - Threats blocked: 47
  - Safety score: ~94%
"""
import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")
import psycopg2

LEGIT_MERCHANTS = [
    "Amazon India", "Flipkart", "Swiggy", "Zomato", "BigBasket",
    "Myntra", "Nykaa", "BookMyShow", "Ola", "Uber", "PhonePe",
    "IRCTC", "MakeMyTrip", "Paytm Mall", "Jio Recharge",
    "Grofers", "Zepto", "Blinkit", "Meesho", "Dunzo",
]

FRAUD_MERCHANTS = [
    "Unknown Vendor 7821", "Offshore Transfer XYZ", "Crypto Exchange 99",
    "International Wire LLC", "Gift Card Depot", "Temp Merchant 4521",
    "Unverified Payee 001", "Foreign Remittance 88", "Unknown Vendor 9921",
    "Overseas Remittance Co", "Crypto Exchange Offshore", "Gift Card Bulk Purchase",
]

CATEGORIES = ["Shopping", "Food", "Transport", "Entertainment", "Recharge", "Health"]
LOCATIONS = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune", "Kolkata"]


def main():
    DB = dict(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "smartspend_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    # Discover user_id for abc@gmail.com
    cur.execute("SELECT id FROM users WHERE email='abc@gmail.com' LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("ERROR: abc@gmail.com not found. Cannot seed.")
        return
    user_id = row[0]
    print(f"Seeding for user_id={user_id} (abc@gmail.com)")

    # Check existing transaction count
    cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=%s", (user_id,))
    existing = cur.fetchone()[0]
    print(f"Existing transactions for this user: {existing}")

    # Check transactions table columns
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='transactions'"
    )
    cols = {r[0] for r in cur.fetchall()}
    print(f"Transactions columns: {sorted(cols)}")

    # Check fraud_alerts columns
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='fraud_alerts'"
    )
    alert_cols = {r[0] for r in cur.fetchall()}
    print(f"fraud_alerts columns: {sorted(alert_cols)}")

    # Add severity column to fraud_alerts if missing
    if "severity" not in alert_cols:
        print("Adding severity column to fraud_alerts ...")
        cur.execute(
            "ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS severity VARCHAR(10) DEFAULT 'MEDIUM'"
        )
        conn.commit()
        print("severity column added.")

    base_date = datetime.now() - timedelta(days=90)
    random.seed(42)

    def make_txn(txn_dt, amount, merchant, category, location, is_fraud, anomaly_score):
        """Build a transaction row dict matching the actual schema."""
        h = txn_dt.hour
        d = txn_dt.weekday()
        row = {
            "user_id": user_id,
            "amount": amount,
            "merchant": merchant,
        }
        if "transaction_date" in cols:
            row["transaction_date"] = txn_dt.date()
        if "transaction_time" in cols:
            row["transaction_time"] = txn_dt.time()
        if "created_at" in cols:
            row["created_at"] = txn_dt
        if "category" in cols:
            row["category"] = category
        if "location" in cols:
            row["location"] = location
        if "is_fraud" in cols:
            row["is_fraud"] = is_fraud
        if "is_night_txn" in cols:
            row["is_night_txn"] = h >= 22 or h < 6
        if "is_weekend" in cols:
            row["is_weekend"] = d >= 5
        if "hour_of_day" in cols:
            row["hour_of_day"] = h
        if "day_of_week" in cols:
            row["day_of_week"] = d
        if "anomaly_flag" in cols:
            row["anomaly_flag"] = is_fraud
        if "risk_score" in cols:
            row["risk_score"] = int(anomaly_score * 100)
        if "risk_level" in cols:
            row["risk_level"] = "CRITICAL" if is_fraud else "LOW"
        if "ml_processed" in cols:
            row["ml_processed"] = True
        if "type" in cols:
            row["type"] = "DEBIT"
        return row

    # ── INSERT 500 legit transactions ──────────────────────────────
    print("Inserting 500 legitimate transactions ...")
    legit_inserted = 0
    for i in range(500):
        dt = base_date + timedelta(
            days=random.randint(0, 89), hours=random.randint(8, 22), minutes=random.randint(0, 59)
        )
        amount = round(random.uniform(100, 8000), 2)
        row = make_txn(dt, amount, random.choice(LEGIT_MERCHANTS),
                       random.choice(CATEGORIES), random.choice(LOCATIONS),
                       False, round(random.uniform(0.01, 0.25), 3))
        keys = list(row.keys())
        try:
            cur.execute(
                f"INSERT INTO transactions ({', '.join(keys)}) VALUES ({', '.join(['%s']*len(keys))})",
                [row[k] for k in keys],
            )
            legit_inserted += 1
        except Exception as e:
            conn.rollback()
            print(f"  legit txn error: {e}")
            break

    conn.commit()
    print(f"  Inserted {legit_inserted} legit transactions.")

    # ── INSERT 47 fraud transactions ───────────────────────────────
    print("Inserting 47 fraud transactions ...")
    fraud_amounts = []
    fraud_txn_ids = []
    for i in range(47):
        dt = base_date + timedelta(
            days=random.randint(0, 89), hours=random.randint(0, 23), minutes=random.randint(0, 59)
        )
        amount = round(random.uniform(8000, 85000), 2)
        fraud_amounts.append(amount)
        row = make_txn(dt, amount, random.choice(FRAUD_MERCHANTS),
                       "Transfer", "Unknown", True, round(random.uniform(0.75, 0.99), 3))
        keys = list(row.keys())
        try:
            cur.execute(
                f"INSERT INTO transactions ({', '.join(keys)}) VALUES ({', '.join(['%s']*len(keys))}) RETURNING id",
                [row[k] for k in keys],
            )
            txn_id = cur.fetchone()[0]
            fraud_txn_ids.append((txn_id, amount))
        except Exception as e:
            conn.rollback()
            print(f"  fraud txn error: {e}")
            break

    conn.commit()
    print(f"  Inserted {len(fraud_txn_ids)} fraud transactions.")

    # ── INSERT 47 fraud_alerts ─────────────────────────────────────
    print("Inserting 47 fraud_alerts ...")
    alerts_inserted = 0
    for txn_id, amount in fraud_txn_ids:
        # Determine severity by amount
        if amount > 50000:
            severity = "CRITICAL"
        elif amount > 20000:
            severity = "HIGH"
        elif amount > 5000:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        risk_score = int(min(99, 70 + (amount / 85000) * 29))
        money_saved = round(amount, 2)

        alert_vals = {
            "user_id": user_id,
            "transaction_id": txn_id,
            "risk_score": risk_score,
        }
        if "pattern_matched" in alert_cols:
            alert_vals["pattern_matched"] = "FRAUD_DETECTED"
        if "amount_at_risk" in alert_cols:
            alert_vals["amount_at_risk"] = amount
        if "warning_message" in alert_cols:
            alert_vals["warning_message"] = f"Suspicious transaction of Rs {amount:,.0f} blocked"
        if "hinglish_explanation" in alert_cols:
            alert_vals["hinglish_explanation"] = f"Yeh transaction suspicious lag rahi hai - Rs {amount:,.0f}"
        if "user_action" in alert_cols:
            alert_vals["user_action"] = random.choice(["RESOLVED", "PENDING"])
        if "money_saved" in alert_cols:
            alert_vals["money_saved"] = money_saved
        if "severity" in alert_cols:
            alert_vals["severity"] = severity
        if "created_at" in alert_cols:
            alert_vals["created_at"] = datetime.now() - timedelta(days=random.randint(0, 89))

        keys = list(alert_vals.keys())
        placeholders = ", ".join(["%s"] * len(keys))
        col_list = ", ".join(keys)
        try:
            cur.execute(
                f"INSERT INTO fraud_alerts ({col_list}) VALUES ({placeholders})",
                [alert_vals[k] for k in keys],
            )
            alerts_inserted += 1
        except Exception as e:
            conn.rollback()
            print(f"  alert insert error: {e} for txn_id={txn_id}")

    conn.commit()
    print(f"  Inserted {alerts_inserted} fraud alerts.")

    # ── UPDATE severity for existing alerts based on amount ────────
    print("Updating severity for existing fraud_alerts ...")
    cur.execute("""
        UPDATE fraud_alerts fa
        SET severity = CASE
            WHEN fa.amount_at_risk > 50000 THEN 'CRITICAL'
            WHEN fa.amount_at_risk > 20000 THEN 'HIGH'
            WHEN fa.amount_at_risk > 5000  THEN 'MEDIUM'
            ELSE 'LOW'
        END
        WHERE fa.severity IS NULL OR fa.severity = 'MEDIUM'
          AND fa.amount_at_risk IS NOT NULL
    """)
    conn.commit()

    # ── Final stats ────────────────────────────────────────────────
    total_fraud_amount = sum(fraud_amounts)
    cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=%s AND is_fraud=true", (user_id,))
    threat_count = cur.fetchone()[0]

    cur.execute("SELECT SUM(money_saved) FROM fraud_alerts WHERE user_id=%s", (user_id,))
    saved_row = cur.fetchone()
    money_saved_db = float(saved_row[0] or 0)

    cur.execute("SELECT COUNT(*) FROM fraud_alerts WHERE user_id=%s", (user_id,))
    alert_count = cur.fetchone()[0]

    print("\n" + "=" * 50)
    print("SEED COMPLETE")
    print("=" * 50)
    print(f"Threats blocked (fraud_confirmed=true): {threat_count}")
    print(f"Money seeded in fraud amounts:          Rs {total_fraud_amount:,.0f}")
    print(f"Money saved in fraud_alerts (DB):       Rs {money_saved_db:,.0f}")
    print(f"Total fraud_alerts for this user:       {alert_count}")
    print(f"Safety score estimate: ~{(threat_count / (threat_count + 3) * 100):.1f}%")
    print("=" * 50)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
