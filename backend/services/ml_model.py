"""Enhanced Isolation Forest ML pipeline for transaction anomaly detection."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_PROJECT_ROOT / ".env")


class EnhancedIsolationForest:
    """
    Enhanced Isolation Forest for financial transaction anomaly detection.
    Uses 8 engineered features + StandardScaler + per-user category stats.
    """

    def __init__(self) -> None:
        self.models: dict[int, IsolationForest] = {}
        self.scalers: dict[int, StandardScaler] = {}
        self.encoders: dict[int, LabelEncoder] = {}
        self.user_stats: dict[int, dict[str, Any]] = {}

    def get_db_connection(self) -> psycopg2.extensions.connection:
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "smartspend_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )

    def fetch_user_transactions(self, user_id: int) -> pd.DataFrame:
        conn = self.get_db_connection()
        try:
            query = """
                SELECT id, amount, type, category, merchant,
                       hour_of_day, day_of_week, is_weekend, is_night_txn,
                       transaction_date, balance_after, payment_method,
                       anomaly_flag, ml_processed
                FROM transactions
                WHERE user_id = %s
                ORDER BY transaction_date DESC, id DESC
            """
            df = pd.read_sql_query(query, conn, params=(user_id,))
            return df
        finally:
            conn.close()

    def compute_user_stats(self, user_id: int, df: pd.DataFrame) -> None:
        debit_df = df[df["type"] == "DEBIT"].copy()
        stats: dict[str, Any] = {}

        for category in debit_df["category"].dropna().unique():
            cat_data = debit_df[debit_df["category"] == category]["amount"].astype(float)
            if len(cat_data) == 0:
                continue
            stats[str(category)] = {
                "mean": float(cat_data.mean()),
                "std": float(cat_data.std()) if len(cat_data) > 1 else float(cat_data.mean() * 0.3 + 1e-6),
                "max": float(cat_data.max()),
                "median": float(cat_data.median()),
                "q95": float(cat_data.quantile(0.95)),
                "count": int(len(cat_data)),
            }

        if len(debit_df) == 0:
            stats["_overall"] = {
                "mean": 1000.0,
                "std": 500.0,
                "max": 5000.0,
                "median": 800.0,
                "q95": 3000.0,
                "count": 0,
            }
        else:
            amt = debit_df["amount"].astype(float)
            stats["_overall"] = {
                "mean": float(amt.mean()),
                "std": float(amt.std()) if len(amt) > 1 else float(amt.mean() * 0.3 + 1e-6),
                "max": float(amt.max()),
                "median": float(amt.median()),
                "q95": float(amt.quantile(0.95)),
                "count": int(len(amt)),
            }

        self.user_stats[user_id] = stats

    def _safe_cat_encode(self, user_id: int, category: object) -> float:
        le = self.encoders[user_id]
        label = str(category) if category is not None and str(category) != "nan" else "Others"
        if label not in le.classes_:
            label = "Others" if "Others" in le.classes_ else le.classes_[0]
        return float(le.transform([label])[0])

    def engineer_features(self, df: pd.DataFrame, user_id: int) -> np.ndarray:
        stats = self.user_stats.get(user_id, {})
        overall = stats.get("_overall", {"mean": 1000.0, "std": 500.0})
        o_mean = max(float(overall["mean"]), 1e-6)
        o_std = max(float(overall["std"]), 1e-6)

        if user_id not in self.encoders:
            le = LabelEncoder()
            cats = df["category"].fillna("Others").astype(str).tolist()
            le.fit(sorted(set(cats) | {"Others"}))
            self.encoders[user_id] = le

        feats: list[list[float]] = []
        for _, row in df.iterrows():
            amt = float(row["amount"] or 0)
            amount_zscore = (amt - o_mean) / o_std

            cat_key = str(row["category"]) if pd.notna(row.get("category")) else "Others"
            cat_stats = stats.get(cat_key, overall)
            cat_mean = max(float(cat_stats.get("mean", o_mean)), 1e-6)
            cat_ratio = amt / cat_mean

            hour = row["hour_of_day"]
            hour = int(hour) if pd.notna(hour) else 12
            if hour >= 23 or hour <= 5:
                hour_risk = 2.0
            elif 20 <= hour <= 22:
                hour_risk = 1.0
            else:
                hour_risk = 0.0

            wk = row.get("is_weekend")
            is_weekend = 1.0 if (wk is True or wk == 1 or str(wk).lower() == "true") else 0.0

            dow = row.get("day_of_week")
            day_of_week = float(int(dow)) if pd.notna(dow) else 3.0

            bal = row.get("balance_after")
            if bal is None or (isinstance(bal, float) and np.isnan(bal)):
                balance = 100000.0
            else:
                balance = max(float(bal), 1.0)
            balance_ratio = amt / balance

            cat_encoded = self._safe_cat_encode(user_id, row.get("category"))

            a = abs(amt)
            is_round = 1.0 if (a >= 500 and (a % 1000 == 0 or a % 500 == 0)) else 0.0

            feats.append(
                [
                    amount_zscore,
                    cat_ratio,
                    hour_risk,
                    is_weekend,
                    day_of_week,
                    balance_ratio,
                    cat_encoded,
                    is_round,
                ]
            )

        return np.asarray(feats, dtype=np.float64)

    def train(self, user_id: int) -> bool:
        try:
            df = self.fetch_user_transactions(user_id)
            if len(df) < 10:
                print(f"⚠️  Not enough data for user {user_id}")
                return False

            train_df = df[df["type"] == "DEBIT"].copy()
            if len(train_df) < 10:
                print(f"⚠️  Not enough DEBIT rows for user {user_id}")
                return False

            self.compute_user_stats(user_id, df)
            features = self.engineer_features(train_df, user_id)

            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            self.scalers[user_id] = scaler

            model = IsolationForest(
                n_estimators=200,
                contamination=0.06,
                random_state=42,
                max_features=0.8,
            )
            model.fit(features_scaled)
            self.models[user_id] = model

            print(f"✅ ML model trained for user {user_id} on {len(train_df)} transactions")
            return True
        except Exception as e:
            print(f"❌ ML training failed for user {user_id}: {e}")
            return False

    def _risk_scores_from_samples(self, scores: np.ndarray) -> np.ndarray:
        """Lower score_samples = more anomalous → higher risk 0–100."""
        lo, hi = float(scores.min()), float(scores.max())
        span = hi - lo if hi > lo else 1e-6
        return np.clip(100.0 * (lo - scores) / span, 0, 100)

    def get_risk_level(self, risk_score: int) -> str:
        if risk_score >= 86:
            return "CRITICAL"
        if risk_score >= 61:
            return "HIGH"
        if risk_score >= 31:
            return "MEDIUM"
        return "LOW"

    def get_anomaly_reason(self, row: dict[str, Any], user_id: int) -> str:
        stats = self.user_stats.get(user_id, {})
        cat = row.get("category") or "Others"
        cat_key = str(cat)
        cat_stats = stats.get(cat_key, stats.get("_overall", {}))

        reasons: list[str] = []
        amt = float(row.get("amount") or 0)
        q95 = cat_stats.get("q95")
        if q95 is not None and amt > float(q95):
            ratio = amt / max(float(cat_stats.get("mean", 1)), 1)
            reasons.append(
                f"Amount is {ratio:.1f}x higher than usual for {cat_key}"
            )

        hour = row.get("hour_of_day")
        if hour is not None and (int(hour) >= 23 or int(hour) <= 5):
            reasons.append(f"Transaction at unusual hour ({int(hour)}:00)")

        if amt >= 5000 and amt % 5000 == 0:
            reasons.append("Suspiciously round amount")

        return ". ".join(reasons) if reasons else "Statistical anomaly detected by ML model"

    def detect_and_update(self, user_id: int, process_all: bool = False) -> dict[str, Any]:
        if user_id not in self.models:
            if not self.train(user_id):
                return {"processed": 0, "anomalies_found": 0, "high_risk": 0, "error": "train_failed"}

        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            if process_all:
                cursor.execute(
                    """
                    SELECT id, amount, type, category, merchant,
                           hour_of_day, day_of_week, is_weekend, is_night_txn,
                           transaction_date, balance_after, payment_method
                    FROM transactions
                    WHERE user_id = %s AND type = 'DEBIT'
                    ORDER BY id
                    """,
                    (user_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, amount, type, category, merchant,
                           hour_of_day, day_of_week, is_weekend, is_night_txn,
                           transaction_date, balance_after, payment_method
                    FROM transactions
                    WHERE user_id = %s AND type = 'DEBIT' AND ml_processed = FALSE
                    ORDER BY id
                    """,
                    (user_id,),
                )

            rows = cursor.fetchall()
            cols = [
                "id",
                "amount",
                "type",
                "category",
                "merchant",
                "hour_of_day",
                "day_of_week",
                "is_weekend",
                "is_night_txn",
                "transaction_date",
                "balance_after",
                "payment_method",
            ]

            if not rows:
                return {"processed": 0, "anomalies_found": 0, "high_risk": 0}

            df = pd.DataFrame(rows, columns=cols)
            features = self.engineer_features(df, user_id)
            features_scaled = self.scalers[user_id].transform(features)

            model = self.models[user_id]
            predictions = model.predict(features_scaled)
            scores = model.score_samples(features_scaled)
            risk_arr = self._risk_scores_from_samples(scores)

            anomalies_found = 0
            high_risk = 0

            for i in range(len(df)):
                row = df.iloc[i].to_dict()
                pred = predictions[i]
                is_out = bool(np.asarray(pred == -1).item())
                risk_score = int(round(float(risk_arr[i])))
                risk_level = self.get_risk_level(risk_score)
                reason = self.get_anomaly_reason(row, user_id) if is_out else None

                cursor.execute(
                    """
                    UPDATE transactions
                    SET anomaly_flag = %s,
                        risk_score = %s,
                        risk_level = %s,
                        anomaly_reason = %s,
                        ml_processed = TRUE
                    WHERE id = %s
                    """,
                    (is_out, risk_score, risk_level, reason, int(row["id"])),
                )

                if is_out:
                    anomalies_found += 1

                if is_out and risk_level in ("HIGH", "CRITICAL"):
                    high_risk += 1
                    tid = int(row["id"])
                    cursor.execute(
                        """
                        SELECT 1 FROM alerts
                        WHERE transaction_id = %s AND alert_type = 'ML_ANOMALY'
                        LIMIT 1
                        """,
                        (tid,),
                    )
                    if cursor.fetchone() is None:
                        merchant = row.get("merchant") or "Unknown"
                        cursor.execute(
                            """
                            INSERT INTO alerts (
                                user_id, transaction_id, severity, alert_type, message, detail
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                user_id,
                                tid,
                                risk_level,
                                "ML_ANOMALY",
                                f"Suspicious transaction detected: ₹{float(row['amount']):,.0f} at {merchant}",
                                (reason or "")[:2000],
                            ),
                        )

            conn.commit()
            return {
                "processed": len(rows),
                "anomalies_found": anomalies_found,
                "high_risk": high_risk,
            }
        except Exception as e:
            conn.rollback()
            print(f"❌ Detection failed for user {user_id}: {e}")
            return {"processed": 0, "anomalies_found": 0, "high_risk": 0, "error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def get_anomaly_summary(self, user_id: int) -> list[dict[str, Any]]:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT t.id, t.merchant, t.amount, t.transaction_date,
                       t.category, t.risk_score, t.risk_level, t.anomaly_reason,
                       t.hour_of_day, t.payment_method,
                       a.alert_type, a.severity
                FROM transactions t
                LEFT JOIN alerts a ON a.transaction_id = t.id AND a.alert_type = 'ML_ANOMALY'
                WHERE t.user_id = %s AND t.anomaly_flag = TRUE
                ORDER BY t.risk_score DESC, t.transaction_date DESC
                LIMIT 50
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                result.append(
                    {
                        "transaction_id": int(row[0]),
                        "merchant": row[1],
                        "amount": float(row[2]),
                        "transaction_date": str(row[3]),
                        "category": row[4],
                        "risk_score": int(row[5] or 0),
                        "risk_level": row[6],
                        "reason": row[7] or "Anomaly detected",
                        "hour": row[8],
                        "payment_method": row[9],
                        "alert_type": row[10],
                        "severity": row[11],
                    }
                )
            return result
        finally:
            cursor.close()
            conn.close()

    def train_all_users(self) -> None:
        conn = self.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name FROM users ORDER BY id")
            users = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        print(f"\n🤖 Training ML models for {len(users)} users...")
        for user_id, name in users:
            uid = int(user_id)
            print(f"   Training for {name}...")
            self.train(uid)
            result = self.detect_and_update(uid, process_all=False)
            print(
                f"   ✅ {name}: processed={result.get('processed', 0)}, "
                f"anomalies={result.get('anomalies_found', 0)}, high_risk={result.get('high_risk', 0)}"
            )
        print("🎯 ML Pipeline Ready!\n")


ml_detector = EnhancedIsolationForest()
