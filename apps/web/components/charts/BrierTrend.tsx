"use client";

import { FONT, VIZ, scale, truncate } from "@/components/charts/chartTheme";
import type { TrendPoint } from "@/lib/types";

const W = 520;
const H = 220;
const PAD = { top: 16, right: 56, bottom: 44, left: 40 };

/** Rolling Brier score per closed project (lower is better), with each project's own score as faint dots. */
export function BrierTrend({ points }: { points: TrendPoint[] }) {
  if (points.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        The trend appears once at least one project is closed and graded.
      </div>
    );
  }
  const values = points.flatMap((p) => [p.brier_project, ...(p.brier_rolling !== null ? [p.brier_rolling] : [])]);
  const yMax = Math.max(0.3, ...values) * 1.1;
  const x = scale([0, Math.max(points.length - 1, 1)], [PAD.left, W - PAD.right]);
  const y = scale([0, yMax], [H - PAD.bottom, PAD.top]);
  const rolling = points.map((p, i) => ({ i, v: p.brier_rolling })).filter((d): d is { i: number; v: number } => d.v !== null);
  const path = rolling.map((d, k) => `${k === 0 ? "M" : "L"}${x(d.i).toFixed(1)} ${y(d.v).toFixed(1)}`).join(" ");
  const last = rolling[rolling.length - 1];
  const yTicks = [0, yMax / 2, yMax];

  return (
    <figure className="w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Brier score trend across closed projects">
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} stroke={VIZ.grid} strokeWidth={1} />
            <text x={PAD.left - 6} y={y(t) + 3} textAnchor="end" style={{ font: FONT, fill: VIZ.text2 }}>
              {t.toFixed(2)}
            </text>
          </g>
        ))}
        {points.map((p, i) => (
          <g key={p.project_id}>
            <title>{`${p.project_title ?? "Project"}: project Brier ${p.brier_project.toFixed(3)}${p.brier_rolling !== null ? `, rolling ${p.brier_rolling.toFixed(3)} (n=${p.n_rolling})` : ""}`}</title>
            <circle cx={x(i)} cy={y(p.brier_project)} r={4} fill={VIZ.series1Soft} />
            <text x={x(i)} y={H - PAD.bottom + 16} textAnchor="middle" style={{ font: FONT, fill: VIZ.text2 }}>
              {truncate(p.project_title ?? "—", 12)}
            </text>
          </g>
        ))}
        {rolling.length > 0 && <path d={path} fill="none" stroke={VIZ.series1} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />}
        {rolling.map((d) => (
          <g key={d.i}>
            <circle cx={x(d.i)} cy={y(d.v)} r={6} fill={VIZ.surface} />
            <circle cx={x(d.i)} cy={y(d.v)} r={4} fill={VIZ.series1} />
          </g>
        ))}
        {last && (
          <text x={x(last.i) + 10} y={y(last.v) + 4} style={{ font: FONT, fill: VIZ.text }}>
            {last.v.toFixed(3)}
          </text>
        )}
        <text x={PAD.left} y={H - 6} style={{ font: FONT, fill: VIZ.text2 }}>
          Line: rolling Brier over the last 30 predictions · dots: each project alone · lower is better
        </text>
      </svg>
    </figure>
  );
}
