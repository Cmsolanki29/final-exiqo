"""
Seed 50 Phase 9 LLM investigation records into phase_9_investigations table.
Run from backend directory: python scripts/seed_investigations.py
"""
import asyncio
import random
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

VERDICTS = ["FRAUD", "FRAUD", "FRAUD", "SUSPICIOUS", "LEGITIMATE"]

REASONING_TEMPLATES = [
    "Transaction shows unusually high amount for this merchant category. User's behavioral baseline indicates average spend 12x lower. Device fingerprint mismatch detected. GNN fraud ring connection probability: 0.87.",
    "Payee has been flagged in 3 previous fraud rings. Transaction time (3:47 AM) is outside user's normal activity window. IP geolocation inconsistent with registered address. Velocity score: CRITICAL.",
    "Velocity check failed: 4 transactions in 6 minutes to different payees. Pattern matches known account takeover behavior. SHAP top driver: is_new_payee (+0.41). Immediate block recommended.",
    "Merchant ID not found in verified registry. UPI handle registered 2 days ago. Amount matches common phishing transaction template (Rs 15,000-85,000 bracket). Anomaly score: 0.94.",
    "Cross-referencing with GNN fraud ring data: this payee is connected to 2 confirmed fraud nodes with edge weight 0.87. High risk of coordinated fraud ring. DNN shadow model agrees: 0.95.",
    "Transaction amount (Rs 78,000) is 18x user's 90-day average. Location anomaly detected: transaction origin is 1,200km from last activity. New device fingerprint. Risk: CRITICAL.",
    "Pattern analysis: this merchant has received 12 transactions from 8 different users in the last 48 hours, all flagged. Likely merchant compromise or social engineering attack.",
    "XGBoost confidence: 0.96 fraud. Top SHAP features: is_night_txn (+0.38), is_new_payee (+0.34), location_anomaly (+0.29), high_amount (+0.21). LLM confirms: FRAUD.",
]

EVIDENCE_TEMPLATES = [
    ["Amount 15x above 90-day user baseline", "Device fingerprint mismatch (new device)", "Transaction at 3:24 AM (outside normal window)"],
    ["Payee flagged in 3 fraud rings (GNN)", "UPI handle registered < 7 days ago", "IP geolocation 1,100km from home address"],
    ["4 transactions in 6 minutes to new payees", "Velocity rule CRITICAL triggered", "SHAP: is_new_payee driver = +0.41"],
    ["Merchant not in verified business registry", "UPI pattern matches known phishing template", "Anomaly score: 0.94 (threshold: 0.75)"],
    ["GNN fraud ring edge weight: 0.87", "2 connected confirmed-fraud nodes", "DNN shadow model: 0.95 fraud probability"],
    ["Amount Rs 78,000 = 18x user average", "Location anomaly: 1,200km from last activity", "New device + new location combination"],
    ["Merchant received 12 txns from 8 users in 48h", "All 12 transactions flagged as suspicious", "Coordinated attack pattern confirmed"],
    ["XGBoost: 0.96 fraud confidence", "SHAP top 4 drivers all point to fraud", "Consistent with account takeover pattern"],
]

RECOMMENDATIONS = [
    "Block transaction immediately. Freeze account pending user verification. File cybercrime report.",
    "Block transaction. Send OTP verification to registered mobile. Flag payee for monitoring.",
    "Block all pending transactions. Trigger account security review. Alert user via registered contact.",
    "Block transaction. Add merchant to watchlist. Recommend user report phishing attempt.",
    "Block transaction. Escalate to fraud ring investigation team. Preserve evidence for LEA.",
    "Block transaction. Require biometric re-authentication. Generate fraud report.",
    "Allow with enhanced monitoring. Flag for manual review within 24 hours.",
    "Transaction appears legitimate. Continue with standard fraud monitoring.",
]


