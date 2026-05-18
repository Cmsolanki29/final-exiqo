"""Phase 9-12 admin authentication (audit-8).

The Phase 1-8 admin convention in this codebase is the ``X-Admin-Token``
header verified against the ``ADMIN_TOKEN`` env var.  Phase 9-12 admin
routes inherited that convention, which is *consistent* with Phase 1-8
but *inconsistent* with the user-facing endpoints that use JWT.

The audit (issue #8) flagged this and asked us to migrate to JWT.
After the user's review the chosen direction is:

* **Additive — do not break the X-Admin-Token contract.**
* Phase 9-12 admin routes additionally accept a JWT bearer token whose
  ``user_id`` claim appears in the ``ADMIN_USER_IDS`` env var
  (comma-separated list of integer ids).
* Phase 1-8 routes are NOT touched.  This is teammate territory and the
  refactor would force a coordinated PR — out of scope for this branch.

This module exposes a single FastAPI dependency, ``require_admin``,
that succeeds when *either* of the two auth paths is satisfied.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer

from utils.auth import decode_token

_optional_bearer = HTTPBearer(auto_error=False)


def _admin_user_ids() -> set[int]:
    raw = os.getenv("ADMIN_USER_IDS", "").strip()
    out: set[int] = set()
    for piece in raw.replace(";", ",").split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.add(int(piece))
        except ValueError:
            continue
    return out


def _expected_admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "dev-admin-secret")


def _check_jwt(token: Optional[str]) -> Optional[int]:
    """Return the JWT's user_id if it parses AND belongs to an admin.

    Never raises; on any failure returns None so the caller can decide
    whether to fall back to X-Admin-Token.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
    except HTTPException:
        return None
    except Exception:  # noqa: BLE001
        return None
    if payload.get("type") != "access":
        return None
    user_id = payload.get("user_id")
    if user_id is None:
        return None
    try:
        uid_int = int(user_id)
    except (TypeError, ValueError):
        return None
    return uid_int if uid_int in _admin_user_ids() else None


def require_admin(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    bearer = Depends(_optional_bearer),
) -> dict:
    """FastAPI dependency: succeeds on JWT-admin OR X-Admin-Token.

    Returns a small audit dict identifying which path matched, useful
    for logging in admin handlers.

    Failure: raises 401 with a hint covering both auth paths.
    """
    # --- Path A: JWT bearer token ---
    bearer_token: Optional[str] = None
    if bearer is not None:
        bearer_token = bearer.credentials  # type: ignore[union-attr]
    else:
        auth_hdr = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            bearer_token = auth_hdr.split(" ", 1)[1].strip()

    admin_uid = _check_jwt(bearer_token)
    if admin_uid is not None:
        return {"auth_path": "jwt", "user_id": admin_uid}

    # --- Path B: X-Admin-Token (legacy / Phase 1-8 compatible) ---
    if x_admin_token and x_admin_token == _expected_admin_token():
        return {"auth_path": "x_admin_token", "user_id": None}

    raise HTTPException(
        status_code=401,
        detail=(
            "Admin auth required.  Provide either an X-Admin-Token "
            "header OR an Authorization: Bearer <jwt> whose user_id is "
            "in the ADMIN_USER_IDS allow-list."
        ),
    )


def verify_admin_or_transaction_owner(request: Request, transaction_id: int) -> dict[str, Any]:
    """Allow Phase 9 read/run if admin (X-Admin-Token or JWT admin list) OR JWT owns the transaction.

    Used by investigation routes so normal users can investigate their own flagged txns
    without REACT_APP_ADMIN_TOKEN.
    """
    x_admin = request.headers.get("X-Admin-Token") or request.headers.get("x-admin-token")
    if x_admin and x_admin == _expected_admin_token():
        return {"auth_path": "x_admin_token", "user_id": None}

    bearer_token: Optional[str] = None
    auth_hdr = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_hdr and auth_hdr.lower().startswith("bearer "):
        bearer_token = auth_hdr.split(" ", 1)[1].strip()

    admin_uid = _check_jwt(bearer_token)
    if admin_uid is not None:
        return {"auth_path": "jwt_admin", "user_id": admin_uid}

    if not bearer_token:
        raise HTTPException(
            status_code=401,
            detail="Sign in to run investigations, or use admin credentials.",
        )
    try:
        payload = decode_token(bearer_token)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session. Sign in again to investigate your transactions.",
        ) from None
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    try:
        uid = int(payload.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token payload") from None

    from db import get_connection  # noqa: PLC0415

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM transactions WHERE id = %s", (transaction_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row or int(row[0]) != uid:
        raise HTTPException(
            status_code=403,
            detail="You can only access investigations for your own transactions.",
        )
    return {"auth_path": "jwt_owner", "user_id": uid}
