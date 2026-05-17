"""Quick check: scoped fraud + EMI for user 19."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
import psycopg2

pw = os.getenv("DB_PASSWORD", "").strip().strip('"').strip("'")
conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=pw,
)
from routes.fraud_shield import fraud_stats, list_alerts
from routes.emi_detector import _build_emi_detection

cur = conn.cursor()
cur.execute("UPDATE users SET dashboard_mode='credit_card_only' WHERE id=19")
conn.commit()
print("stats", fraud_stats(19, conn))
al = list_alerts(19, conn=conn)
print("alerts", len(al["alerts"]))
for a in al["alerts"][:6]:
    print(" ", a.get("merchant"), a.get("risk_score"), a.get("pattern_matched"))
r = _build_emi_detection(conn, 19)
for e in r["emis_detected"]:
    if "card" in e["merchant"].lower() or "axis" in e["merchant"].lower():
        print("emi", e["merchant"], e["amount"])
conn.close()
