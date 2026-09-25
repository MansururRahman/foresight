"use client";

import { FONT, VIZ, scale } from "@/components/charts/chartTheme";
import type { Bin } from "@/lib/types";

const W = 320;
const H = 320;
const PAD = { top: 12, right: 12, bottom: 40, left: 44 };

/**
 * Reliability diagram: mean predicted probability (x) against observed frequency (y).
 * Dots sit on the diagonal when a forecaster is perfectly calibrated. Dot area scales with the
 * number of predictions in the bin; bins with too few samples are hollow and parked on the
 * baseline because their observed frequency is not shown.
 */
export function ReliabilityDiagram({ bins }: { bins: Bin[] }) {
  const total = bins.reduce((s, b) => s + b.n, 0);
  if (total === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        No graded predictions yet. Seal a session, close the project and grade the risks.
      </div>
    );
  }
  const x = scale([0, 1], [PAD.left, W - PAD.right]);
  const y = scale([0, 1], [H - PAD.bottom, PAD.top]);
  const maxN = Math.max(...bins.map((b) => b.n), 1);
  const radius = (n: number) => 4 + 10 * Math.sqrt(n / maxN);
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <figure className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full max-w-sm" role="img" aria-label="Reliability diagram: predicted probability against observed frequency">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(0)} x2={x(1)} y1={y(t)} y2={y(t)} stroke={VIZ.grid} strokeWidth={1} />
            <text x={PAD.left - 8} y={y(t) + 3} textAnchor="end" style={{ font: FONT, fill: VIZ.text2 }}>
              {Math.round(t * 100)}%
            </text>
            <text x={x(t)} y={H - PAD.bottom + 16} textAnchor="middle" style={{ font: FONT, fill: VIZ.text2 }}>
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        <line data-testid="diagonal" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke={VIZ.text2} strokeWidth={1} strokeDasharray="4 4" />
        <text x={(x(0) + x(1)) / 2} y={H - 6} textAnchor="middle" style={{ font: FONT, fill: VIZ.text }}>
          Predicted probability
        </text>
        <text transform={`translate(12 ${(y(0) + y(1)) / 2}) rotate(-90)`} textAnchor="middle" style={{ font: FONT, fill: VIZ.text }}>
          Observed frequency
        </text>
        {bins
          .filter((b) => b.n > 0 && b.mean_predicted !== null)
          .map((b) => {
            const cx = x(b.mean_predicted ?? 0);
            const cy = b.reliable && b.observed !== null ? y(b.observed) : y(0) + 14;
            const r = radius(b.n);
            const label = b.reliable
              ? `${b.range[0]}–${b.range[1]}%: predicted ${Math.round((b.mean_predicted ?? 0) * 100)}%, observed ${Math.round((b.observed ?? 0) * 100)}% (n=${b.n})`
              : `${b.range[0]}–${b.range[1]}%: n=${b.n}, too few to show observed frequency`;
            return (
              <g key={b.index} data-testid="bin-dot" data-reliable={b.reliable ? "true" : "false"}>
                <title>{label}</title>
                <circle cx={cx} cy={cy} r={r + 2} fill={VIZ.surface} />
                <circle cx={cx} cy={cy} r={r} fill={b.reliable ? VIZ.series1 : "none"} stroke={VIZ.series1} strokeWidth={2} />
              </g>
            );
          })}
      </svg>
      <figcaption className="mt-1 text-xs text-muted-foreground">
        Dot size = predictions in the bin. Hollow dots on the baseline have fewer than 5 samples. Above the diagonal means risks happened more often than predicted.
      </figcaption>
    </figure>
  );
}