async def seed():
    from core.db import init_pool, get_pool
    import asyncpg

    print("[*] Initializing DB pool...")
    await init_pool()
    pool = get_pool()
    if pool is None:
        print("[FAIL] DB pool not available")
        return

    user_id = 5  # abc@gmail.com

    async with pool.acquire() as conn:
        # Check table schema
        cols = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'phase_9_investigations'
            ORDER BY ordinal_position
        """)
        col_names = [c['column_name'] for c in cols]
        print(f"[*] phase_9_investigations columns: {col_names}")

        if not col_names:
            print("[FAIL] Table phase_9_investigations does not exist")
            await pool.close()
            return

        # Get fraud transaction IDs to link to
        txn_rows = await conn.fetch("""
            SELECT id, amount FROM transactions
            WHERE user_id = $1 AND is_fraud = true
            ORDER BY created_at DESC
        """, user_id)

        if not txn_rows:
            print("[FAIL] No fraud transactions found. Run seed_demo_data.py first.")
            await pool.close()
            return

        print(f"[*] Found {len(txn_rows)} fraud transactions to link investigations to")

        # Current count
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM phase_9_investigations WHERE user_id = $1", user_id
        )
        print(f"[*] Existing investigations for user {user_id}: {existing}")

        needed = max(0, 50 - existing)
        if needed == 0:
            print("[OK] Already have 50+ investigations. Nothing to do.")
            await pool.close()
            return

        base_date = datetime.now() - timedelta(days=45)
        inserted = 0

        for i in range(needed):
            txn = random.choice(txn_rows)
            verdict_idx = random.randint(0, len(VERDICTS) - 1)
            verdict = VERDICTS[verdict_idx]
            confidence = round(random.uniform(0.78, 0.99), 3)
            reasoning_idx = random.randint(0, len(REASONING_TEMPLATES) - 1)
            reasoning = REASONING_TEMPLATES[reasoning_idx]
            evidence = EVIDENCE_TEMPLATES[reasoning_idx % len(EVIDENCE_TEMPLATES)]
            recommendation = RECOMMENDATIONS[verdict_idx % len(RECOMMENDATIONS)]
            inv_date = base_date + timedelta(
                days=random.randint(0, 44),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )

            try:
                # Build INSERT based on available columns
                if 'evidence' in col_names and 'recommendation' in col_names and 'status' in col_names:
                    await conn.execute("""
                        INSERT INTO phase_9_investigations
                        (user_id, transaction_id, verdict, confidence, reasoning,
                         evidence, recommendation, status, created_at, completed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, 'completed', $8, $8)
                        ON CONFLICT DO NOTHING
                    """, user_id, txn['id'], verdict, confidence, reasoning,
                        str(evidence), recommendation, inv_date)
                elif 'evidence' in col_names and 'status' in col_names:
                    await conn.execute("""
                        INSERT INTO phase_9_investigations
                        (user_id, transaction_id, verdict, confidence, reasoning,
                         evidence, status, created_at, completed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, 'completed', $7, $7)
                        ON CONFLICT DO NOTHING
                    """, user_id, txn['id'], verdict, confidence, reasoning,
                        str(evidence), inv_date)
                elif 'status' in col_names:
                    await conn.execute("""
                        INSERT INTO phase_9_investigations
                        (user_id, transaction_id, verdict, confidence, reasoning,
                         status, created_at, completed_at)
                        VALUES ($1, $2, $3, $4, $5, 'completed', $6, $6)
                        ON CONFLICT DO NOTHING
                    """, user_id, txn['id'], verdict, confidence, reasoning, inv_date)
                else:
                    await conn.execute("""
                        INSERT INTO phase_9_investigations
                        (user_id, transaction_id, verdict, confidence, reasoning,
                         created_at, completed_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $6)
                        ON CONFLICT DO NOTHING
                    """, user_id, txn['id'], verdict, confidence, reasoning, inv_date)
                inserted += 1
            except Exception as e:
                print(f"  [WARN] Row {i} failed: {e}")

        total = await conn.fetchval(
            "SELECT COUNT(*) FROM phase_9_investigations WHERE user_id = $1", user_id
        )
        print(f"[OK] Inserted {inserted}/{needed} investigation records")
        print(f"[OK] Total investigations for user {user_id}: {total}")

    await pool.close()


asyncio.run(seed())
