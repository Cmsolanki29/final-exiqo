/**
 * phaseConfig — canonical metadata for all 8 phases.
 * Used in TrustCenter PhaseCards and elsewhere.
 */

export const PHASES = [
  {
    id: 1,
    title: "Auto-Scoring Pipeline",
    subtitle: "ML scores every transaction < 50ms",
    icon: "Zap",
    color: "#3b82f6",
    bg: "#eff6ff",
    description:
      "Different from Fraud Shield's manual checker — this pipeline automatically scores 100% of transactions using ML the moment they occur. Redis Streams capture every event and feed all 8 downstream phases without you doing anything.",
    metrics: ["Auto-scored transactions", "Avg latency (ms)", "Queue depth"],
    adminOnly: false,
  },
  {
    id: 2,
    title: "Feature Store",
    subtitle: "200+ behavioural signals",
    icon: "Database",
    color: "#8b5cf6",
    bg: "#f5f3ff",
    description:
      "Online + offline feature store precomputes 200+ signals per user: velocity, merchant history, geolocation drift, and more.",
    metrics: ["Features computed", "Cache hit rate", "Staleness p99"],
    adminOnly: false,
  },
  {
    id: 3,
    title: "Supervised Learning",
    subtitle: "XGBoost trained on fraud labels",
    icon: "Brain",
    color: "#06b6d4",
    bg: "#ecfeff",
    description:
      "XGBoost classifier trained on analyst-labelled fraud patterns, continuously retrained as new labels arrive.",
    metrics: ["Model accuracy", "Precision", "Recall", "AUC-PR"],
    adminOnly: true,
  },
  {
    id: 4,
    title: "Decision Engine",
    subtitle: "Per-merchant risk policies",
    icon: "Settings2",
    color: "#f59e0b",
    bg: "#fffbeb",
    description:
      "Deterministic rule layer sits on top of the ML score to enforce merchant-level limits, KYC rules, and velocity caps.",
    metrics: ["Decisions/min", "Policy violations", "Override rate"],
    adminOnly: true,
  },
  {
    id: 5,
    title: "MLOps & Registry",
    subtitle: "Drift detection + auto-retrain",
    icon: "RefreshCw",
    color: "#10b981",
    bg: "#ecfdf5",
    description:
      "MLflow registry + APScheduler trigger weekly drift checks. Model is retrained automatically when PSI > threshold.",
    metrics: ["Drift score (PSI)", "Retrain frequency", "Shadow accuracy"],
    adminOnly: true,
  },
  {
    id: 6,
    title: "Graph Intelligence",
    subtitle: "Fraud ring detection",
    icon: "Network",
    color: "#ec4899",
    bg: "#fdf2f8",
    description:
      "Shared-device and shared-IP graph flags account clusters. A mule score propagates guilt-by-association.",
    metrics: ["Clusters found", "Ring members", "Mule score"],
    adminOnly: true,
  },
  {
    id: 7,
    title: "SHAP Explainability",
    subtitle: "Why was this flagged?",
    icon: "BarChart2",
    color: "#6366f1",
    bg: "#eef2ff",
    description:
      "SHAP values decompose each model decision into human-readable feature contributions. Analysts see exactly what drove the score.",
    metrics: ["Explanations generated", "Top feature", "Confidence"],
    adminOnly: false,
  },
  {
    id: 8,
    title: "Feedback Flywheel",
    subtitle: "Analyst labels → retraining",
    icon: "MessageSquare",
    color: "#f97316",
    bg: "#fff7ed",
    description:
      "Analyst dispute queue feeds confirmed fraud labels back into the supervised training pipeline, closing the loop.",
    metrics: ["Pending reviews", "Labels added", "Model improvement Δ"],
    adminOnly: false,
  },
];
