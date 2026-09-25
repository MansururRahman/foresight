"use client";

import { FONT, VIZ, scale } from "@/components/charts/chartTheme";
import type { TagCalibration } from "@/lib/types";

const W = 520;
const ROW = 26;
const PAD = { top: 8, right: 56, bottom: 24, left: 110 };

/** Diverging bars: positive bias = the team over-estimates risk for this tag; negative = under-estimates. */
export function TagBiasChart({ tags }: { tags: TagCalibration[] }) {
  if (tags.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        Per-tag calibration appears once a tag has 10 or more graded predictions.
      </div>
    );
  }
  const sorted = [...tags].sort((a, b) => Math.abs(b.bias) - Math.abs(a.bias));
  const maxAbs = Math.max(0.1, ...sorted.map((t) => Math.abs(t.bias)));
  const H = PAD.top + sorted.length * ROW + PAD.bottom;
  const x = scale([-maxAbs, maxAbs], [PAD.left, W - PAD.right]);
  const mid = x(0);

  return (
    <figure className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Bias by tag: positive over-estimates risk, negative under-estimates">
        <line x1={mid} x2={mid} y1={PAD.top} y2={H - PAD.bottom} stroke={VIZ.text2} strokeWidth={1} />
        {sorted.map((t, i) => {
          const yTop = PAD.top + i * ROW + 5;
          const x0 = Math.min(mid, x(t.bias));
          const w = Math.abs(x(t.bias) - mid);
          const positive = t.bias >= 0;
          const label = `${positive ? "+" : ""}${(t.bias * 100).toFixed(0)} pts`;
          return (
            <g key={t.tag}>
              <title>{`${t.tag}: predicted ${Math.round(t.mean_predicted * 100)}%, observed ${Math.round(t.observed * 100)}% over ${t.n} predictions${t.chronic ? ` (chronically ${t.chronic}-estimated)` : ""}`}</title>
              <text x={PAD.left - 8} y={yTop + 12} textAnchor="end" style={{ font: FONT, fill: VIZ.text }}>
                {t.tag}
              </text>
              <rect x={x0} y={yTop} width={Math.max(w, 1)} height={ROW - 10} rx={4} fill={positive ? VIZ.divergePos : VIZ.divergeNeg} />
              <text x={positive ? x(t.bias) + 6 : x(t.bias) - 6} y={yTop + 12} textAnchor={positive ? "start" : "end"} style={{ font: FONT, fill: VIZ.text2 }}>
                {label}
              </text>
            </g>
          );
        })}
        <text x={mid - 6} y={H - 6} textAnchor="end" style={{ font: FONT, fill: VIZ.text2 }}>
          ← under-estimates risk
        </text>
        <text x={mid + 6} y={H - 6} style={{ font: FONT, fill: VIZ.text2 }}>
          over-estimates risk →
        </text>
      </svg>
    </figure>
  );
}
