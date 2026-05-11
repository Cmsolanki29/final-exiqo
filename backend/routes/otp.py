"""OTP demo routes for onboarding mobile verification."""

from __future__ import annotations

import random
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from db import get_connection

router = APIRouter(prefix="/otp", tags=["OTP"])


class SendOTPRequest(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)


class VerifyOTPRequest(BaseModel):
    mobile_number: str = Field(..., min_length=10, max_length=15)
    otp_code: str = Field(..., min_length=6, max_length=6)


@router.post("/send")
async def send_otp(data: SendOTPRequest) -> dict[str, int | str | bool]:
    """
    Generate and 'send' OTP (mock - stored in DB).
    For demo only: returns OTP in response.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        otp_code = str(random.randint(100000, 999999))
        cur.execute(
            """
            INSERT INTO otp_verifications (mobile_number, otp_code, expires_at, verified)
            VALUES (%s, %s, NOW() + INTERVAL '5 minutes', FALSE)
            """,
            (data.mobile_number, otp_code),
        )
        conn.commit()
        return {
            "success": True,
            "message": "OTP sent successfully",
            "otp_code": otp_code,  # demo-only
            "expires_in": 300,
        }
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    finally:
        cur.close()
        conn.close()


@router.post("/verify")
async def verify_otp(data: VerifyOTPRequest) -> dict[str, str | bool]:
    """Verify OTP code against latest record for mobile number."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, otp_code, expires_at, verified
            FROM otp_verifications
            WHERE mobile_number = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (data.mobile_number,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OTP found for this number")

        otp_id, otp_code, expires_at, verified = row[0], row[1], row[2], row[3]
        if verified:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP already used")
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
        if str(otp_code) != data.otp_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

        cur.execute("UPDATE otp_verifications SET verified = TRUE WHERE id = %s", (otp_id,))
        cur.execute(
            "UPDATE users SET is_verified = TRUE WHERE phone = %s",
            (data.mobile_number,),
        )
        conn.commit()
        return {"success": True, "message": "OTP verified successfully", "mobile_number": data.mobile_number}
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    finally:
        cur.close()
        conn.close()
