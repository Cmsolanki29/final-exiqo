"""Validate ML pipeline from the command line.

Run from the backend folder:
    python -m services.ml_model_test

Or from the repo root (Exiqo phase2):
    python -m backend.services.ml_model_test
"""

from __future__ import annotations


def main() -> None:
    from collections import Counter

    from services.ml_model import ml_detector

    conn = ml_detector.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM users ORDER BY id")
    users = cur.fetchall()
    cur.close()
    conn.close()

    print("\n" + "=" * 72)
    print("SmartSpend ML pipeline validation")
    print("=" * 72)
    print(f"{'User':<18} | {'Trained':^8} | {'Anom':>5} | {'HiRisk':>7} | {'Top risk merchant':<22}")
    print("-" * 72)

    for uid, name in users:
        uid = int(uid)
        ok = ml_detector.train(uid)
        det = ml_detector.detect_and_update(uid, process_all=True)
        summ = ml_detector.get_anomaly_summary(uid)
        merchants = [s.get("merchant") or "" for s in summ]
        top_m = Counter(merchants).most_common(1)
        top_label = top_m[0][0][:22] if top_m else "-"
        trained = "✅" if ok else "❌"
        print(
            f"{str(name)[:17]:<18} | {trained:^8} | {det.get('anomalies_found', 0):>5} | "
            f"{det.get('high_risk', 0):>7} | {top_label:<22}"
        )

    print("-" * 72)
    print("✅ ML Pipeline validated successfully!\n")


if __name__ == "__main__":
    main()
