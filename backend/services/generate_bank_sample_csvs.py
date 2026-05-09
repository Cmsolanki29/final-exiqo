"""
One-off / repeatable generator for 5 Indian bank sample CSVs (800 rows each).
Run from repo root: python backend/services/generate_bank_sample_csvs.py
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_csvs"

TxnKind = Literal["debit", "credit"]


@dataclass
class RawTxn:
    d: date
    kind: TxnKind
    amount: float
    narration_builder: str  # key for formatter
    extra: dict | None = None


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _month_label(d: date) -> str:
    return d.strftime("%b").upper()[:3] + d.strftime("%y")


def build_event_list(rng: random.Random, opening_hint: str) -> list[RawTxn]:
    """Exactly 800 transactions Nov 2025 – Apr 2026: 48 recurring + 18 anomalies + 734 daily."""
    start = date(2025, 11, 1)
    end = date(2026, 4, 30)
    days = list(_daterange(start, end))
    events: list[RawTxn] = []

    # --- Recurring monthly (6 months × 8) = 48 ---
    for m in range(11, 13):
        events += _monthly_recurring(date(2025, m, 1), rng)
    for m in range(1, 5):
        events += _monthly_recurring(date(2026, m, 1), rng)

    # --- 18 ML anomalies ---
    events.extend(_anomalies(rng))

    # --- Daily filler: 734 = 10×5 + 171×4 ---
    extra_days = set(rng.sample(days, 10))
    for d in days:
        n = 5 if d in extra_days else 4
        for _ in range(n):
            events.append(_random_daily(d, rng))

    assert len(events) == 800, len(events)
    # Credits first on each day (e.g. salary on 1st before spends)
    events.sort(key=lambda e: (e.d, 0 if e.kind == "credit" else 1, e.narration_builder))
    return events


def _monthly_recurring(month_start: date, rng: random.Random) -> list[RawTxn]:
    y, m = month_start.year, month_start.month
    ml = _month_label(month_start)
    out: list[RawTxn] = []
    out.append(RawTxn(date(y, m, 1), "credit", 85000.0, "SALARY", {"ml": ml}))
    out.append(RawTxn(date(y, m, 5), "debit", 18000.0, "RENT", {"ml": ml}))
    out.append(RawTxn(date(y, m, 8), "debit", 999.0, "INET", {}))
    out.append(RawTxn(date(y, m, 10), "debit", float(rng.randint(2200, 3500)), "ELEC", {}))
    out.append(RawTxn(date(y, m, 12), "debit", 499.0, "NFLX", {}))
    out.append(RawTxn(date(y, m, 15), "debit", 119.0, "SPOT", {}))
    out.append(RawTxn(date(y, m, 18), "debit", 299.0, "PRIME", {}))
    out.append(RawTxn(date(y, m, 20), "debit", 299.0, "HOT", {}))
    return out


def _anomalies(rng: random.Random) -> list[RawTxn]:
    """Inject 18 suspicious / edge-case rows."""
    a: list[RawTxn] = []
    # Sunday NEFT large — 2026-03-15 is Sunday
    a.append(RawTxn(date(2026, 3, 15), "debit", 95000.0, "ANOM_SUNDAY_NEFT", {}))
    a.append(RawTxn(date(2025, 11, 18), "debit", 52000.0, "ANOM_CRYPTO", {}))
    a.append(RawTxn(date(2025, 12, 3), "debit", 48000.0, "ANOM_BINANCE", {}))
    a.append(RawTxn(date(2026, 1, 22), "debit", 75000.0, "ANOM_XYZ", {}))
    a.append(RawTxn(date(2026, 2, 14), "debit", 100000.0, "ANOM_ROUND", {}))
    a.append(RawTxn(date(2026, 4, 2), "debit", 2500.0, "ANOM_DUP1", {}))
    a.append(RawTxn(date(2026, 4, 2), "debit", 2500.0, "ANOM_DUP2", {}))
    a.append(RawTxn(date(2025, 11, 27), "debit", 89000.0, "ANOM_WIRE", {}))
    a.append(RawTxn(date(2026, 2, 2), "debit", 1.0, "ANOM_PROBE", {}))
    a.append(RawTxn(date(2026, 2, 2), "debit", 1.0, "ANOM_PROBE2", {}))
    a.append(RawTxn(date(2025, 12, 25), "debit", 62000.0, "ANOM_GIFT", {}))
    a.append(RawTxn(date(2026, 1, 5), "debit", 33000.0, "ANOM_CASHOUT", {}))
    a.append(RawTxn(date(2026, 3, 28), "debit", 41000.0, "ANOM_FOREX", {}))
    # Burst same 25 minutes — 2026-04-10
    burst_day = date(2026, 4, 10)
    for i in range(5):
        a.append(RawTxn(burst_day, "debit", float(120 + i * 17), "ANOM_BURST", {"i": i}))
    return a


def _random_daily(d: date, rng: random.Random) -> RawTxn:
    food = [
        ("UPI_FOOD_SW", "SWIGGY"),
        ("UPI_FOOD_ZO", "ZOMATO"),
        ("POS_DOM", "DOMINOS"),
        ("POS_MCD", "MCDONALDS"),
        ("POS_KFC", "KFC"),
        ("POS_SB", "STARBUCKS"),
        ("POS_CCD", "CCD"),
        ("POS_HAL", "HALDIRAMS"),
    ]
    transport = [
        ("UPI_UBER", "UBER"),
        ("UPI_OLA", "OLA"),
        ("UPI_RAP", "RAPIDO"),
        ("POS_IOCL", "INDIAN OIL"),
        ("POS_HP", "HP PETROL"),
        ("POS_BP", "BHARAT PETROLEUM"),
    ]
    shop = [
        ("UPI_AMZ", "AMAZON"),
        ("POS_FLIP", "FLIPKART"),
        ("ECOM_MYN", "MYNTRA"),
        ("UPI_BB", "BIGBASKET"),
        ("POS_DMART", "DMART"),
        ("POS_REL", "RELIANCE FRESH"),
    ]
    bills = [
        ("BBPS_ELEC", "ADANI ELECTRICITY"),
        ("BBPS_TP", "TATA POWER"),
        ("UPI_JIO", "JIO"),
        ("UPI_AIRTEL", "AIRTEL"),
        ("UPI_VI", "VI"),
        ("BBPS_ACT", "ACT FIBERNET"),
    ]
    ent = [("UPI_BMS", "BOOKMYSHOW"), ("POS_PVR", "PVR CINEMAS"), ("POS_INOX", "INOX")]
    health = [
        ("POS_APOLLO", "APOLLO PHARMACY"),
        ("UPI_NETMEDS", "NETMEDS"),
        ("UPI_PE", "PHARMEASY"),
        ("POS_FORTIS", "FORTIS HOSPITAL"),
    ]
    pool = food + transport + shop + bills + ent + health
    key, _merch = rng.choice(pool)
    amt = float(rng.choice([49, 99, 149, 199, 249, 299, 349, 499, 799, 1299, 1899, 2499]))
    return RawTxn(d, "debit", amt, key, {})


# --- Narration formatters per bank ---

def fmt_hdfc(e: RawTxn, ref: str, rng: random.Random) -> tuple[str, str, str, str, str, str]:
    ml = e.extra.get("ml", "NOV25") if e.extra else "NOV25"
    if e.narration_builder == "SALARY":
        nar = f"NEFT-HDFC0001234-ABC TECHNOLOGIES PVT LTD-SALARY {ml}-{ref}"
    elif e.narration_builder == "RENT":
        nar = f"NEFT DR-SBIN0012345-KUMAR LANDLORD-RENT {ml}-N{ref[-9:]}"
    elif e.narration_builder == "INET":
        nar = "UPI-ACT FIBERNET-act@axisbank-AXISBANK-ACT987654"
    elif e.narration_builder == "ELEC":
        nar = f"BBPS/ADANI ELECTRICITY MUMBAI/{ref}"
    elif e.narration_builder == "NFLX":
        nar = "UPI-NETFLIX-netflix@icici-ICICIBANK-NFLX001"
    elif e.narration_builder == "SPOT":
        nar = "UPI-SPOTIFY-spotify@ybl-PAYTMBANK-SPT002"
    elif e.narration_builder == "PRIME":
        nar = "UPI-AMAZON PAY-amazonpay@icici-ZZZ345678"
    elif e.narration_builder == "HOT":
        nar = "UPI-HOTSTAR-hotstar@paytm-PAYTM-HTS003"
    elif e.narration_builder == "ANOM_CRYPTO":
        nar = "UPI-CRYPTOX EXCHANGE DUBAI-cryptox@ybl-YESBANK-CRX882211"
    elif e.narration_builder == "ANOM_BINANCE":
        nar = "UPI-BINANCE INT-binance@ibl-HDFCBANK-BNX991122"
    elif e.narration_builder == "ANOM_SUNDAY_NEFT":
        nar = f"NEFT DR-HDFC0099887-UNKNOWN BENEFICIARY-LARGE TXN SUN-N{ref[-9:]}"
    elif e.narration_builder == "ANOM_XYZ":
        nar = "UPI-XYZ TRADING LTD-xyztrd@okaxis-AXISBANK-XYZ554433"
    elif e.narration_builder == "ANOM_ROUND":
        nar = "NEFT DR-ICIC0002211-ROUND FIG TEST-N888777666"
    elif e.narration_builder in ("ANOM_DUP1", "ANOM_DUP2"):
        nar = f"POS 334455 DUPLICATE MERCHANT MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder == "ANOM_WIRE":
        nar = "NEFT DR-SBIN0099001-OFFSHORE REMIT TEST-N776655443"
    elif e.narration_builder in ("ANOM_PROBE", "ANOM_PROBE2"):
        nar = "UPI-VERIFY-probe@ybl-PAYTMBANK-PRB001"
    elif e.narration_builder == "ANOM_GIFT":
        nar = "UPI-LARGE GIFT-lrgift@paytm-PAYTMBANK-GFTXMAS"
    elif e.narration_builder == "ANOM_CASHOUT":
        nar = "ATM WDL AT HDFC0067890 ANDHERI"
    elif e.narration_builder == "ANOM_FOREX":
        nar = "POS 998877 FOREX CARD LOAD SINGAPORE CARD XX2233"
    elif e.narration_builder == "ANOM_BURST":
        i = e.extra.get("i", 0) if e.extra else 0
        nar = f"UPI-SWIGGY-swiggy@ybl-PAYTMBANK-BRST{i:03d}{ref[-6:]}"
    elif e.narration_builder.startswith("UPI_FOOD"):
        code = ref[-6:]
        if "SW" in e.narration_builder:
            nar = f"UPI-SWIGGY-swiggy@ybl-PAYTMBANK-{code}"
        else:
            nar = f"UPI-ZOMATO-zomato@paytm-YESBANK-{code}"
    elif e.narration_builder.startswith("POS_DOM"):
        nar = f"POS {rng.randint(100000,999999)} DOMINOS ANDHERI W MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_MCD"):
        nar = f"POS {rng.randint(100000,999999)} MCDONALDS ANDHERI W MUMBAI"
    elif e.narration_builder.startswith("POS_KFC"):
        nar = f"POS {rng.randint(100000,999999)} KFC POWAI MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_SB"):
        nar = f"POS {rng.randint(100000,999999)} STARBUCKS BANDRA MUMBAI"
    elif e.narration_builder.startswith("POS_CCD"):
        nar = f"POS {rng.randint(100000,999999)} CCD LINKING RD MUMBAI"
    elif e.narration_builder.startswith("POS_HAL"):
        nar = f"POS {rng.randint(100000,999999)} HALDIRAMS PHOENIX MUMBAI"
    elif e.narration_builder.startswith("UPI_UBER"):
        nar = f"UPI-UBER-uber@axisbank-AXISBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("UPI_OLA"):
        nar = f"UPI-OLA-ola@ybl-PAYTMBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("UPI_RAP"):
        nar = f"UPI-RAPIDO-rapido@ibl-HDFCBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("POS_IOCL"):
        nar = f"POS {rng.randint(100000,999999)} INDIAN OIL VILE PARLE MUMBAI"
    elif e.narration_builder.startswith("POS_HP"):
        nar = f"POS {rng.randint(100000,999999)} HP PETROL CHEMBUR MUMBAI"
    elif e.narration_builder.startswith("POS_BP"):
        nar = f"POS {rng.randint(100000,999999)} BHARAT PETROLEUM MUMBAI"
    elif e.narration_builder.startswith("UPI_AMZ"):
        nar = f"UPI-AMAZON PAY-amazonpay@icici-ICICIBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("POS_FLIP"):
        nar = f"POS {rng.randint(100000,999999)} FLIPKART PAYMENTS MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("ECOM_MYN"):
        nar = f"ECOM MYNTRA.COM CARD XXXX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("UPI_BB"):
        nar = f"UPI-BIGBASKET-bigbasket@ybl-PAYTMBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("POS_DMART"):
        nar = f"POS {rng.randint(100000,999999)} DMART POWAI MUMBAI"
    elif e.narration_builder.startswith("POS_REL"):
        nar = f"POS {rng.randint(100000,999999)} RELIANCE FRESH GHATKOPAR MUMBAI"
    elif e.narration_builder.startswith("BBPS_ELEC"):
        nar = f"BBPS/ELECTRICITY/ADANI ELECTRICITY MUMBAI/{ref[-8:]}"
    elif e.narration_builder.startswith("BBPS_TP"):
        nar = f"BBPS/ELECTRICITY/TATA POWER MUMBAI/{ref[-8:]}"
    elif e.narration_builder.startswith("UPI_JIO"):
        nar = f"UPI-JIO-jio@paytm-PAYTMBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("UPI_AIRTEL"):
        nar = f"UPI-AIRTEL-airtel@ybl-YESBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("UPI_VI"):
        nar = f"UPI-VI-vi@ibl-HDFCBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("BBPS_ACT"):
        nar = f"BBPS/BROADBAND/ACT FIBERNET/{ref[-8:]}"
    elif e.narration_builder.startswith("UPI_BMS"):
        nar = f"UPI-BOOKMYSHOW-bms@icici-ICICIBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("POS_PVR"):
        nar = f"POS {rng.randint(100000,999999)} PVR CINEMAS MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_INOX"):
        nar = f"POS {rng.randint(100000,999999)} INOX R CITY MUMBAI"
    elif e.narration_builder.startswith("POS_APOLLO"):
        nar = f"POS {rng.randint(100000,999999)} APOLLO PHARMACY BANDRA MUMBAI"
    elif e.narration_builder.startswith("UPI_NETMEDS"):
        nar = f"UPI-NETMEDS-netmeds@ybl-PAYTMBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("UPI_PE"):
        nar = f"UPI-PHARMEASY-pharmeasy@ibl-HDFCBANK-{ref[-9:]}"
    elif e.narration_builder.startswith("POS_FORTIS"):
        nar = f"POS {rng.randint(100000,999999)} FORTIS HOSPITAL MULUND MUMBAI"
    else:
        nar = f"UPI-MISC-misc@ybl-PAYTMBANK-{ref[-9:]}"
    vd = e.d.strftime("%d/%m/%y")
    if e.kind == "debit":
        return (vd, nar, ref, vd, f"{e.amount:.2f}", "")
    return (vd, nar, ref, vd, "", f"{e.amount:.2f}")


def apply_balances_hdfc(rows: list[tuple[str, str, str, str, str, str]]) -> list[list[str]]:
    """rows: (date, nar, ref, vd, w, d) before balance — w or d empty string when unused."""
    bal = 50000.0
    out = []
    for date_s, nar, ref, vd, w, d in rows:
        wv = float(w) if w else 0.0
        dv = float(d) if d else 0.0
        if wv:
            bal -= wv
        if dv:
            bal += dv
        out.append([date_s, nar, ref, vd, w, d, f"{bal:.2f}"])
    return out


def write_hdfc(path: Path, rng: random.Random):
    events = build_event_list(rng, "hdfc")
    events.sort(key=lambda e: e.d)
    refn = 100000001
    raw = []
    for e in events:
        ref = f"N{refn}"
        refn += 1
        vd, nar, ref, vds, w, d = fmt_hdfc(e, ref, rng)
        raw.append((vd, nar, ref, vds, w, d))
    bal_rows = apply_balances_hdfc(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
        w.writerows(bal_rows)


# --- SBI ---

def fmt_sbi(e: RawTxn, ref: str, rng: random.Random) -> tuple[str, str, str, str, str, str]:
    dstr = e.d.strftime("%d %b %Y").upper().replace(" 0", " ")  # "01 NOV 2025"
    if dstr[0] == " ":
        dstr = e.d.strftime("%d %b %Y").upper()
    # pandas %b is locale — use manual
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    dstr = f"{e.d.day:02d} {months[e.d.month - 1]} {e.d.year}"
    ml = e.extra.get("ml", "MAR26") if e.extra else "MAR26"
    if e.narration_builder == "SALARY":
        desc = f"NEFT CR-HDFC0001234-ABC COMPANY LTD-SALARY-{ref}"
    elif e.narration_builder == "RENT":
        desc = f"NEFT DR-ICIC0005678-LANDLORD RENT-{ref}"
    elif e.narration_builder == "INET":
        desc = "BBPS/BROADBAND/ACT FIBERNET/REF" + ref[-6:]
    elif e.narration_builder == "ELEC":
        desc = "BBPS/ELECTRICITY/ADANI ELECTRICITY MUMBAI/REF" + ref[-6:]
    elif e.narration_builder == "NFLX":
        desc = "UPI/998877665544/NETFLIX/netflix@icici/Subscription"
    elif e.narration_builder == "SPOT":
        desc = "UPI/887766554433/SPOTIFY/spotify@ybl/Music"
    elif e.narration_builder == "PRIME":
        desc = "UPI/776655443322/AMAZON PAY/amazonpay@icici/Prime"
    elif e.narration_builder == "HOT":
        desc = "UPI/665544332211/HOTSTAR/hotstar@paytm/Video"
    elif e.narration_builder == "ANOM_CRYPTO":
        desc = "UPI/112233445566/CRYPTOX EXCHANGE DUBAI/cryptox@ybl/Payment"
    elif e.narration_builder == "ANOM_BINANCE":
        desc = "UPI/223344556677/BINANCE INT/binance@ibl/Payment"
    elif e.narration_builder == "ANOM_SUNDAY_NEFT":
        desc = f"NEFT DR-HDFC0099887-SUSP BENEFICIARY-SUN-{ref}"
    elif e.narration_builder == "ANOM_XYZ":
        desc = "UPI/334455667788/XYZ TRADING LTD/xyztrd@okaxis/Payment"
    elif e.narration_builder == "ANOM_ROUND":
        desc = "NEFT DR-ICIC0002211-ROUND TEST BENEFICIARY-N998877"
    elif e.narration_builder in ("ANOM_DUP1", "ANOM_DUP2"):
        desc = f"POS PURCHASE DUPLICATE MERCHANT MUMBAI {ref[-6:]}"
    elif e.narration_builder == "ANOM_WIRE":
        desc = "NEFT DR-SBIN0099001-OFFSHORE TEST REMIT-N665544"
    elif e.narration_builder in ("ANOM_PROBE", "ANOM_PROBE2"):
        desc = "UPI/445566778899/VERIFY/probe@ybl/Test"
    elif e.narration_builder == "ANOM_GIFT":
        desc = "UPI/556677889900/LARGE GIFT/lrgift@paytm/Payment"
    elif e.narration_builder == "ANOM_CASHOUT":
        desc = "ATM CASH WITHDRAWAL SBI0001234 ANDHERI"
    elif e.narration_builder == "ANOM_FOREX":
        desc = "POS PURCHASE FOREX LOAD SINGAPORE 887766"
    elif e.narration_builder == "ANOM_BURST":
        i = e.extra.get("i", 0) if e.extra else 0
        desc = f"UPI/66778899001{i}/SWIGGY/swiggy@payt/Food Order"
    elif "SW" in e.narration_builder or "ZO" in e.narration_builder:
        mer = "SWIGGY" if "SW" in e.narration_builder else "ZOMATO"
        vpa = "swiggy@payt" if mer == "SWIGGY" else "zomato@ybl"
        desc = f"UPI/{ref[-12:]}/{mer}/{vpa}/Payment"
    elif e.narration_builder.startswith("POS_") or e.narration_builder.startswith("ECOM"):
        desc = f"POS PURCHASE {e.narration_builder.replace('_', ' ')} MUMBAI {ref[-6:]}"
    elif e.narration_builder.startswith("BBPS") or e.narration_builder.startswith("UPI_JIO"):
        desc = f"BBPS/MOBILE/JIO PREPAID/REF{ref[-6:]}"
    elif e.narration_builder.startswith("UPI_AIRTEL"):
        desc = f"UPI/{ref[-12:]}/Phonepe/Airtel Recharge"
    elif e.narration_builder.startswith("UPI_VI"):
        desc = f"UPI/{ref[-12:]}/VI/vi@ibl/Recharge"
    elif e.narration_builder.startswith("UPI_UBER"):
        desc = f"UPI/{ref[-12:]}/UBER/uber@axis/Ride"
    elif e.narration_builder.startswith("UPI_OLA"):
        desc = f"UPI/{ref[-12:]}/OLA/ola@ybl/Ride"
    elif e.narration_builder.startswith("UPI_RAP"):
        desc = f"UPI/{ref[-12:]}/RAPIDO/rapido@ibl/Ride"
    else:
        desc = f"UPI/{ref[-12:]}/MERCHANT/merch@ybl/Payment"
    if e.kind == "debit":
        return (dstr, dstr, desc, ref, f"{e.amount:.2f}", "")
    return (dstr, dstr, desc, ref, "", f"{e.amount:.2f}")


def write_sbi(path: Path, rng: random.Random):
    events = build_event_list(rng, "sbi")
    events.sort(key=lambda e: e.d)
    refn = 200000001
    rows = []
    bal = 45000.0
    for e in events:
        ref = str(refn)
        refn += 1
        td, vd, desc, r, deb, cred = fmt_sbi(e, ref, rng)
        debf = float(deb) if deb else 0.0
        crf = float(cred) if cred else 0.0
        if debf:
            bal -= debf
        if crf:
            bal += crf
        rows.append([td, vd, desc, r, deb, cred, f"{bal:.2f}"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Txn Date", "Value Date", "Description", "Ref No./Cheque No.", "Debit", "Credit", "Balance"])
        w.writerows(rows)


# --- ICICI ---

def fmt_icici(e: RawTxn, ref: str, rng: random.Random) -> tuple[str, str, str, str, str, str]:
    ds = e.d.strftime("%d-%m-%Y")
    ml = e.extra.get("ml", "MAR26") if e.extra else "MAR26"
    if e.narration_builder == "SALARY":
        desc = f"NEFT CR ABC TECHNOLOGIES PVT LTD SALARY {ml}"
    elif e.narration_builder == "RENT":
        desc = f"NEFT DR-SBIN0012345-KUMAR-RENT {ml}-N{ref[-9:]}"
    elif e.narration_builder == "INET":
        desc = "UPI/DR/887766554433/ACT FIBERNET/act@axis/Internet"
    elif e.narration_builder == "ELEC":
        desc = "UPI/DR/776655443322/ADANI ELECTRICITY/adani@ybl/Bill"
    elif e.narration_builder == "NFLX":
        desc = "UPI/DR/665544332211/NETFLIX/netflix@icici/OTT"
    elif e.narration_builder == "SPOT":
        desc = "UPI/DR/554433221100/SPOTIFY/spotify@paytm/Music"
    elif e.narration_builder == "PRIME":
        desc = "UPI/DR/443322110099/AMAZON PAY/amazonpay@icici/Prime"
    elif e.narration_builder == "HOT":
        desc = "UPI/DR/332211009988/HOTSTAR/hotstar@paytm/Video"
    elif e.narration_builder == "ANOM_CRYPTO":
        desc = "UPI/DR/221100998877/CRYPTOX EXCHANGE DUBAI/cryptox@ybl/Payment"
    elif e.narration_builder == "ANOM_BINANCE":
        desc = "UPI/DR/110099887766/BINANCE INT/binance@ibl/Payment"
    elif e.narration_builder == "ANOM_SUNDAY_NEFT":
        desc = f"NEFT DR-HDFC0099887-SUN LARGE-N{ref[-9:]}"
    elif e.narration_builder == "ANOM_XYZ":
        desc = "UPI/DR/009988776655/XYZ TRADING LTD/xyztrd@okaxis/Payment"
    elif e.narration_builder == "ANOM_ROUND":
        desc = "NEFT DR ICICI ROUND TEST N888777666"
    elif e.narration_builder in ("ANOM_DUP1", "ANOM_DUP2"):
        desc = f"POS 556677 MCDONALDS ANDHERI W MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder == "ANOM_WIRE":
        desc = "IMPS-OUT-998877665544-OFFSHORE TEST-HDFC"
    elif e.narration_builder in ("ANOM_PROBE", "ANOM_PROBE2"):
        desc = "UPI/DR/887766554433/VERIFY/probe@ybl/Test"
    elif e.narration_builder == "ANOM_GIFT":
        desc = "UPI/DR/776655443322/LARGE GIFT/lrgift@paytm/Payment"
    elif e.narration_builder == "ANOM_CASHOUT":
        desc = "ATM WDL ICICI ATM BANDRA MUMBAI 789012"
    elif e.narration_builder == "ANOM_FOREX":
        desc = "POS 445566 FOREX LOAD SINGAPORE MUMBAI CARD XX2233"
    elif e.narration_builder == "ANOM_BURST":
        i = e.extra.get("i", 0) if e.extra else 0
        desc = f"UPI/DR/1234567890{i:02d}/SWIGGY/swiggy@ybl/Food"
    elif "SW" in e.narration_builder or "ZO" in e.narration_builder:
        mer = "SWIGGY" if "SW" in e.narration_builder else "ZOMATO"
        vpa = "swiggy@ybl" if mer == "SWIGGY" else "zomato@paytm"
        desc = f"UPI/DR/{ref[-12:]}/{mer}/{vpa}/Food"
    elif e.narration_builder.startswith("ECOM"):
        desc = f"ECOM AMAZON.IN CARD XXXX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_DMART"):
        desc = f"POS {rng.randint(100000,999999)} DMART POWAI MUMBAI CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("ATM"):
        desc = "ATM WDL ICICI ATM ANDHERI MUMBAI 445566"
    elif e.narration_builder.startswith("UPI_"):
        tail = e.narration_builder.split("_", 1)[-1]
        desc = f"UPI/DR/{ref[-12:]}/{tail}/merch@ybl/Payment"
    else:
        desc = f"POS {rng.randint(100000,999999)} RELIANCE FRESH MUMBAI CARD XX{rng.randint(1000,9999)}"
    chq = "" if "NEFT" not in desc and "IMPS" not in desc else ref[-10:]
    if e.kind == "debit":
        return (ds, ds, desc, chq, f"{e.amount:.2f}", "")
    return (ds, ds, desc, chq, "", f"{e.amount:.2f}")


def write_icici(path: Path, rng: random.Random):
    events = build_event_list(rng, "icici")
    events.sort(key=lambda e: e.d)
    refn = 300000001
    rows = []
    bal = 62000.0
    for e in events:
        ref = str(refn)
        refn += 1
        parts = fmt_icici(e, ref, rng)
        td, vd, desc, chq, w, d = parts
        wf = float(w) if w else 0.0
        df = float(d) if d else 0.0
        if wf:
            bal -= wf
        if df:
            bal += df
        rows.append([td, vd, desc, chq, w, d, f"{bal:.2f}"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Transaction Date",
                "Value Date",
                "Description",
                "Cheque Number",
                "Withdrawal Amount (INR)",
                "Deposit Amount (INR)",
                "Available Balance (INR)",
            ]
        )
        w.writerows(rows)


# --- Axis ---

def fmt_axis(e: RawTxn, ref: str, rng: random.Random) -> tuple[str, str, str, str, str, str]:
    ds = e.d.strftime("%d-%m-%Y")
    ml = e.extra.get("ml", "MAR26") if e.extra else "MAR26"
    if e.narration_builder == "SALARY":
        part = f"NEFT INWARD-ABC COMPANY-SALARY {ml}-N{ref[-6:]}"
    elif e.narration_builder == "RENT":
        part = f"NEFT OUTWARD-LANDLORD-RENT-N{ref[-6:]}"
    elif e.narration_builder == "INET":
        part = "BBPS-ACT FIBERNET-INTERNET-REF" + ref[-6:]
    elif e.narration_builder == "ELEC":
        part = "BBPS-TATA POWER-BILL PAYMENT-REF" + ref[-6:]
    elif e.narration_builder == "NFLX":
        part = "UPI-NETFLIX-UPI/998877665544/NETFLIX/Payment"
    elif e.narration_builder == "SPOT":
        part = "UPI-SPOTIFY-UPI/887766554433/Music/Payment"
    elif e.narration_builder == "PRIME":
        part = "UPI-PHONEPE-AMAZON PRIME 299"
    elif e.narration_builder == "HOT":
        part = "UPI-PAYTM-HOTSTAR 299"
    elif e.narration_builder == "ANOM_CRYPTO":
        part = "UPI-CRYPTOX-UPI/112233445566/Payment"
    elif e.narration_builder == "ANOM_BINANCE":
        part = "UPI-BINANCE-UPI/223344556677/Payment"
    elif e.narration_builder == "ANOM_SUNDAY_NEFT":
        part = f"NEFT OUTWARD-SUN LARGE-N{ref[-6:]}"
    elif e.narration_builder == "ANOM_XYZ":
        part = "UPI-XYZ TRADING-UPI/334455667788/Payment"
    elif e.narration_builder == "ANOM_ROUND":
        part = "NEFT OUTWARD-ROUND TEST-N888777"
    elif e.narration_builder in ("ANOM_DUP1", "ANOM_DUP2"):
        part = f"ECOM FLIPKART.COM CARD XXXX1234 TXN{ref[-6:]}"
    elif e.narration_builder == "ANOM_WIRE":
        part = "NEFT OUTWARD-OFFSHORE TEST-N665544"
    elif e.narration_builder in ("ANOM_PROBE", "ANOM_PROBE2"):
        part = "UPI-PHONEPE-VERIFY 1"
    elif e.narration_builder == "ANOM_GIFT":
        part = "UPI-PAYTM-LARGE GIFT 62000"
    elif e.narration_builder == "ANOM_CASHOUT":
        part = "ATM WDL AXIS BANK ATM ANDHERI"
    elif e.narration_builder == "ANOM_FOREX":
        part = "ECOM FOREX LOAD SINGAPORE CARD XXXX2233"
    elif e.narration_builder == "ANOM_BURST":
        i = e.extra.get("i", 0) if e.extra else 0
        part = f"UPI-SWIGGY-UPI/66778899{i:02d}/SWIGGY/Payment"
    elif "SW" in e.narration_builder:
        part = f"UPI-SWIGGY-UPI/{ref[-9:]}/SWIGGY/Payment"
    elif "ZO" in e.narration_builder:
        part = f"UPI-ZOMATO-UPI/{ref[-9:]}/Food Order"
    elif e.narration_builder.startswith("UPI_PHONEPE_JIO"):
        part = "UPI-PHONEPE-JIO RECHARGE 399"
    elif e.narration_builder.startswith("UPI_JIO"):
        part = "UPI-PHONEPE-JIO RECHARGE 399"
    elif e.narration_builder.startswith("UPI_AIRTEL"):
        part = "UPI-PAYTM-AIRTEL RECHARGE 799"
    elif e.narration_builder.startswith("ECOM"):
        part = f"ECOM AMAZON.IN CARD XXXX1234 TXN{rng.randint(100000,999999)}"
    elif e.narration_builder.startswith("POS_DMART"):
        part = f"POS DMART POWAI MUMBAI CARD XX{rng.randint(1000,9999)}"
    else:
        part = f"UPI-PHONEPE-MERCHANT {ref[-6:]}"
    if e.kind == "debit":
        return (ds, part, ref, ds, f"{e.amount:.2f}", "")
    return (ds, part, ref, ds, "", f"{e.amount:.2f}")


def write_axis(path: Path, rng: random.Random):
    events = build_event_list(rng, "axis")
    events.sort(key=lambda e: e.d)
    refn = 400000001
    rows = []
    bal = 58000.0
    for e in events:
        ref = str(refn)
        refn += 1
        td, part, r, vd, w, d = fmt_axis(e, ref, rng)
        wf = float(w) if w else 0.0
        df = float(d) if d else 0.0
        if wf:
            bal -= wf
        if df:
            bal += df
        rows.append([td, part, r, vd, w, d, f"{bal:.2f}"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Tran Date", "Particulars", "Chq/Ref Number", "Value Date", "Withdrawal", "Deposit", "Closing Balance"])
        w.writerows(rows)


# --- Kotak ---

def fmt_kotak(e: RawTxn, ref: str, rng: random.Random) -> tuple[str, str, str, str, str]:
    ds = e.d.strftime("%d/%m/%Y")
    ml = e.extra.get("ml", "MAR26") if e.extra else "MAR26"
    if e.narration_builder == "SALARY":
        desc = f"NEFT CR ABC COMPANY LTD SALARY {ml} N{ref[-6:]}"
    elif e.narration_builder == "RENT":
        desc = f"NEFT DR TO LANDLORD RENT {ml} N{ref[-6:]}"
    elif e.narration_builder == "INET":
        desc = "BILL PAYMENT ACT FIBERNET REF" + ref[-6:]
    elif e.narration_builder == "ELEC":
        desc = "BILL PAYMENT ADANI ELECTRICITY MUMBAI REF" + ref[-6:]
    elif e.narration_builder == "NFLX":
        desc = "UPI P2M NETFLIX NETFLIX@ICICI " + ref[-12:]
    elif e.narration_builder == "SPOT":
        desc = "UPI P2M SPOTIFY SPOTIFY@YBL " + ref[-12:]
    elif e.narration_builder == "PRIME":
        desc = "UPI P2M AMAZON PAY AMAZONPAY@ICICI " + ref[-12:]
    elif e.narration_builder == "HOT":
        desc = "UPI P2M HOTSTAR HOTSTAR@PAYTM " + ref[-12:]
    elif e.narration_builder == "ANOM_CRYPTO":
        desc = "UPI P2M CRYPTOX EXCHANGE DUBAI CRYPTOX@YBL " + ref[-12:]
    elif e.narration_builder == "ANOM_BINANCE":
        desc = "UPI P2M BINANCE INT BINANCE@IBL " + ref[-12:]
    elif e.narration_builder == "ANOM_SUNDAY_NEFT":
        desc = f"NEFT DR SUNDAY LARGE TXN N{ref[-6:]}"
    elif e.narration_builder == "ANOM_XYZ":
        desc = "UPI P2M XYZ TRADING LTD XYZTRD@OKAXIS " + ref[-12:]
    elif e.narration_builder == "ANOM_ROUND":
        desc = "NEFT DR ROUND FIGURE TEST N888777"
    elif e.narration_builder in ("ANOM_DUP1", "ANOM_DUP2"):
        desc = f"PURCHASE AT DUPLICATE MERCHANT ON {e.d.strftime('%d-%m-%y')} CARD XX1234"
    elif e.narration_builder == "ANOM_WIRE":
        desc = "FT TO OFFSHORE TEST IMPS " + ref[-9:]
    elif e.narration_builder in ("ANOM_PROBE", "ANOM_PROBE2"):
        desc = "UPI P2M VERIFY PROBE@YBL " + ref[-12:]
    elif e.narration_builder == "ANOM_GIFT":
        desc = "UPI P2M LARGE GIFT LRGIFT@PAYTM " + ref[-12:]
    elif e.narration_builder == "ANOM_CASHOUT":
        desc = "ATM CASH WDL AT KOTAK MAHINDRA BANK BANDRA"
    elif e.narration_builder == "ANOM_FOREX":
        desc = f"PURCHASE AT FOREX LOAD ON {e.d.strftime('%d-%m-%y')} CARD XX2233"
    elif e.narration_builder == "ANOM_BURST":
        i = e.extra.get("i", 0) if e.extra else 0
        desc = f"UPI P2M SWIGGY SWIGGY@PAYTM {ref[-12:]}BR{i:02d}"
    elif "SW" in e.narration_builder:
        desc = f"UPI P2M SWIGGY SWIGGY@PAYTM {ref[-12:]}"
    elif "ZO" in e.narration_builder:
        desc = f"UPI P2M ZOMATO ZOMATO@YBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_JIO"):
        desc = "BILL PAYMENT JIO PREPAID REF" + ref[-6:]
    elif e.narration_builder.startswith("UPI_UBER"):
        desc = f"UPI P2M UBER UBER@AXISBANK {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_OLA"):
        desc = f"UPI P2M OLA OLA@YBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_RAP"):
        desc = f"UPI P2M RAPIDO RAPIDO@IBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_AMZ"):
        desc = f"UPI P2M AMAZON PAY AMAZONPAY@ICICI {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_BB"):
        desc = f"UPI P2M BIGBASKET BIGBASKET@YBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_AIRTEL"):
        desc = f"UPI P2M AIRTEL AIRTEL@YBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_VI"):
        desc = f"UPI P2M VI VI@IBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_NETMEDS"):
        desc = f"UPI P2M NETMEDS NETMEDS@YBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_PE"):
        desc = f"UPI P2M PHARMEASY PHARMEASY@IBL {ref[-12:]}"
    elif e.narration_builder.startswith("UPI_BMS"):
        desc = f"UPI P2M BOOKMYSHOW BMS@ICICI {ref[-12:]}"
    elif e.narration_builder.startswith("BBPS_ELEC") or e.narration_builder.startswith("BBPS_TP"):
        desc = "BILL PAYMENT ADANI ELECTRICITY MUMBAI REF" + ref[-6:]
    elif e.narration_builder.startswith("BBPS_ACT"):
        desc = "BILL PAYMENT ACT FIBERNET REF" + ref[-6:]
    elif e.narration_builder.startswith("POS_IOCL"):
        desc = f"PURCHASE AT INDIAN OIL ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_HP"):
        desc = f"PURCHASE AT HP PETROL ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_BP"):
        desc = f"PURCHASE AT BHARAT PETROLEUM ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_FLIP"):
        desc = f"PURCHASE AT FLIPKART.COM ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("ECOM_MYN"):
        desc = f"PURCHASE AT MYNTRA.COM ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_DMART"):
        desc = f"PURCHASE AT DMART POWAI ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_REL"):
        desc = f"PURCHASE AT RELIANCE FRESH ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_DOM"):
        desc = f"PURCHASE AT DOMINOS ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_MCD"):
        desc = f"PURCHASE AT MCDONALDS ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_KFC"):
        desc = f"PURCHASE AT KFC ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_SB"):
        desc = f"PURCHASE AT STARBUCKS ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_CCD"):
        desc = f"PURCHASE AT CCD ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_HAL"):
        desc = f"PURCHASE AT HALDIRAMS ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_PVR"):
        desc = f"PURCHASE AT PVR CINEMAS ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_INOX"):
        desc = f"PURCHASE AT INOX ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_APOLLO"):
        desc = f"PURCHASE AT APOLLO PHARMACY ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS_FORTIS"):
        desc = f"PURCHASE AT FORTIS HOSPITAL ON {e.d.strftime('%d-%m-%y')} CARD XX{rng.randint(1000,9999)}"
    elif e.narration_builder.startswith("POS") or e.narration_builder.startswith("ECOM"):
        desc = f"PURCHASE AT AMAZON.IN ON {e.d.strftime('%d-%m-%y')}"
    else:
        desc = f"FT TO AMIT SHARMA IMPS {ref[-9:]}"
    if e.kind == "debit":
        return (ds, desc, ref, f"{e.amount:.2f}", "")
    return (ds, desc, ref, "", f"{e.amount:.2f}")


def write_kotak(path: Path, rng: random.Random):
    events = build_event_list(rng, "kotak")
    events.sort(key=lambda e: e.d)
    refn = 500000001
    rows = []
    bal = 48000.0
    for e in events:
        ref = str(refn)
        refn += 1
        ds, desc, r, deb, cred = fmt_kotak(e, ref, rng)
        wf = float(deb) if deb else 0.0
        df = float(cred) if cred else 0.0
        if wf:
            bal -= wf
        if df:
            bal += df
        rows.append([ds, desc, r, deb, cred, f"{bal:.2f}"])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Description", "Ref No.", "Debit", "Credit", "Balance"])
        w.writerows(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_hdfc(OUT_DIR / "hdfc_statement.csv", random.Random(101))
    write_sbi(OUT_DIR / "sbi_statement.csv", random.Random(102))
    write_icici(OUT_DIR / "icici_statement.csv", random.Random(103))
    write_axis(OUT_DIR / "axis_statement.csv", random.Random(104))
    # Fix axis JIO/Airtel patterns in daily pool - already mixed via random_daily
    write_kotak(OUT_DIR / "kotak_statement.csv", random.Random(105))
    for name in ["hdfc_statement.csv", "sbi_statement.csv", "icici_statement.csv", "axis_statement.csv", "kotak_statement.csv"]:
        p = OUT_DIR / name
        n = sum(1 for _ in p.open(encoding="utf-8")) - 1
        print(f"{name}: {n} data rows")


if __name__ == "__main__":
    main()
