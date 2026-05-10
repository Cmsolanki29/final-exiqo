"""audit-8: Phase 9-12 admin auth (X-Admin-Token OR JWT).

Verifies that the shared ``services.risk_common.admin_auth.require_admin``
dependency:
  1. accepts a valid X-Admin-Token (legacy path, Phase 1-8 compatible);
  2. accepts an Authorization: Bearer JWT whose user_id is in the
     ADMIN_USER_IDS allow-list;
  3. rejects a JWT whose user_id is NOT in the allow-list, even if the
     JWT is well-formed and signed with the right secret;
  4. rejects requests with neither credential.

The tests build a tiny FastAPI app inline so we don't need to spin up
the full risk-engine import graph (which depends on Postgres / Redis).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _build_app() -> FastAPI:
    """Mount a single admin endpoint behind require_admin."""
    from services.risk_common.admin_auth import require_admin

    app = FastAPI()

    @app.get("/probe")
    async def probe(_admin: dict = Depends(require_admin)) -> dict[str, Any]:
        return {"ok": True, "auth": _admin}

    return app


def test_x_admin_token_happy_path(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-xat")
    monkeypatch.setenv("ADMIN_USER_IDS", "")  # JWT path off

    client = TestClient(_build_app())
    r = client.get("/probe", headers={"X-Admin-Token": "secret-xat"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["auth"]["auth_path"] == "x_admin_token"
    assert body["auth"]["user_id"] is None


def test_jwt_admin_happy_path(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "wrong-on-purpose")
    monkeypatch.setenv("ADMIN_USER_IDS", "42, 99")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    # Reload the auth module so the new SECRET_KEY actually takes effect.
    # utils.auth reads SECRET_KEY at import time.
    import importlib

    from utils import auth as utils_auth
    importlib.reload(utils_auth)

    token = utils_auth.create_access_token(user_id=42, email="alice@example.com")

    # Re-import admin_auth to make sure it picks up the reloaded utils.auth.
    from services.risk_common import admin_auth as admin_auth_mod
    importlib.reload(admin_auth_mod)

    app = FastAPI()

    @app.get("/probe")
    async def probe(_admin: dict = Depends(admin_auth_mod.require_admin)):
        return {"ok": True, "auth": _admin}

    client = TestClient(app)
    r = client.get("/probe", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["auth"]["auth_path"] == "jwt"
    assert body["auth"]["user_id"] == 42


def test_jwt_with_non_admin_user_rejected(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "wrong-on-purpose")
    monkeypatch.setenv("ADMIN_USER_IDS", "42, 99")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    import importlib

    from utils import auth as utils_auth
    importlib.reload(utils_auth)
    from services.risk_common import admin_auth as admin_auth_mod
    importlib.reload(admin_auth_mod)

    # user_id 7 is NOT in the admin allow-list
    token = utils_auth.create_access_token(user_id=7)

    app = FastAPI()

    @app.get("/probe")
    async def probe(_admin: dict = Depends(admin_auth_mod.require_admin)):
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/probe", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "Admin auth required" in r.json()["detail"]


def test_no_credentials_rejected(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-xat")
    monkeypatch.setenv("ADMIN_USER_IDS", "42")

    client = TestClient(_build_app())
    r = client.get("/probe")  # no headers
    assert r.status_code == 401


def test_wrong_x_admin_token_rejected(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "secret-xat")
    monkeypatch.setenv("ADMIN_USER_IDS", "")

    client = TestClient(_build_app())
    r = client.get("/probe", headers={"X-Admin-Token": "guess"})
    assert r.status_code == 401
