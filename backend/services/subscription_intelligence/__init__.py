"""Subscription Intelligence — verdict engine, substitutions, reminders (DB-backed)."""

from .verdict_engine import (
    detect_declining_subscriptions,
    detect_dormant_subscriptions,
    detect_thriving_subscriptions,
    detect_upgrade_opportunities_for_user,
    evaluate_subscription,
    generate_all_verdict_reports,
    persist_verdict,
)
from .substitution_detector import (
    detect_category_migrations,
    detect_substitutions,
    save_category_migration_insights,
)
from .reminder_scheduler import (
    apply_reminder_action,
    create_reminders_with_escalation,
    schedule_reminders_for_subscription,
    simulate_next_day,
    tick_due_reminders,
    validate_snooze_reason,
)
from .llm_paragraph import fetch_recommendation_paragraph

__all__ = [
    "evaluate_subscription",
    "persist_verdict",
    "detect_thriving_subscriptions",
    "detect_declining_subscriptions",
    "detect_dormant_subscriptions",
    "detect_upgrade_opportunities_for_user",
    "generate_all_verdict_reports",
    "detect_substitutions",
    "detect_category_migrations",
    "save_category_migration_insights",
    "schedule_reminders_for_subscription",
    "create_reminders_with_escalation",
    "validate_snooze_reason",
    "tick_due_reminders",
    "apply_reminder_action",
    "simulate_next_day",
    "fetch_recommendation_paragraph",
]
