"""Feature catalog — authoritative list of all features with SQL source queries.

Phase 2: Online Feature Store.
Phase 6 additions: 6 graph features added to user entity.
                   Graph features have source_query=None because they are computed
                   by GraphFeatureService (multi-query BFS) rather than a single SQL.
                   The materializer handles them via a dedicated graph pass.

Dependencies: none (pure Python dataclasses).
Performance budget: catalog is imported once at startup; zero runtime cost.

Design decisions:
  - Each FeatureSpec carries its own SQL aggregation query so the materializer
    can run them without hardcoding SQL elsewhere.
  - entity_type mirrors the Redis key prefix: feat:{entity_type}:{entity_id}.
  - Features that require columns not yet in the schema (device_id, ip_address)
    had stub queries returning default_value.  Phase 6 migration adds those columns
    so the MVs and graph features are now data-backed.
  - window is informational only (documents the lookback); the SQL query encodes
    the actual time window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal


@dataclass(frozen=True)
class FeatureSpec:
    """Defines one feature: its name, source entity, default, and SQL derivation.

    Attributes:
        name:          Unique feature name (used as dict key in assembled vector).
        entity_type:   Which entity this feature describes.
        description:   Human-readable explanation.
        dtype:         Python type: float | int | bool | list | str.
        window:        Lookback window label (informational, e.g. "30d", "1h").
        default_value: Returned when entity not in store or query fails.
        source_query:  Callable(entity_id: str) → SQL string + params tuple.
                       Returns a tuple: (sql_text, params_tuple).
                       If None, feature is computed at assembly time (not materialised).
    """

    name: str
    entity_type: Literal["user", "device", "ip", "merchant", "card"]
    description: str
    dtype: type
    window: str
    default_value: Any
    source_query: Callable[[str], tuple[str, tuple]] | None = field(
        default=None, compare=False, hash=False
    )


# ------------------------------------------------------------------ #
# USER features
# ------------------------------------------------------------------ #

_USER_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        name="txn_count_1h",
        entity_type="user",
        description="Number of DEBIT transactions in the last 1 hour",
        dtype=int,
        window="1h",
        default_value=0,
        source_query=lambda uid: (
            "SELECT COUNT(*) FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '1 hour'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="txn_count_24h",
        entity_type="user",
        description="Number of DEBIT transactions in the last 24 hours",
        dtype=int,
        window="24h",
        default_value=0,
        source_query=lambda uid: (
            "SELECT COUNT(*) FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '24 hours'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="txn_count_7d",
        entity_type="user",
        description="Number of DEBIT transactions in the last 7 days",
        dtype=int,
        window="7d",
        default_value=0,
        source_query=lambda uid: (
            "SELECT COUNT(*) FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '7 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="txn_count_30d",
        entity_type="user",
        description="Number of DEBIT transactions in the last 30 days",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=lambda uid: (
            "SELECT COUNT(*) FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_sum_1h",
        entity_type="user",
        description="Total DEBIT amount in the last 1 hour (INR)",
        dtype=float,
        window="1h",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(SUM(amount), 0)::float FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '1 hour'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_sum_24h",
        entity_type="user",
        description="Total DEBIT amount in the last 24 hours (INR)",
        dtype=float,
        window="24h",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(SUM(amount), 0)::float FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '24 hours'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_sum_7d",
        entity_type="user",
        description="Total DEBIT amount in the last 7 days (INR)",
        dtype=float,
        window="7d",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(SUM(amount), 0)::float FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '7 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_sum_30d",
        entity_type="user",
        description="Total DEBIT amount in the last 30 days (INR)",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(SUM(amount), 0)::float FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_avg_30d",
        entity_type="user",
        description="Mean DEBIT transaction amount over last 30 days",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(AVG(amount), 0)::float FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_std_30d",
        entity_type="user",
        description="Standard deviation of DEBIT amounts over last 30 days",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(STDDEV(amount), 0)::float FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_p95_30d",
        entity_type="user",
        description="95th percentile DEBIT amount over last 30 days",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY amount), 0)::float "
            "FROM transactions WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="debit_median_30d",
        entity_type="user",
        description="Median DEBIT amount over last 30 days",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount), 0)::float "
            "FROM transactions WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="unique_merchants_7d",
        entity_type="user",
        description="Count of distinct merchants used in last 7 days",
        dtype=int,
        window="7d",
        default_value=0,
        source_query=lambda uid: (
            "SELECT COUNT(DISTINCT merchant) FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' AND merchant IS NOT NULL "
            "AND transaction_date >= NOW() - INTERVAL '7 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="unique_merchants_30d",
        entity_type="user",
        description="Count of distinct merchants used in last 30 days",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=lambda uid: (
            "SELECT COUNT(DISTINCT merchant) FROM transactions "
            "WHERE user_id = $1 AND type = 'DEBIT' AND merchant IS NOT NULL "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="account_age_days",
        entity_type="user",
        description="Days since user's first transaction in the system",
        dtype=float,
        window="all-time",
        default_value=0.0,
        source_query=lambda uid: (
            "SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(transaction_date))) / 86400, 0)::float "
            "FROM transactions WHERE user_id = $1",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="avg_hours_between_txns_30d",
        entity_type="user",
        description="Average inter-arrival time (hours) between DEBIT transactions over 30 days",
        dtype=float,
        window="30d",
        default_value=24.0,
        source_query=lambda uid: (
            """
            WITH ordered AS (
                SELECT transaction_date,
                       LAG(transaction_date) OVER (ORDER BY transaction_date) AS prev
                FROM transactions
                WHERE user_id = $1 AND type = 'DEBIT'
                  AND transaction_date >= NOW() - INTERVAL '30 days'
            )
            SELECT COALESCE(
                AVG(EXTRACT(EPOCH FROM (transaction_date - prev)) / 3600.0), 24.0
            )::float FROM ordered WHERE prev IS NOT NULL
            """,
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="most_common_hour_30d",
        entity_type="user",
        description="Hour of day (0-23) user transacts most frequently in last 30 days",
        dtype=int,
        window="30d",
        default_value=12,
        source_query=lambda uid: (
            "SELECT COALESCE(EXTRACT(HOUR FROM transaction_date)::int, 12) AS hr "
            "FROM transactions WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days' "
            "GROUP BY hr ORDER BY COUNT(*) DESC LIMIT 1",
            (int(uid),),
        ),
    ),
    FeatureSpec(
        name="weekend_txn_ratio_30d",
        entity_type="user",
        description="Fraction of DEBIT transactions on weekends over last 30 days",
        dtype=float,
        window="30d",
        default_value=0.3,
        source_query=lambda uid: (
            "SELECT COALESCE("
            "  SUM(CASE WHEN is_weekend THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0), 0.3"
            ") FROM transactions WHERE user_id = $1 AND type = 'DEBIT' "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (int(uid),),
        ),
    ),
    # Stub features — columns not yet in schema; Phase 6 will populate these
    FeatureSpec(
        name="unique_devices_30d",
        entity_type="user",
        description="Count of distinct device IDs used in last 30 days [Phase 6 activates]",
        dtype=int,
        window="30d",
        default_value=1,
        source_query=None,  # No device_id column yet
    ),
    FeatureSpec(
        name="unique_ips_7d",
        entity_type="user",
        description="Count of distinct IPs used in last 7 days [Phase 6 activates]",
        dtype=int,
        window="7d",
        default_value=1,
        source_query=None,
    ),
    FeatureSpec(
        name="failed_txn_ratio_24h",
        entity_type="user",
        description="Ratio of failed/declined transactions in last 24h [requires status column]",
        dtype=float,
        window="24h",
        default_value=0.0,
        source_query=None,
    ),
    FeatureSpec(
        name="chargeback_count_lifetime",
        entity_type="user",
        description="Total chargebacks/disputes filed by this user [Phase 8 activates]",
        dtype=int,
        window="all-time",
        default_value=0,
        source_query=None,
    ),
]

# ------------------------------------------------------------------ #
# MERCHANT features
# ------------------------------------------------------------------ #

_MERCHANT_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        name="merchant_txn_count_30d",
        entity_type="merchant",
        description="Total transactions at this merchant in last 30 days",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=lambda mid: (
            "SELECT COUNT(*) FROM transactions WHERE merchant = $1 "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (str(mid),),
        ),
    ),
    FeatureSpec(
        name="merchant_unique_users_30d",
        entity_type="merchant",
        description="Unique users who transacted at this merchant in last 30 days",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=lambda mid: (
            "SELECT COUNT(DISTINCT user_id) FROM transactions WHERE merchant = $1 "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (str(mid),),
        ),
    ),
    FeatureSpec(
        name="merchant_avg_amount_30d",
        entity_type="merchant",
        description="Average transaction amount at this merchant in last 30 days",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda mid: (
            "SELECT COALESCE(AVG(amount), 0)::float FROM transactions WHERE merchant = $1 "
            "AND type = 'DEBIT' AND transaction_date >= NOW() - INTERVAL '30 days'",
            (str(mid),),
        ),
    ),
    FeatureSpec(
        name="merchant_chargeback_rate_30d",
        entity_type="merchant",
        description="Fraction of merchant's transactions flagged as anomaly in last 30 days",
        dtype=float,
        window="30d",
        default_value=0.0,
        source_query=lambda mid: (
            "SELECT COALESCE("
            "  SUM(CASE WHEN anomaly_flag THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0), 0.0"
            ") FROM transactions WHERE merchant = $1 "
            "AND transaction_date >= NOW() - INTERVAL '30 days'",
            (str(mid),),
        ),
    ),
]

# ------------------------------------------------------------------ #
# DEVICE / IP features — stubs until Phase 6 adds columns
# ------------------------------------------------------------------ #

_DEVICE_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        name="device_unique_users_30d",
        entity_type="device",
        description="Unique users seen on this device in last 30 days [Phase 6]",
        dtype=int,
        window="30d",
        default_value=1,
        source_query=None,
    ),
    FeatureSpec(
        name="device_first_seen_days_ago",
        entity_type="device",
        description="Days since device was first seen [Phase 6]",
        dtype=float,
        window="all-time",
        default_value=30.0,
        source_query=None,
    ),
    FeatureSpec(
        name="device_txn_count_30d",
        entity_type="device",
        description="Total transactions from this device in last 30 days [Phase 6]",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=None,
    ),
]

_IP_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        name="ip_unique_users_24h",
        entity_type="ip",
        description="Unique users from this IP in last 24h [Phase 6]",
        dtype=int,
        window="24h",
        default_value=1,
        source_query=None,
    ),
    FeatureSpec(
        name="ip_unique_users_7d",
        entity_type="ip",
        description="Unique users from this IP in last 7 days [Phase 6]",
        dtype=int,
        window="7d",
        default_value=1,
        source_query=None,
    ),
    FeatureSpec(
        name="ip_is_known_proxy",
        entity_type="ip",
        description="Whether IP is a known proxy/VPN [external feed hookpoint]",
        dtype=bool,
        window="real-time",
        default_value=False,
        source_query=None,
    ),
]

# ------------------------------------------------------------------ #
# Phase 6: Graph features (user entity)
#
# source_query=None because these are computed by GraphFeatureService
# (multi-step BFS + materialized view joins) rather than a single SQL.
# The feature_materializer has a dedicated graph pass for these.
# ------------------------------------------------------------------ #

_GRAPH_FEATURES: list[FeatureSpec] = [
    FeatureSpec(
        name="graph_device_count_30d",
        entity_type="user",
        description="Distinct device IDs used by user in last 30 days [Phase 6]",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=None,
    ),
    FeatureSpec(
        name="graph_ip_count_7d",
        entity_type="user",
        description="Distinct IP addresses used by user in last 7 days [Phase 6]",
        dtype=int,
        window="7d",
        default_value=0,
        source_query=None,
    ),
    FeatureSpec(
        name="graph_max_device_user_count",
        entity_type="user",
        description="Max number of other users sharing any device with this user (mv_device_user_count) [Phase 6]",
        dtype=int,
        window="30d",
        default_value=0,
        source_query=None,
    ),
    FeatureSpec(
        name="graph_max_ip_user_count",
        entity_type="user",
        description="Max other users sharing any IP with this user in last 24h (mv_ip_user_count_24h) [Phase 6]",
        dtype=int,
        window="24h",
        default_value=0,
        source_query=None,
    ),
    FeatureSpec(
        name="graph_shortest_path_to_fraud",
        entity_type="user",
        description="Shortest hop distance to nearest confirmed-fraud user via shared merchants. -1=no path [Phase 6]",
        dtype=float,
        window="30d",
        default_value=-1.0,
        source_query=None,
    ),
    FeatureSpec(
        name="graph_component_size",
        entity_type="user",
        description="Approximate size of connected component within 2 merchant-sharing hops (capped at 100) [Phase 6]",
        dtype=int,
        window="30d",
        default_value=1,
        source_query=None,
    ),
]

# ------------------------------------------------------------------ #
# Unified catalog
# ------------------------------------------------------------------ #

FEATURE_CATALOG: list[FeatureSpec] = (
    _USER_FEATURES + _MERCHANT_FEATURES + _DEVICE_FEATURES + _IP_FEATURES + _GRAPH_FEATURES
)

# Lookup maps for O(1) access
CATALOG_BY_NAME: dict[str, FeatureSpec] = {f.name: f for f in FEATURE_CATALOG}
CATALOG_BY_ENTITY: dict[str, list[FeatureSpec]] = {}
for _spec in FEATURE_CATALOG:
    CATALOG_BY_ENTITY.setdefault(_spec.entity_type, []).append(_spec)

# Features that have real SQL queries (can be materialised)
MATERIALISABLE: list[FeatureSpec] = [f for f in FEATURE_CATALOG if f.source_query is not None]


def get_defaults(entity_type: str) -> dict[str, Any]:
    """Return a dict of {feature_name: default_value} for an entity type."""
    return {
        f.name: f.default_value
        for f in CATALOG_BY_ENTITY.get(entity_type, [])
    }
