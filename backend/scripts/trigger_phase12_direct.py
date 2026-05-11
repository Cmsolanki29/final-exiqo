"""
Directly call the orchestrator decide() function from Python to trigger
5 Tier-4 Phase 12 judge calls and log them to the DB.

Bypasses the HTTP API entirely — uses the same DB and models as the live server.
"""
import asyncio
import os
import sys
import logging

logging.basicConfig(level=logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

HIGH_RISK_TRANSACTIONS = [
    {"amount": 175000, "merchant": "International Wire Transfer", "location": "Unknown",       "category": "Wire",     "type": "DEBIT"},
    {"amount": 220000, "merchant": "Crypto Exchange Offshore",   "location": "Foreign",        "category": "Transfer", "type": "DEBIT"},
    {"amount": 98000,  "merchant": "Gift Card Bulk Purchase",    "location": "Unknown",        "category": "Other",    "type": "DEBIT"},
    {"amount": 150000, "merchant": "Unverified Merchant 9921",   "location": "International",  "category": "Wire",     "type": "DEBIT"},
    {"amount": 300000, "merchant": "Overseas Remittance Co",     "location": "Foreign",        "category": "Transfer", "type": "DEBIT"},
]

USER_ID = 5


async def main():
    from core.db import init_pool, get_pool
    from schemas.score import ScoreResult
    from services.phase_12_orchestrator.orchestrator import decide as orchestrator_decide

    print("[*] Initializing DB pool...")
    await init_pool()
    pool = get_pool()
    if pool is None:
        print("[FAIL] DB pool not available")
        return

    print("[*] Firing 5 Tier-4 transactions with score_override=95...")
    print("=" * 60)

    judge_count = 0
    for i, txn_data in enumerate(HIGH_RISK_TRANSACTIONS, 1):
        score_override = ScoreResult(
            risk_score=95,
            risk_level="CRITICAL",
            unsup_score=0.97,
            sup_score=0.97,
            explanation="score_override:95 (forced Tier-4 test)",
            explanation_detail=None,
            signals={"risk_score_override": True, "test_mode": True},
            detector_version="phase12_test_override_v1",
            latency_ms=0,
        )

        try:
            outcome = await orchestrator_decide(
                user_id=USER_ID,
                txn=txn_data,
                user={"id": USER_ID},
                features=None,
                score_override=score_override,
                triggered_by="phase12_demo_test",
            )
            d = outcome.to_dict()
            tier = d.get("tier", "?")
            score = d.get("baseline_score", "?")
            judge = d.get("judge") or {}
            judge_invoked = judge.get("invoked", False) if isinstance(judge, dict) else False
            if judge_invoked:
                judge_count += 1
            print(f"[{i}] {txn_data['merchant'][:40]:40s} | tier={tier} | score={score} | judge={judge_invoked}")
        except Exception as e:
            print(f"[{i}] ERROR: {e}")
            import traceback; traceback.print_exc()

    print("=" * 60)
    print(f"[*] Judge fired: {judge_count}/5")

    # Check the counts in DB
    async with pool.acquire() as conn:
        today_count = await conn.fetchval("""
            SELECT COUNT(*) FROM orchestration_decisions
            WHERE tier = 'tier_4_llm_agent'
            AND created_at >= CURRENT_DATE
        """)
        judge_calls = await conn.fetchval("""
            SELECT COUNT(*) FROM orchestration_decisions
            WHERE judge_invoked = true
            AND created_at >= CURRENT_DATE
        """)
        total_tier4 = await conn.fetchval("""
            SELECT COUNT(*) FROM orchestration_decisions
            WHERE tier = 'tier_4_llm_agent'
        """)
    print(f"\n[DB] Tier-4 decisions today: {today_count}")
    print(f"[DB] Judge calls today: {judge_calls}")
    print(f"[DB] Total Tier-4 all time: {total_tier4}")

    if judge_calls is None or judge_calls == 0:
        print("\n[WARN] judge_invoked column may not exist or is 0 — checking structure...")
        async with pool.acquire() as conn:
            cols = await conn.fetch("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='orchestration_decisions'
                ORDER BY ordinal_position
            """)
            print("Columns:", [c['column_name'] for c in cols])
            rows = await conn.fetch("""
                SELECT id, tier, risk_score, judge_invoked, created_at
                FROM orchestration_decisions
                ORDER BY created_at DESC LIMIT 5
            """)
            for r in rows:
                print(dict(r))

    await pool.close()


asyncio.run(main())
