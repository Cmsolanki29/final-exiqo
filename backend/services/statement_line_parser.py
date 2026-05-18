"""
Deterministic parsers for Indian bank/CC statement text (Axis-style tables).

Used when PDF text matches ``DD-Mon narration amount`` rows — avoids LLM misses.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from services.categorizer import resolve_category

_MONTH_ABBR = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_CREDIT_HINTS = (
    "neft cr",
    "upi from",
    "reimbursement",
    "interest credit",
    "salary",
    "payroll",
    "credit interest",
    "int.pd",
)

_LINE_RE = re.compile(
    r"^(\d{1,2})-([A-Za-z]{3})\s+(.+?)\s+(\d+(?:\.\d{1,2})?)\s*$",
    re.IGNORECASE,
)

_PERIOD_RE = re.compile(
    r"statement\s+period\s*:\s*\d{1,2}\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)


def _statement_year_month(text: str) -> tuple[int, int]:
    m = _PERIOD_RE.search(text or "")
    if m:
        mon_name = m.group(1).lower()[:3]
        year = int(m.group(2))
        month = _MONTH_ABBR.get(mon_name, 5)
        return year, month
    return date.today().year, date.today().month


def _infer_type(narration: str) -> str:
    low = narration.lower()
    if any(h in low for h in _CREDIT_HINTS):
        return "credit"
    return "debit"


def parse_axis_style_statement(text: str) -> list[dict[str, Any]]:
    """
    Parse lines like ``05-May MSEDCL BILL AUTOPAY 1860`` from Axis sample statements.
    Returns monster-compatible dicts: date, description, amount, type, category.
    """
    if not text or "date narration" not in text.lower():
        return []

    year, default_month = _statement_year_month(text)
    out: list[dict[str, Any]] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        day_s, mon_abbr, narration, amt_s = m.groups()
        mon = _MONTH_ABBR.get(mon_abbr.lower()[:3])
        if not mon:
            mon = default_month
        try:
            d = date(year, mon, int(day_s))
        except ValueError:
            continue
        try:
            amount = float(amt_s)
        except ValueError:
            continue
        if amount <= 0:
            continue
        narr = narration.strip()
        txn_type = _infer_type(narr)
        category = resolve_category(narr, None)
        out.append(
            {
                "date": d.isoformat(),
                "description": narr,
                "amount": amount,
                "type": txn_type,
                "category": category,
            }
        )
    return out
