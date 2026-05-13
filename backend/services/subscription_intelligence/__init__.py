"""Subscription Intelligence — verdict engine, substitutions, reminders (DB-backed)."""

from .verdict_engine import evaluate_subscription, persist_verdict
from .substitution_detector import detect_substitutions
from .reminder_scheduler import (
    apply_reminder_action,
    schedule_reminders_for_subscription,
    simulate_next_day,
    tick_due_reminders,
)
from .llm_paragraph import fetch_recommendation_paragraph

__all__ = [
    "evaluate_subscription",
    "persist_verdict",
    "detect_substitutions",
    "schedule_reminders_for_subscription",
    "tick_due_reminders",
    "apply_reminder_action",
    "simulate_next_day",
    "fetch_recommendation_paragraph",
]
