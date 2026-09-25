/** CSS-variable roles for charts. Values live in app/globals.css for light and dark. */
export const VIZ = {
  surface: "var(--viz-surface)",
  series1: "var(--viz-series-1)",
  series1Soft: "var(--viz-series-1-soft)",
  divergeNeg: "var(--viz-diverge-neg)",
  divergePos: "var(--viz-diverge-pos)",
  divergeMid: "var(--viz-diverge-mid)",
  grid: "var(--viz-grid)",
  text: "var(--viz-text)",
  text2: "var(--viz-text-2)",
} as const;

export const FONT = "11px ui-sans-serif, system-ui, sans-serif";

/** Linear scale helper for hand-rolled SVG charts. */
export function scale(domain: [number, number], range: [number, number]) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;
  return (v: number) => r0 + ((v - d0) / span) * (r1 - r0);
}

export function truncate(s: string, n = 14): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
