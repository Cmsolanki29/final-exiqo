"""Phase 12 — Multi-Model Orchestrator (LLM-as-Judge).

Wraps the existing :class:`services.hybrid_scorer.HybridScorer` and
:class:`services.decision_engine.DecisionEngine` to add:

1. **Tier labelling** — declares which model layers contributed to a
   decision (rules, XGBoost, GNN, DNN, LLM agent).  Pure observability
   when the orchestrator master switch is off.
2. **Selective escalation** — for high-risk or model-disagreement cases,
   synchronously invokes the Phase 9 LLM investigator.
3. **LLM-as-Judge** — a separate LLM call that cross-checks borderline
   decisions and may, with sufficient confidence, override the action.

Every orchestrated decision is persisted to ``orchestration_decisions``
for audit and analytics.
"""
