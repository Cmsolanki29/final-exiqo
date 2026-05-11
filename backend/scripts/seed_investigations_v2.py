"""
Seed Phase 9 investigation records using psycopg2 (sync, no hanging pool).
Run: python scripts/seed_investigations_v2.py
"""
import psycopg2
import random
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv('../.env')
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'smartspend_db')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASSWORD', '').strip('"')

VERDICTS = ["FRAUD", "FRAUD", "FRAUD", "SUSPICIOUS", "LEGITIMATE"]

REASONING = [
    "Transaction shows unusually high amount for this merchant category. User's behavioral baseline indicates average spend 12x lower. Device fingerprint mismatch detected. GNN fraud ring connection probability: 0.87.",
    "Payee has been flagged in 3 previous fraud rings. Transaction time 3:47 AM is outside user's normal activity window. IP geolocation inconsistent with registered address. Velocity score: CRITICAL.",
    "Velocity check failed: 4 transactions in 6 minutes to different payees. Pattern matches known account takeover behavior. SHAP top driver: is_new_payee +0.41. Immediate block recommended.",
    "Merchant ID not found in verified registry. UPI handle registered 2 days ago. Amount matches common phishing transaction template. Anomaly score: 0.94.",
    "Cross-referencing with GNN fraud ring data: payee connected to 2 confirmed fraud nodes with edge weight 0.87. High risk of coordinated fraud ring. DNN shadow model agrees: 0.95.",
    "Transaction amount Rs 78,000 is 18x user 90-day average. Location anomaly detected: origin is 1,200km from last activity. New device fingerprint. Risk: CRITICAL.",
    "Pattern analysis: this merchant received 12 transactions from 8 different users in 48 hours, all flagged. Likely merchant compromise or social engineering attack vector.",
    "XGBoost confidence 0.96 fraud. Top SHAP features: is_night_txn +0.38, is_new_payee +0.34, location_anomaly +0.29, high_amount +0.21. LLM investigation confirms: FRAUD.",
]

EVIDENCE = [
    "Amount 15x above 90-day user baseline | Device fingerprint mismatch | Transaction at 3:24 AM",
    "Payee flagged in 3 fraud rings (GNN) | UPI handle registered 7 days ago | IP 1,100km from home",
    "4 transactions in 6 minutes to new payees | Velocity rule CRITICAL | SHAP: is_new_payee +0.41",
    "Merchant not in verified registry | UPI matches phishing template | Anomaly score: 0.94",
    "GNN fraud ring edge weight: 0.87 | 2 connected confirmed-fraud nodes | DNN: 0.95 fraud prob",
    "Amount Rs 78,000 = 18x user average | Location anomaly: 1,200km from last | New device + location",
    "Merchant: 12 txns from 8 users in 48h | All 12 flagged suspicious | Coordinated attack confirmed",
    "XGBoost: 0.96 fraud | SHAP top 4 drivers all fraud | Consistent with account takeover",
]

RECOMMENDATIONS = [
    "Block transaction immediately. Freeze account pending user verification. File cybercrime report at cybercrime.gov.in.",
    "Block transaction. Send OTP verification to registered mobile. Flag payee for 30-day monitoring.",
    "Block all pending transactions. Trigger account security review. Alert user via registered contact.",
    "Block transaction. Add merchant to watchlist. Recommend user report phishing attempt to 1930.",
    "Block transaction. Escalate to fraud ring investigation team. Preserve evidence for law enforcement.",
    "Block transaction. Require biometric re-authentication before next transaction. Generate fraud report.",
    "Allow with enhanced monitoring. Flag for manual review within 24 hours. Reduce transaction limits.",
    "Transaction appears legitimate based on behavioral analysis. Continue with standard fraud monitoring.",
]


def main():
    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
    cur = conn.cursor()
    user_id = 5

    # Check table columns
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'phase_9_investigations'
        ORDER BY ordinal_position
    """)
    col_names = [r[0] for r in cur.fetchall()]
    print(f"[*] Columns: {col_names}")

    if not col_names:
        print("[FAIL] Table does not exist")
        conn.close()
        return

    # Get fraud transactions to link to
    cur.execute("""
        SELECT id, amount FROM transactions
        WHERE user_id = %s AND is_fraud = true
        ORDER BY created_at DESC
    """, (user_id,))
    txn_rows = cur.fetchall()
    print(f"[*] Fraud transactions available: {len(txn_rows)}")

    # Current count
    cur.execute("SELECT COUNT(*) FROM phase_9_investigations WHERE user_id = %s", (user_id,))
    existing = cur.fetchone()[0]
    print(f"[*] Existing investigations: {existing}")

    needed = max(0, 50 - existing)
    if needed == 0:
        print("[OK] Already have 50+ investigations")
        conn.close()
        return

    base_date = datetime.now() - timedelta(days=45)
    inserted = 0

    for i in range(needed):
        txn = random.choice(txn_rows)
        v_idx = random.randint(0, len(VERDICTS) - 1)
        verdict = VERDICTS[v_idx]
        confidence = round(random.uniform(0.78, 0.99), 3)
        r_idx = random.randint(0, len(REASONING) - 1)
        inv_date = base_date + timedelta(
            days=random.randint(0, 44),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )

        try:
            if 'evidence' in col_names and 'recommendation' in col_names and 'status' in col_names:
                cur.execute("""
                    INSERT INTO phase_9_investigations
                    (user_id, transaction_id, verdict, confidence, reasoning,
                     evidence, recommendation, status, created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', %s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_id, txn[0], verdict, confidence, REASONING[r_idx],
                      EVIDENCE[r_idx % len(EVIDENCE)], RECOMMENDATIONS[v_idx % len(RECOMMENDATIONS)],
                      inv_date, inv_date))
            elif 'status' in col_names:
                cur.execute("""
                    INSERT INTO phase_9_investigations
                    (user_id, transaction_id, verdict, confidence, reasoning, status, created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, 'completed', %s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_id, txn[0], verdict, confidence, REASONING[r_idx], inv_date, inv_date))
            else:
                cur.execute("""
                    INSERT INTO phase_9_investigations
                    (user_id, transaction_id, verdict, confidence, reasoning, created_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_id, txn[0], verdict, confidence, REASONING[r_idx], inv_date, inv_date))
            inserted += 1
        except Exception as e:
            print(f"  [WARN] Row {i} failed: {e}")
            conn.rollback()
            continue

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM phase_9_investigations WHERE user_id = %s", (user_id,))
    total = cur.fetchone()[0]
    print(f"[OK] Inserted {inserted}/{needed}")
    print(f"[OK] Total investigations for user {user_id}: {total}")

    conn.close()


main()
