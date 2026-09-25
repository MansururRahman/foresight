import { StatTile } from "@/components/charts/StatTile";
import { BIAS_LABEL, CONFIDENCE_LABEL, num, signed } from "@/lib/format";
import type { UserCalibration, WorkspaceCalibration } from "@/lib/types";

type Summary = Pick<UserCalibration | WorkspaceCalibration, "brier" | "brier_skill" | "base_rate" | "bias" | "bias_label" | "overconfidence" | "confidence_label" | "trend">;

const TREND_LABEL = { improving: "improving", worsening: "worsening", flat: "flat", insufficient_data: "needs 4+ projects" } as const;

export function CalibrationSummaryTiles({ s, nGraded }: { s: Summary; nGraded: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <StatTile label="Brier score" value={num(s.brier, 3)} hint={s.brier === null ? "needs 10 graded" : `${nGraded} graded · 0 is perfect`} tone={s.brier !== null && s.brier < 0.15 ? "good" : "neutral"} />
      <StatTile label="Skill vs base rate" value={signed(s.brier_skill)} hint={`base rate ${num(s.base_rate)}`} tone={s.brier_skill !== null && s.brier_skill > 0 ? "good" : "neutral"} />
      <StatTile label="Bias" value={signed(s.bias)} hint={s.bias_label ? BIAS_LABEL[s.bias_label] : "—"} tone={s.bias_label && s.bias_label !== "calibrated" ? "warn" : "neutral"} />
      <StatTile label="Confidence" value={signed(s.overconfidence)} hint={s.confidence_label ? CONFIDENCE_LABEL[s.confidence_label] : "—"} tone={s.confidence_label && s.confidence_label !== "calibrated" ? "warn" : "neutral"} />
      <StatTile label="Trend" value={TREND_LABEL[s.trend.direction]} hint={s.trend.slope !== null ? `slope ${signed(s.trend.slope, 3)} per project` : "rolling Brier"} tone={s.trend.direction === "improving" ? "good" : s.trend.direction === "worsening" ? "warn" : "neutral"} />
    </div>
  );
}
