export function verdictDisplayLabel(verdictKey?: string | null): string;

export function humanizeVerdictReason(
  text?: string | null,
  verdictKey?: string | null
): string;

export function formatUsage30d(hours: number): string | null;

export function humanizeMigration<T extends Record<string, unknown>>(m: T): T;

export function humanizeInsightType(type?: string | null): string;

export const VERDICT_BUCKETS_UI: Array<{
  key: string;
  title: string;
  hint: string;
  IconKey: string;
  accent: string;
}>;
