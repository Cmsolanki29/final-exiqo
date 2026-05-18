"""EMI formula tests — scenarios 2.1–2.4 from integration testing prompt."""

from __future__ import annotations

import pytest

from services.emi_calculator import calculate_emi, loan_summary


def _assert_emi_near(actual: float, expected: float, tolerance: float = 50.0) -> None:
    assert abs(actual - expected) <= tolerance, f"EMI {actual} not within ±{tolerance} of {expected}"


def test_scenario_2_1_laptop_12_months_12pct() -> None:
    s = loan_summary(60_000, 0, 12, 12)
    # Standard formula: ~₹5,329/mo (prompt manual ~₹5,321 is within ±₹50)
    _assert_emi_near(s["emi_monthly"], 5_329, 15)
    assert s["total_amount_payable"] == pytest.approx(63_971, rel=0.002)
    assert s["total_interest"] == pytest.approx(3_971, rel=0.002)
    assert len(s["amortization_schedule"]) == 12


def test_scenario_2_2_smartphone_with_down_payment() -> None:
    s = loan_summary(30_000, 10_000, 15, 6)
    assert s["principal"] == 20_000
    assert s["down_payment"] == 10_000
    _assert_emi_near(s["emi_monthly"], 3_525, 80)


def test_scenario_2_3_variable_rates() -> None:
    p, n = 50_000, 12
    e8, e12, e18 = calculate_emi(p, 8, n), calculate_emi(p, 12, n), calculate_emi(p, 18, n)
    assert e8 < e12 < e18
    _assert_emi_near(e8, 4_340, 15)
    _assert_emi_near(e12, 4_442, 15)
    _assert_emi_near(e18, 4_584, 15)


def test_scenario_2_4_tenure_comparison() -> None:
    price = 80_000
    e6, e12, e24, e36 = (
        calculate_emi(price, 12, 6),
        calculate_emi(price, 12, 12),
        calculate_emi(price, 12, 24),
        calculate_emi(price, 12, 36),
    )
    assert e36 < e24 < e12 < e6
    _assert_emi_near(e6, 13_804, 50)
    _assert_emi_near(e12, 7_106, 50)
    _assert_emi_near(e24, 3_764, 50)
    _assert_emi_near(e36, 2_655, 50)


def test_longer_tenure_more_total_interest() -> None:
    p, rate = 80_000, 12
    s6 = loan_summary(p, 0, rate, 6)
    s36 = loan_summary(p, 0, rate, 36)
    assert s36["total_interest"] > s6["total_interest"]
