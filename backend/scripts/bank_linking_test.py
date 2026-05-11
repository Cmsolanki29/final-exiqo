"""
Bank Linking Real Test Script
Tests the full bank-linking flow for a fresh user:
  1. Register new user
  2. Send OTP (returns code in demo mode)
  3. Verify OTP
  4. Link each bank (happy path, wrong creds, duplicate)
  5. Verify DB rows
  6. Print full test matrix
"""
import base64
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import requests


def decode_jwt_user_id(token: str) -> int | None:
    """Decode JWT payload without verifying signature to extract user_id."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        padding = 4 - len(parts[1]) % 4
        payload_b64 = parts[1] + "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("user_id")
    except Exception:
        return None

BASE_URL = "http://localhost:8000"
MOBILE_NUMBER = "9876543210"
BANKS = ["hdfc", "sbi", "icici", "axis", "kotak"]
BANK_DISPLAY = {
    "hdfc": "HDFC Bank",
    "sbi": "State Bank of India",
    "icici": "ICICI Bank",
    "axis": "Axis Bank",
    "kotak": "Kotak Mahindra",
}

results = {}


def step(msg: str, ok: bool, detail: str = ""):
    status = "[PASS]" if ok else "[FAIL]"
    print(f"  {status}: {msg}" + (f" - {detail}" if detail else ""))
    return ok


def main():
    print("=" * 60)
    print("BANK LINKING REAL TEST  -  test_bank_user_001")
    print("=" * 60)

    # ── STEP 1: Register fresh test user ──────────────────────────
    print("\n[1] Registering fresh test user …")
    reg = requests.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Bank Test User",
        "email": f"banktest_{int(datetime.now().timestamp())}@fraudshield.dev",
        "password": "Pass@123",
    }, timeout=15)

    # Some apps return 200 or 201
    if reg.status_code not in (200, 201):
        # Try login with existing banktest user if signup disabled
        step("Signup", False, f"HTTP {reg.status_code}: {reg.text[:200]}")
        # Try to log in as a previously created test user
        login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "banktest@fraudshield.dev",
            "password": "Pass@123",
        }, timeout=15)
        if login.status_code != 200:
            print("FATAL: Cannot create or login test user. Abort.")
            return
        token = login.json().get("access_token") or login.json().get("token")
        user_id = login.json().get("user_id") or login.json().get("id")
        step("Login existing banktest user", True, f"user_id={user_id}")
    else:
        data = reg.json()
        token = data.get("access_token") or data.get("token")
        user_id = (
            data.get("user_id")
            or data.get("id")
            or (data.get("user") or {}).get("id")
            or (decode_jwt_user_id(token) if token else None)
        )
        step("Signup", True, f"user_id={user_id}")

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # ── STEP 2: Send OTP ──────────────────────────────────────────
    print("\n[2] Sending OTP …")
    otp_send = requests.post(f"{BASE_URL}/api/otp/send", json={
        "mobile_number": MOBILE_NUMBER,
    }, timeout=15)
    if otp_send.status_code != 200:
        step("Send OTP", False, f"HTTP {otp_send.status_code}: {otp_send.text[:200]}")
        return
    otp_code = otp_send.json().get("otp_code")
    step("Send OTP", True, f"OTP code returned: {otp_code}")

    # ── STEP 3: Verify OTP ────────────────────────────────────────
    print("\n[3] Verifying OTP …")
    otp_verify = requests.post(f"{BASE_URL}/api/otp/verify", json={
        "mobile_number": MOBILE_NUMBER,
        "otp_code": str(otp_code),
    }, timeout=15)
    ok = otp_verify.status_code == 200
    step("Verify OTP", ok, otp_verify.text[:100] if not ok else "")
    if not ok:
        return

    # ── STEP 4: Happy path — link each bank ───────────────────────
    print("\n[4] Happy-path bank linking …")
    for slug in BANKS:
        display = BANK_DISPLAY[slug]
        payload = {
            "bank_slug": slug,
            "mobile_number": MOBILE_NUMBER,
        }
        r = requests.post(f"{BASE_URL}/api/onboarding/link-bank", json=payload, headers=headers, timeout=15)
        ok = r.status_code == 200
        results.setdefault(display, {})["happy_path"] = "PASS" if ok else f"FAIL {r.status_code}: {r.text[:80]}"
        step(f"Happy Path — {display}", ok, r.text[:80] if not ok else r.json().get("message", "linked"))

        # Re-send and re-verify OTP for subsequent banks (OTP gets consumed)
        if slug != BANKS[-1]:
            otp_send2 = requests.post(f"{BASE_URL}/api/otp/send", json={"mobile_number": MOBILE_NUMBER}, timeout=15)
            if otp_send2.status_code == 200:
                new_code = otp_send2.json().get("otp_code")
                requests.post(f"{BASE_URL}/api/otp/verify", json={
                    "mobile_number": MOBILE_NUMBER,
                    "otp_code": str(new_code),
                }, timeout=15)

    # ── STEP 5: Wrong credentials test ───────────────────────────
    print("\n[5] Wrong-credentials tests (unverified OTP mobile number) ...")
    # Use a second throwaway token/user to test wrong creds on fresh banks
    # The mock system treats OTP failure as wrong creds: mobile must have verified OTP
    for slug in ["hdfc", "sbi"]:
        display = BANK_DISPLAY[slug]
        # Use a number that has never had OTP sent/verified
        r = requests.post(f"{BASE_URL}/api/onboarding/link-bank", json={
            "bank_slug": slug,
            "mobile_number": "0000000000",  # unverified → OTP not verified
        }, headers=headers, timeout=15)
        # Expected: 400 (Send OTP first / OTP not verified) — pass for wrong-creds test
        expected_fail = r.status_code in (400, 422)
        results.setdefault(display, {})["wrong_creds"] = "PASS" if expected_fail else f"WARN {r.status_code}"
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text[:80]
        step(f"Wrong Creds — {display}", expected_fail,
             f"Got {r.status_code}: {detail}" if expected_fail else f"Unexpected {r.status_code}: {r.text[:80]}")

    # ── STEP 6: Duplicate link test ───────────────────────────────
    print("\n[6] Duplicate link tests …")
    # Re-verify OTP for our main number
    otp_send4 = requests.post(f"{BASE_URL}/api/otp/send", json={"mobile_number": MOBILE_NUMBER}, timeout=15)
    if otp_send4.status_code == 200:
        c = otp_send4.json().get("otp_code")
        requests.post(f"{BASE_URL}/api/otp/verify", json={"mobile_number": MOBILE_NUMBER, "otp_code": str(c)}, timeout=15)

    for slug in ["hdfc", "icici"]:
        display = BANK_DISPLAY[slug]
        r = requests.post(f"{BASE_URL}/api/onboarding/link-bank", json={
            "bank_slug": slug,
            "mobile_number": MOBILE_NUMBER,
        }, headers=headers, timeout=15)
        # unique constraint → 500 with psycopg2 UniqueViolation, or a 409
        is_dup_rejected = r.status_code in (400, 409, 422, 500)
        results.setdefault(display, {})["duplicate"] = "PASS" if is_dup_rejected else f"FAIL {r.status_code}"
        step(f"Duplicate — {display}", is_dup_rejected,
             f"Rejected HTTP {r.status_code}" if is_dup_rejected else f"Unexpectedly accepted: {r.text[:80]}")

    # ── STEP 7: Verify DB rows ─────────────────────────────────────
    print("\n[7] DB verification …")
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    import psycopg2

    DB = dict(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "smartspend_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    db = psycopg2.connect(**DB)
    cur = db.cursor()
    cur.execute("SELECT bank_name, connection_status FROM bank_connections WHERE user_id=%s ORDER BY bank_name", (user_id,))
    linked = cur.fetchall()
    print(f"  DB rows for user_id={user_id}:")
    for row in linked:
        print(f"    bank={row[0]}, status={row[1]}")

    db_ok = len(linked) >= 3
    step(f"At least 3 banks in DB for user {user_id}", db_ok, f"found {len(linked)} banks")

    # Check no duplicate rows
    cur.execute(
        "SELECT bank_name, COUNT(*) FROM bank_connections WHERE user_id=%s GROUP BY bank_name HAVING COUNT(*) > 1",
        (user_id,)
    )
    dups = cur.fetchall()
    step("No duplicate bank rows", len(dups) == 0, f"duplicates: {dups}" if dups else "")

    cur.close()
    db.close()

    # ── STEP 8: Print matrix ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("BANK LINKING REAL TEST RESULTS")
    print("=" * 60)
    print(f"{'Bank':<25} {'Happy Path':<15} {'Wrong Creds':<15} {'Duplicate':<15} {'DB Row'}")
    print("-" * 80)
    for bank_name in [BANK_DISPLAY[s] for s in BANKS]:
        r = results.get(bank_name, {})
        happy = r.get("happy_path", "—")
        wrong = r.get("wrong_creds", "—")
        dup = r.get("duplicate", "—")
        db_row = "PASS" if any(b[0] == bank_name for b in linked) else "FAIL"
        print(f"{bank_name:<25} {happy:<15} {wrong:<15} {dup:<15} {db_row}")

    print(f"\nUser ID tested: {user_id}")
    print(f"Total linked banks: {len(linked)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
