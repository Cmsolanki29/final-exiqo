# Frontend Risk Engine Changes
**8-Phase Fraud Detection UI — by Chirag Solanki**

All changes are **purely additive**. No existing component was deleted or modified
beyond the targeted wiring steps listed below.

---

## New Files

### Foundation (Wave 1)
| File | Purpose |
|------|---------|
| `src/services/riskApi.js` | Axios API client for all Phase 1-8 backend endpoints |
| `src/contexts/RiskContext.jsx` | Global engine health provider (polls `/health` every 30s) |
| `src/utils/risk/trustScoreBand.js` | Maps 0-1000 score → grade/color/label |
| `src/utils/risk/riskTheme.js` | Maps action → color/bg/icon constants |
| `src/utils/risk/shapHelpers.js` | SHAP sort, normalize, top-N helpers |
| `src/utils/risk/formatters.js` | `fmtPercent`, `fmtScore`, `fmtCurrency`, `fmtRelativeTime` |
| `src/utils/risk/phaseConfig.js` | Canonical metadata for all 8 phases |
| `src/hooks/risk/useExplanation.js` | Fetches SHAP explanation for a transaction |
| `src/hooks/risk/useReviewQueue.js` | Fetches + manages admin review queue |
| `src/hooks/risk/useModels.js` | Fetches model registry + drift + shadow reports |
| `src/hooks/risk/useFeedbackStats.js` | Fetches user-level fraud feedback stats |

### Always-visible Components (Wave 2)
| File | Purpose |
|------|---------|
| `src/components/risk/RiskStatePlaceholder.jsx` | Skeleton/error/empty fallback for all risk UI |
| `src/components/risk/RiskProtectionBadge.jsx` | Animated shield badge in sidebar footer |
| `src/components/risk/RiskLiveTicker.jsx` | Live event ticker in TopBar (xl screens) |

### Per-transaction Components (Wave 3)
| File | Purpose |
|------|---------|
| `src/components/risk/RiskScoreChip.jsx` | Colored action pill in transaction rows |
| `src/components/risk/ShapExplanationBars.jsx` | Horizontal SHAP bar chart |
| `src/components/risk/RiskChallengeModal.jsx` | Slide-up modal: SHAP + Report Fraud action |

### Trust Center (Wave 4)
| File | Purpose |
|------|---------|
| `src/components/risk/PhaseCard.jsx` | Expandable card for each of the 8 phases |
| `src/components/risk/TrustScoreGauge.jsx` | Animated semi-circular trust score gauge |
| `src/pages/risk/TrustCenter.jsx` | Showpiece page with engine status, gauge, phase cards |

### Deep-dive Pages (Wave 5)
| File | Purpose |
|------|---------|
| `src/pages/risk/AIPerformance.jsx` | Model metrics, drift PSI gauge, shadow test, registry |
| `src/pages/risk/AlertsCenter.jsx` | Review queue, confirm/dismiss fraud, feedback stats |

---

## Modified Files

### `frontend/tailwind.config.js`
- Added `risk.*` color palette (`safe`, `review`, `challenge`, `block`, `neutral`, `info` + bg variants)
- Added `risk-pulse` and `risk-shimmer` animations/keyframes

### `frontend/src/index.css`
- Appended `@layer utilities { .risk-shimmer-bg, .risk-card, .risk-chip-* }` at end of file

### `frontend/src/index.js`
- Wrapped `<App />` with `<RiskProvider>` (outer = AuthProvider, inner = RiskProvider)

### `frontend/src/App.jsx`
- Added `lazy` + `Suspense` import
- Added lazy imports for `TrustCenter`, `AIPerformance`, `AlertsCenter`
- Added `trust-center`, `ai-performance`, `alerts-center` tab rendering blocks

### `frontend/src/components/Layout/Sidebar.jsx`
- Added `trust-center` nav item (ShieldCheck icon)
- Imported `RiskProtectionBadge` and rendered it above the Logout button

### `frontend/src/components/Layout/TopBar.jsx`
- Imported `RiskLiveTicker` and rendered it in a `hidden xl:flex` container

### `frontend/src/components/Transactions/TransactionTable.jsx`
- Imported `RiskScoreChip` and `RiskChallengeModal`
- `Risk` column now renders `<RiskScoreChip>` when `tx.risk_action` is present
- `<RiskChallengeModal>` mounted below `<section>` (Phase 7 SHAP on click)

---

## Graceful Degradation Strategy

- **Engine offline**: `RiskContext` sets `healthy=false` → all risk components show an "offline" pill
- **Missing endpoints**: `riskApi.js` stubs for unbuilt endpoints throw errors caught by hooks
- **No SHAP data**: `ShapExplanationBars` → `RiskStatePlaceholder` with "No SHAP data" message
- **Admin endpoints**: `AIPerformance` + `AlertsCenter` show `RiskStatePlaceholder error` variant
- **Trust score**: `TrustScoreGauge` renders an animated skeleton when `score=null`

---

## Navigation

New tabs added to `BASE_NAV`:
- `trust-center` → Trust Center (always visible)

Deep-dive sub-pages (linked from Trust Center cards):
- `ai-performance` → AI Performance
- `alerts-center` → Alerts Center
