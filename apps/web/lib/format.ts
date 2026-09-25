export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function pct100(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function signed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export const PHASE_LABEL: Record<string, string> = {
  collect: "Collecting risks",
  merge: "Merging",
  vote: "Voting",
  sealed: "Sealed",
};

export const STATUS_LABEL: Record<string, string> = {
  planning: "Planning",
  active: "Active",
  closed: "Closed",
};

export const BIAS_LABEL: Record<string, string> = {
  over_estimates_risk: "over-estimates risk",
  under_estimates_risk: "under-estimates risk",
  calibrated: "calibrated",
};

export const CONFIDENCE_LABEL: Record<string, string> = {
  overconfident: "overconfident",
  underconfident: "underconfident",
  calibrated: "calibrated",
};
