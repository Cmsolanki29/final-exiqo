"""Merchant-based auto-categorization for uploaded transactions."""

from __future__ import annotations

MERCHANT_CATEGORY_MAP: dict[str, str] = {
    "swiggy": "Food & Dining",
    "zomato": "Food & Dining",
    "blinkit": "Food & Dining",
    "bigbasket": "Food & Dining",
    "zepto": "Food & Dining",
    "mcdonald": "Food & Dining",
    "domino": "Food & Dining",
    "starbucks": "Food & Dining",
    "instamart": "Food & Dining",
    "dmart": "Food & Dining",
    "haldiram": "Food & Dining",
    "mtr": "Food & Dining",
    "uber": "Transportation",
    "ola": "Transportation",
    "rapido": "Transportation",
    "indigo": "Transportation",
    "makemytrip": "Transportation",
    "redbus": "Transportation",
    "bmtc": "Transportation",
    "metro rail": "Transportation",
    "namma metro": "Transportation",
    "irctc": "Transportation",
    "dunzo": "Food & Dining",
    "reliance smart": "Food & Dining",
    "amazon": "Shopping",
    "flipkart": "Shopping",
    "myntra": "Shopping",
    "ajio": "Shopping",
    "nykaa": "Shopping",
    "croma": "Shopping",
    "meesho": "Shopping",
    "jio": "Bills & Utilities",
    "airtel": "Bills & Utilities",
    "bescom": "Bills & Utilities",
    "tata power": "Bills & Utilities",
    "bsnl": "Bills & Utilities",
    "netflix": "Entertainment",
    "spotify": "Entertainment",
    "bookmyshow": "Entertainment",
    "pvr": "Entertainment",
    "hotstar": "Entertainment",
    "prime video": "Entertainment",
    "apollo": "Healthcare",
    "medplus": "Healthcare",
    "practo": "Healthcare",
    "1mg": "Healthcare",
    "netmeds": "Healthcare",
    "zerodha": "Finance & Investment",
    "groww": "Finance & Investment",
    "lic": "Finance & Investment",
    "cred": "Finance & Investment",
    "upstox": "Finance & Investment",
    "paytm": "Transfer",
    "phonepe": "Transfer",
    "google pay": "Transfer",
    "bhim": "Transfer",
}


def categorize_merchant(merchant: str) -> str:
    if not merchant or not str(merchant).strip():
        return "Others"
    m = str(merchant).lower().strip()
    for key, category in MERCHANT_CATEGORY_MAP.items():
        if key in m:
            return category
    return "Others"


def categorize_batch(merchants: list[str]) -> list[str]:
    return [categorize_merchant(m) for m in merchants]
