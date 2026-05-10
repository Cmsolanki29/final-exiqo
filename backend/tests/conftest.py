"""pytest configuration for SmartSpend backend tests.

Provides shared fixtures for:
  - FastAPI test client (httpx AsyncClient)
  - Mock Redis client (fakeredis)
  - Mock asyncpg pool
  - Pre-trained ml_detector with synthetic data

Phases use these fixtures so tests never hit a real DB or Redis.
"""

from __future__ import annotations

import asyncio
from datetime import date, time
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient


# ------------------------------------------------------------------ #
# Event loop — single loop for the entire test session
# ------------------------------------------------------------------ #
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ------------------------------------------------------------------ #
# App fixture — patches DB + Redis so the app starts without infra
# ------------------------------------------------------------------ #
@pytest.fixture(scope="session")
def app():
    """Return the FastAPI app with infra patched out."""
    with (
        patch("core.db.init_pool", new_callable=AsyncMock),
        patch("core.db.close_pool", new_callable=AsyncMock),
        patch("core.redis.init_redis", new_callable=AsyncMock),
        patch("core.redis.close_redis", new_callable=AsyncMock),
        patch("core.redis.get_redis", return_value=None),
        patch("workers.alert_consumer.alert_consumer.start", new_callable=AsyncMock),
        patch("services.ml_model.ml_detector.train_all_users"),
    ):
        from main import app as _app
        yield _app


@pytest_asyncio.fixture(scope="session")
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient connected to the patched FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture(scope="session")
def sync_client(app):
    """Sync TestClient for simple non-async tests."""
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ------------------------------------------------------------------ #
# Mock psycopg2 connection (used by routes that call get_db)
# ------------------------------------------------------------------ #
@pytest.fixture
def mock_conn():
    """A mock psycopg2 connection.  Configure fetchone/fetchall per test."""
    conn = MagicMock()
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor
    return conn


# ------------------------------------------------------------------ #
# Pre-trained ml_detector (in-memory, no DB)
# ------------------------------------------------------------------ #
@pytest.fixture(scope="session")
def trained_detector():
    """EnsembleAnomalyDetector trained on synthetic debit data for user 999."""
    from services.ml_model import EnsembleAnomalyDetector

    rng = np.random.default_rng(42)
    n = 60
    detector = EnsembleAnomalyDetector()
    uid = 999

    rows = []
    for i in range(n):
        rows.append({
            "id": i + 1,
            "amount": float(rng.integers(200, 5000)),
            "type": "DEBIT",
            "category": rng.choice(["Food", "Shopping", "Transport", "Bills"]),
            "merchant": f"Merchant{rng.integers(1, 10)}",
            "hour_of_day": int(rng.integers(8, 22)),
            "day_of_week": int(rng.integers(0, 7)),
            "is_weekend": bool(rng.integers(0, 2)),
            "is_night_txn": False,
            "transaction_date": date(2024, rng.integers(1, 13).item(), rng.integers(1, 28).item()),
            "transaction_time": time(int(rng.integers(8, 22)), 0),
            "balance_after": float(rng.integers(10000, 100000)),
            "payment_method": "UPI",
            "location": "Home",
            "anomaly_flag": False,
            "ml_processed": False,
        })

    df = pd.DataFrame(rows)
    detector.compute_user_stats(uid, df)

    debit_df = df[df["type"] == "DEBIT"].copy()
    enriched = detector.enrich_velocity_and_rollups(debit_df)
    detector.train.__func__  # ensure method exists

    # Directly build internal state without DB
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from pyod.models.iforest import IForest as PyODIForest

    le = LabelEncoder()
    le.fit(["Food", "Shopping", "Transport", "Bills", "Others"])
    detector.encoders[uid] = le

    features = detector.engineer_features(enriched, uid)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(np.nan_to_num(features, nan=0.0))
    detector.scalers[uid] = scaler

    iforest = PyODIForest(n_estimators=50, contamination=0.05, random_state=42)
    iforest.fit(Xs)
    detector.models_if[uid] = iforest

    combined = detector._combined_inference_scores(uid, Xs)
    detector.thresholds[uid] = float(np.nanquantile(combined, 0.95))
    detector.use_copod[uid] = False
    detector.use_pca[uid] = False

    # Store training-time score bounds for score_single normalisation
    if_raw = iforest.decision_function(Xs)
    detector.score_bounds[uid] = {
        "if_min": float(np.nanmin(if_raw)),
        "if_max": float(np.nanmax(if_raw)),
    }

    return detector


# ------------------------------------------------------------------ #
# Sample transaction dicts
# ------------------------------------------------------------------ #
@pytest.fixture
def normal_txn_dict():
    return {
        "amount": 500.0,
        "type": "DEBIT",
        "category": "Food",
        "merchant": "Swiggy",
        "hour_of_day": 13,
        "day_of_week": 2,
        "is_weekend": False,
        "is_night_txn": False,
        "transaction_date": date(2024, 6, 15),
        "transaction_time": time(13, 0),
        "balance_after": 50000.0,
        "payment_method": "UPI",
        "location": "Home",
    }


@pytest.fixture
def high_risk_txn_dict():
    """Characteristics that should push risk score high: very high amount, late night."""
    return {
        "amount": 150000.0,
        "type": "DEBIT",
        "category": "Shopping",
        "merchant": "NewUnknownMerchant",
        "hour_of_day": 3,
        "day_of_week": 6,
        "is_weekend": True,
        "is_night_txn": True,
        "transaction_date": date(2024, 6, 15),
        "transaction_time": time(3, 0),
        "balance_after": 200.0,
        "payment_method": "UPI",
        "location": "Unknown",
    }
