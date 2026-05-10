"""Feature-to-human-text translation templates for SHAP explanation drivers.

Phase 7: SHAP Explainability.
Dependencies: none (pure Python dict lookups).
Performance budget: humanize() is O(1) — effectively free.

Why a separate humanizer?
  SHAP gives us exact math (shap_value = contribution to prediction in log-odds
  space).  End users and fraud analysts need plain English:
    "User made 8 transactions in the last hour"  is more useful than
    "user_txn_count_1h = 8.00 (shap=+0.34)".
  The templates bridge that gap.  The fallback ensures 100% coverage even for
  features added after this module was written.

Template format:
  Values are the RAW feature values (not SHAP values), formatted with an
  f-string spec in curly braces.  Use:
    {value:.0f}   for integer-like floats
    {value:.1f}   for 1-decimal floats
    {value:.2f}   for precise floats
    {abs_shap:.3f} for the SHAP contribution magnitude
"""

from __future__ import annotations

# ------------------------------------------------------------------ #
# Templates: feature_name → format string using {value}, {abs_shap}
# At least 30 templates as specified in the Phase 7 spec.
# ------------------------------------------------------------------ #
FEATURE_TEMPLATES: dict[str, str] = {
    # ---- Transaction velocity (user entity) ---- #
    "user_txn_count_1h":          "User made {value:.0f} transaction(s) in the last hour",
    "user_txn_count_24h":         "User made {value:.0f} transaction(s) in the last 24 hours",
    "user_txn_count_7d":          "User made {value:.0f} transaction(s) in the last 7 days",
    "user_txn_count_30d":         "User made {value:.0f} transaction(s) in the last 30 days",
    "txn_count_1h":               "User made {value:.0f} transaction(s) in the last hour",
    "txn_count_24h":              "User made {value:.0f} transaction(s) in the last 24 hours",
    "txn_count_7d":               "User made {value:.0f} transaction(s) in the last 7 days",
    "txn_count_30d":              "User made {value:.0f} transaction(s) in the last 30 days",

    # ---- Spend amounts (user entity) ---- #
    "user_debit_sum_1h":          "User spent {value:.0f} in the last hour",
    "user_debit_sum_24h":         "User spent {value:.0f} in the last 24 hours",
    "user_debit_avg_30d":         "User's 30-day average spend is {value:.0f}",
    "user_debit_std_30d":         "User's 30-day spend std-dev is {value:.0f}",
    "user_debit_p95_30d":         "User's 95th-percentile spend (30d) is {value:.0f}",
    "debit_avg_30d":              "User's 30-day average spend is {value:.0f}",
    "debit_sum_1h":               "User spent {value:.0f} in the last hour",
    "debit_sum_24h":              "User spent {value:.0f} in the last 24 hours",

    # ---- Transaction-level computed features ---- #
    "txn_log_amount":             "Transaction log-scaled amount is {value:.2f}",
    "txn_amount_vs_user_avg_30d": "Amount is {value:.1f}× the user's 30-day average",
    "txn_amount_vs_user_avg":     "Amount is {value:.1f}× the user's average",
    "txn_is_new_merchant":        "Merchant is {'new (never seen before)' if value > 0.5 else 'known'}",
    "txn_is_night_txn":           "Transaction occurred {'at night' if value > 0.5 else 'during the day'}",
    "txn_hour_sin":               "Cyclical hour signal (sin) = {value:.2f}",
    "txn_hour_cos":               "Cyclical hour signal (cos) = {value:.2f}",
    "txn_velocity_inr_per_hour":  "Spend velocity is {value:.0f} per hour",
    "amt_ratio_30d":              "Amount is {value:.1f}× the user's 30-day average",
    "merchant_changed":           "{'Merchant changed from usual pattern' if value > 0.5 else 'Known merchant'}",

    # ---- Merchant features ---- #
    "merchant_avg_amount_30d":        "Merchant's average transaction is {value:.0f}",
    "merchant_unique_users_count_30d": "Merchant has {value:.0f} unique users in 30 days",
    "merchant_chargeback_rate_30d":    "Merchant chargeback rate is {value:.2%}",
    "merchant_total_txn_count_30d":    "Merchant processed {value:.0f} transactions in 30 days",

    # ---- Account / risk history ---- #
    "user_account_age_days":           "Account is {value:.0f} days old",
    "account_age_days":                "Account is {value:.0f} days old",
    "user_failed_txn_ratio_24h":       "Failed transaction ratio (24h) is {value:.0%}",
    "user_chargeback_count_lifetime":  "User has {value:.0f} lifetime chargeback(s)",
    "user_unique_merchants_7d":        "User visited {value:.0f} merchants in the last 7 days",
    "user_unique_merchants_30d":       "User visited {value:.0f} merchants in the last 30 days",

    # ---- Graph / network features (Phase 6) ---- #
    "user_graph_device_count_30d":        "User used {value:.0f} device(s) in the last 30 days",
    "user_graph_ip_count_7d":             "User connected from {value:.0f} IP address(es) in the last 7 days",
    "user_graph_max_device_user_count":   "Device shared with up to {value:.0f} other user(s)",
    "user_graph_max_ip_user_count":       "IP shared with up to {value:.0f} other user(s) in 24 hours",
    "user_graph_shortest_path_to_fraud":  (
        "Network distance to nearest fraud user: {value:.0f} hop(s)"
        " (–1 = no path found)"
    ),
    "user_graph_component_size":          "User is in a network cluster of ~{value:.0f} user(s)",
    "graph_device_count_30d":             "User used {value:.0f} device(s) in the last 30 days",
    "graph_max_device_user_count":        "Device shared with {value:.0f} other user(s)",
    "graph_component_size":               "Network cluster size: ~{value:.0f} user(s)",
    "graph_shortest_path_to_fraud":       "Network distance to fraud: {value:.0f} hop(s)",

    # ---- Weekend / time of day ---- #
    "user_weekend_txn_ratio_30d": "Weekend transaction ratio (30d) is {value:.0%}",
    "weekend_txn_ratio_30d":      "Weekend transaction ratio (30d) is {value:.0%}",
}


def humanize(feature_name: str, value: float, shap_value: float) -> str:
    """Convert a feature name + value into a human-readable explanation fragment.

    Looks up the feature in FEATURE_TEMPLATES.  If no template exists,
    falls back to a generic "<name>=<value>" string.

    Args:
        feature_name: Feature name as it appears in the SHAP explanation.
        value:        The raw feature value (not the SHAP value).
        shap_value:   The SHAP attribution (used only for abs_shap in templates).

    Returns:
        A human-readable string describing why this feature matters.
    """
    template = FEATURE_TEMPLATES.get(feature_name)
    if template is None:
        # Generic fallback — covers features added after this module
        return f"{feature_name}={value:.2f}"

    try:
        abs_shap = abs(shap_value)
        return template.format(value=value, abs_shap=abs_shap)
    except Exception:
        # Template format errors must never break scoring
        return f"{feature_name}={value:.2f}"
