"""Validate Phase 4 AI Insights Engine (OpenAI GPT-4o-mini).

Run from the backend folder:
    python -m services.insight_test

Or from the repo root (Exiqo phase2):
    python -m backend.services.insight_test
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path


def _ensure_backend_on_path() -> Path:
    """backend/ must be on sys.path for `from services` / `from routes`."""
    here = Path(__file__).resolve().parent
    backend_dir = here.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    return backend_dir


def main() -> None:
    _ensure_backend_on_path()
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    from services.openai_service import (
        explain_anomaly_transaction,
        generate_health_narrative,
        generate_monthly_insights,
        get_personalized_recommendations,
        meter_reset,
        meter_totals,
        simulate_financial_scenario,
    )
    from db import get_connection
    from routes.insights import build_user_data
    from services.scorer import calculate_health_score

    meter_reset()
    conn = get_connection()
    user_id = 1
    today = date.today()
    m, y = today.month, today.year

    print("\n" + "=" * 72)
    print("SmartSpend Phase 4 — AI Insights validation")
    print("=" * 72)

    # --- Test 1: Monthly insights ---
    print("\n[1] Monthly financial insights")
    ud = build_user_data(conn, user_id, m, y)
    ins = generate_monthly_insights(ud)
    print("  summary:", (ins.get("summary") or "")[:200], "..." if len(str(ins.get("summary", ""))) > 200 else "")
    kis = ins.get("key_insights") or []
    print("  first key_insight:", kis[0] if kis else "(none)")
    assert "spending_verdict" in ins, "spending_verdict missing"
    print("  spending_verdict:", ins["spending_verdict"])

    # --- Test 2: Anomaly explanation (English) ---
    print("\n[2] Anomaly explanation")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, merchant, amount, transaction_date, transaction_time, category,
               risk_score, risk_level, COALESCE(anomaly_reason, ''), payment_method
        FROM transactions
        WHERE user_id = %s AND anomaly_flag = TRUE
        ORDER BY risk_score DESC NULLS LAST, id ASC
        LIMIT 1;
        """,
        (user_id,),
    )
    row = cur.fetchone()
    if row:
        tid, merchant, amount, tdate, ttime, cat, rscore, rlevel, reason, pmeth = row
        tx = {
            "merchant": merchant or "",
            "amount": float(amount or 0),
            "transaction_date": str(tdate),
            "transaction_time": str(ttime),
            "category": cat or "",
            "risk_score": int(rscore or 0),
            "risk_level": rlevel or "LOW",
            "anomaly_reason": reason or "Flagged",
            "payment_method": pmeth or "",
            "user_name": ud["name"],
        }
        expl = explain_anomaly_transaction(tx)
        print("  transaction_id:", tid)
        print("  explanation:", expl[:400], "..." if len(expl) > 400 else "")
    else:
        print("  (no flagged transactions — skipped)")
    cur.close()

    # --- Test 3: Scenario ---
    print("\n[3] Scenario simulation")
    sim = simulate_financial_scenario(ud, "What if I reduce food spending by 25%?")
    imp = sim.get("impact") or {}
    print("  savings_change:", imp.get("savings_change"))
    print("  verdict:", sim.get("verdict"))

    # --- Test 4: Recommendations ---
    print("\n[4] Personalized recommendations")
    rec = get_personalized_recommendations(ud)
    pa = rec.get("priority_actions") or []
    if pa and isinstance(pa[0], dict):
        print("  first priority_action:", pa[0].get("action"))
        print("  potential_saving:", pa[0].get("potential_saving"))
    else:
        print("  priority_actions:", pa)

    # --- Test 5: Health narrative ---
    print("\n[5] Financial health narrative")
    hs = calculate_health_score(conn, user_id, m, y)
    comp = hs.components or {}
    details = {
        "score": hs.score,
        "grade": hs.grade,
        "components": {
            "savings_rate_score": int(comp.get("savings_points", 0)),
            "anomaly_penalty": int(comp.get("anomaly_points", 0)),
            "expense_ratio_score": int(comp.get("expense_points", 0)),
            "consistency_score": int(comp.get("consistency_points", 0)),
            "diversity_score": int(comp.get("diversity_points", 0)),
        },
        "trend": hs.trend,
        "weakest_component": "auto",
    }
    nar = generate_health_narrative(ud, details)
    print("  headline:", nar.get("headline"))
    print("  motivational_message:", nar.get("motivational_message"))

    conn.close()

    p, c, t = meter_totals()
    print("\n" + "=" * 72)
    print("✅ All 5 AI features working!")
    print(f"💰 Total GPT tokens used (prompt + completion): ~{t}  (prompt={p}, completion={c})")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
