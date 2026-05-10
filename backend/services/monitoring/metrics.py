"""Prometheus metrics registry for SmartSpend fraud detection.

Phase 5: MLOps.
Dependencies: prometheus-client.
Performance budget: metric observation is O(1), <0.1ms.

All metrics are defined as module-level singletons — prometheus_client
deduplicates on the default REGISTRY, so it is safe to import this module
multiple times.

Exposed at GET /metrics via generate_latest() in main.py.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ------------------------------------------------------------------ #
# Latency histograms
# ------------------------------------------------------------------ #

# End-to-end scoring latency split by internal layer.
# layer labels: rule | stat | unsup | sup | total
risk_layer_latency_ms = Histogram(
    "smartspend_risk_layer_latency_ms",
    "Latency (ms) of each scoring layer",
    labelnames=["layer"],
    buckets=[1, 5, 10, 25, 50, 100, 150, 250, 500, 1000],
)

# Feature store read latency.
# entity_type labels: user | merchant | device | ip
feature_store_read_latency_ms = Histogram(
    "smartspend_feature_store_read_latency_ms",
    "Redis feature store read latency (ms)",
    labelnames=["entity_type"],
    buckets=[0.5, 1, 2, 5, 10, 20, 50, 100],
)

# ------------------------------------------------------------------ #
# Score distribution
# ------------------------------------------------------------------ #

transaction_risk_score_histogram = Histogram(
    "smartspend_transaction_risk_score",
    "Distribution of composite risk scores (0-100)",
    labelnames=["model_version"],
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

# ------------------------------------------------------------------ #
# Action counters
# ------------------------------------------------------------------ #

transaction_action_total = Counter(
    "smartspend_transaction_action_total",
    "Number of transactions by decision action",
    labelnames=["action", "model_version"],
)

# ------------------------------------------------------------------ #
# Drift gauges
# ------------------------------------------------------------------ #

model_drift_psi = Gauge(
    "smartspend_model_drift_psi",
    "Population Stability Index (PSI) per feature (higher = more drift)",
    labelnames=["feature_name"],
)

model_drift_kl = Gauge(
    "smartspend_model_drift_kl",
    "KL divergence per feature",
    labelnames=["feature_name"],
)

# ------------------------------------------------------------------ #
# Shadow deployment metrics
# ------------------------------------------------------------------ #

shadow_score_delta_histogram = Histogram(
    "smartspend_shadow_score_delta",
    "Absolute difference (prod_score - shadow_score) in shadow deployments",
    buckets=[0, 5, 10, 15, 20, 30, 50, 100],
)

# ------------------------------------------------------------------ #
# Infrastructure counters
# ------------------------------------------------------------------ #

event_bus_published_total = Counter(
    "smartspend_event_bus_published_total",
    "Events published to Redis Streams",
    labelnames=["topic"],
)

event_bus_consumed_total = Counter(
    "smartspend_event_bus_consumed_total",
    "Events consumed from Redis Streams",
    labelnames=["topic", "status"],   # status: success | retry | dlq
)

feature_materializer_runs_total = Counter(
    "smartspend_feature_materializer_runs_total",
    "Feature materialization scheduler runs",
    labelnames=["status"],            # success | partial | failed
)
