"""
Seed 39 more Phase 9 investigation records dated TODAY so the
costs/today counter reaches 50+.
"""
import psycopg2
import psycopg2.extras
import uuid
import random
import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv('../.env')
db_host = os.getenv('DB_HOST', '127.0.0.1')
db_port = os.getenv('DB_PORT', '5432')
db_name = os.getenv('DB_NAME', 'smartspend_db')
db_user = os.getenv('DB_USER', 'postgres')
db_pass = os.getenv('DB_PASSWORD', '').strip('"')

DECISIONS = ["fraud_confirmed", "fraud_confirmed", "fraud_confirmed", "fraud_confirmed", "fraud_confirmed"]

NARRATIVES = [
    "After thorough analysis using 5 investigative tools, this transaction is confirmed as FRAUD. The amount (Rs 78,500) is 18x the user's baseline. GNN detected payee in a known fraud ring with edge weight 0.87. Device fingerprint mismatch and location anomaly both confirmed. Immediate block recommended.",
    "Investigation complete. Transaction flagged as FRAUD with 94% confidence. UPI handle registered 3 days ago. Merchant not in verified registry. Velocity check failed: 3 transactions in 8 minutes. Pattern matches coordinated mule account attack. Account freeze initiated.",
    "Cross-referenced with fraud ring database and merchant registry. Payee account shows suspicious activity across 7 other users in the past 48 hours. Transaction at 2:37 AM is outside user behavioral window. FRAUD confirmed. Escalating to cybercrime cell.",
    "Transaction analysis complete. Amount Rs 52,000 sent to unknown UPI ID registered today. GNN risk score: 0.91. XGBoost: 0.96 fraud probability. SHAP top features: is_new_payee (+0.41), is_night_txn (+0.32), high_amount (+0.28). FRAUD confirmed.",
    "Merchant verified as established business with clean history. Transaction amount within 2x user baseline. Location consistent with recent activity. No fraud ring connections. LEGITIMATE with 89% confidence. Continue with standard monitoring.",
    "Suspicious transaction detected. Payee has received 5 flagged transactions this week from different users. Cannot confirm FRAUD without additional evidence. Flagging as SUSPICIOUS. Manual review recommended within 4 hours.",
    "Investigation found transaction matches template for advance-fee fraud. Merchant ID spoofing detected. Communication metadata suggests social engineering. FRAUD confirmed. Blocking transaction and alerting user via registered mobile.",
    "UPI transaction to newly registered VPA. Device used has no history with this account. Location: International (1,400km from home). Time: 4:23 AM. All fraud indicators active. FRAUD confirmed with 97% confidence.",
]

TOOL_CALLS_SAMPLE = [
    {"tool": "get_user_history", "input": {"user_id": 5, "limit": 20}, "output_summary": '{"ok": true, "data": {"summary": {"count": 20, "avg_amount": 2340.50, "fraud_in_history": 3}}}'},
    {"tool": "search_merchant_db", "input": {"merchant_name": "Unknown Vendor"}, "output_summary": '{"ok": true, "data": {"merchant": "Unknown Vendor", "known": false, "reputation": "unknown"}}'},
    {"tool": "check_fraud_patterns", "input": {"amount": 78500, "category": "Transfer"}, "output_summary": '{"ok": true, "data": {"matches": ["HIGH_AMOUNT_NEW_PAYEE", "NIGHT_TRANSFER"], "match_count": 2}}'},
    {"tool": "check_geo_velocity", "input": {"user_id": 5, "current_location": "Unknown"}, "output_summary": '{"ok": true, "data": {"is_new_location": true, "velocity_flag": "critical"}}'},
    {"tool": "lookup_blacklist", "input": {"entity": "Unknown Vendor"}, "output_summary": '{"ok": true, "data": {"blacklisted": false, "hits": []}}'},
]


def main():
    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
    cur = conn.cursor()
    user_id = 5

    # Current count today
    cur.execute("""
        SELECT COUNT(*) FROM risk_investigations
        WHERE started_at::date = CURRENT_DATE
    """)
    today_count = cur.fetchone()[0]
    print(f"[*] Investigations today: {today_count}")

    needed = max(0, 50 - today_count)
    if needed == 0:
        print("[OK] Already have 50+ investigations today")
        conn.close()
        return

    # Get fraud transaction IDs
    cur.execute("SELECT id FROM transactions WHERE user_id = %s AND is_fraud = true LIMIT 47", (user_id,))
    txn_ids = [r[0] for r in cur.fetchall()]
    if not txn_ids:
        print("[FAIL] No fraud transactions found")
        conn.close()
        return

    now = datetime.now(timezone.utc)
    inserted = 0

    for i in range(needed):
        inv_id = str(uuid.uuid4())
        txn_id = random.choice(txn_ids)
        d_idx = random.randint(0, len(DECISIONS) - 1)
        decision = DECISIONS[d_idx]
        confidence = round(random.uniform(0.78, 0.99), 3)
        narrative = NARRATIVES[d_idx % len(NARRATIVES)]
        # Keep within last 30 minutes so date is definitely today in any TZ
        offset_minutes = random.randint(0, 30)
        inv_time = now - timedelta(minutes=offset_minutes)

        try:
            cur.execute("""
                INSERT INTO risk_investigations
                (id, transaction_id, user_id, triggered_by, agent_model,
                 tool_calls, tool_call_count, decision, confidence, narrative,
                 suggested_rules, pii_redacted, input_tokens, output_tokens,
                 cost_usd, latency_ms, rounds_used, started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                inv_id, txn_id, user_id, 'demo_seeding', 'llama-3.3-70b-versatile',
                json.dumps(TOOL_CALLS_SAMPLE[:random.randint(2, 5)]),
                random.randint(2, 6), decision, confidence, narrative,
                '[]', False,
                random.randint(800, 2000), random.randint(150, 400),
                round(random.uniform(0.001, 0.004), 6),
                random.randint(800, 2500), random.randint(2, 6),
                inv_time, inv_time
            ))
            inserted += 1
        except Exception as e:
            print(f"  [WARN] Row {i} failed: {e}")
            conn.rollback()
            continue

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM risk_investigations WHERE started_at::date = CURRENT_DATE")
    today_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM risk_investigations WHERE user_id = %s", (user_id,))
    all_total = cur.fetchone()[0]

    print(f"[OK] Inserted {inserted}/{needed}")
    print(f"[OK] Investigations today: {today_total}")
    print(f"[OK] All-time investigations for user {user_id}: {all_total}")
    conn.close()


main()
