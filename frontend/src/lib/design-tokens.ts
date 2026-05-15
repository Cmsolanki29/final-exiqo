/**
 * SmartSpend Design Tokens — Text Colors
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * THE ONE RULE: Purple is an ACCENT color. Purple is NEVER body text.
 *
 * ❌ NEVER purple for:
 *   - Paragraphs, descriptions, helper text, explainer copy
 *   - Form field labels, input placeholders
 *   - Subtitles under headings
 *   - Empty state messages
 *   - Captions, metadata, timestamps
 *   - Any multi-word phrase
 *
 * ✅ Purple is OK ONLY for:
 *   - Single-word or 1-3 word badges/pills
 *   - Active tab / selected menu item indicator
 *   - Single highlighted accent word inside white text
 *   - Hover/focus ring states (hover:text-violet-*)
 *   - Decorative gradient lines (from-purple-N, via-purple-N)
 *   - Brand logo / SmartSpend wordmark
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * HOW TO USE
 * ─────────────────────────────────────────────────────────────────────────────
 *
 *   import { text } from '../lib/design-tokens';
 *
 *   // ✅ Correct
 *   <p className={text.body}>Your financial health is excellent.</p>
 *   <span className={text.label}>TOTAL SPEND</span>
 *   <span className={text.accent}>PRO</span>   // badge — 1 word, ok
 *
 *   // ❌ Wrong
 *   <p className="text-purple-300">Your financial health is excellent.</p>
 *   <label className="text-violet-400">Card number</label>
 */

// ── Text hierarchy ─────────────────────────────────────────────────────────────
export const text = {
  /** Page titles, hero headings, key numbers — font-bold/semibold */
  heading: "text-white",

  /** Card titles, section headings — font-medium/semibold */
  title: "text-white",

  /** Main body paragraphs, descriptions, readable content */
  body: "text-gray-300",

  /** Subtitles, secondary info, supporting sentences */
  secondary: "text-gray-400",

  /** UPPERCASE labels, captions, metadata, timestamps */
  label: "text-gray-500",

  /** Input/textarea placeholders */
  placeholder: "text-gray-600",

  /** Disabled elements */
  disabled: "text-gray-700",

  // ── Semantic — for status / state (small numbers and pills only) ───────────
  success: "text-emerald-300",
  warning: "text-amber-300",
  danger: "text-rose-300",
  info: "text-cyan-300",

  // ── Accent — use SPARINGLY: single-word badges, active states, icon tints ──
  /** e.g. "PRO" badge, "LIVE" pill, "PREMIUM" tag */
  accent: "text-purple-300",
  accentSubtle: "text-purple-200",
} as const;

export type TextToken = keyof typeof text;

// ── Quick-reference mapping from legacy opacity-based exiqo-glow classes ──────
// Use this when migrating old `text-exiqo-glow/XX` patterns:
//
//   /80 – /100  →  text.body        (text-gray-300)
//   /60 – /75   →  text.secondary   (text-gray-400)
//   /40 – /55   →  text.label       (text-gray-500)
//   /20 – /35   →  text.placeholder (text-gray-600)
//
export const GLOW_MIGRATION_MAP: Record<string, string> = {
  "text-exiqo-glow":      "text-gray-300",
  "text-exiqo-glow/100":  "text-gray-300",
  "text-exiqo-glow/90":   "text-gray-300",
  "text-exiqo-glow/85":   "text-gray-300",
  "text-exiqo-glow/80":   "text-gray-300",
  "text-exiqo-glow/75":   "text-gray-400",
  "text-exiqo-glow/70":   "text-gray-400",
  "text-exiqo-glow/65":   "text-gray-400",
  "text-exiqo-glow/60":   "text-gray-400",
  "text-exiqo-glow/55":   "text-gray-500",
  "text-exiqo-glow/50":   "text-gray-500",
  "text-exiqo-glow/45":   "text-gray-500",
  "text-exiqo-glow/40":   "text-gray-500",
  "text-exiqo-glow/35":   "text-gray-600",
  "text-exiqo-glow/30":   "text-gray-600",
  "text-exiqo-glow/25":   "text-gray-600",
  "text-exiqo-glow/20":   "text-gray-600",
};

export default text;
