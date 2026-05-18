"""Tests for Axis-style deterministic statement parsing."""

from services.statement_line_parser import parse_axis_style_statement

SAMPLE = """
AXIS BANK - ACCOUNT STATEMENT
Statement Period: 01 May 2026 - 30 May 2026
Date Narration Credit (INR) Debit (INR)
01-May NEFT CR INFOSYS LTD PAYROLL MAY26 68450
05-May MSEDCL BILL AUTOPAY 1860
26-May MICRO AUTH APPLE.COM/BILL 1
28-May INTL POS META ADS IRELAND 4999
"""


def test_parse_axis_lines_includes_msedcl() -> None:
    rows = parse_axis_style_statement(SAMPLE)
    assert len(rows) >= 4
    msedcl = [r for r in rows if "MSEDCL" in r["description"].upper()]
    assert msedcl and float(msedcl[0]["amount"]) == 1860
    assert msedcl[0]["type"] == "debit"


def test_payroll_is_credit() -> None:
    rows = parse_axis_style_statement(SAMPLE)
    payroll = [r for r in rows if "PAYROLL" in r["description"].upper()]
    assert payroll and payroll[0]["type"] == "credit"
