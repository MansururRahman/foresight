"use client";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { num, pct100 } from "@/lib/format";
import type { GradingOutcome, RiskOut } from "@/lib/types";
import { cn } from "@/lib/utils";

export type GradingMap = Record<string, { outcome: GradingOutcome; note: string }>;

const OUTCOMES: { value: GradingOutcome; label: string; tone: string }[] = [
  { value: "yes", label: "Yes", tone: "aria-checked:bg-rose-600 aria-checked:text-white aria-checked:border-rose-600" },
  { value: "partial", label: "Partial", tone: "aria-checked:bg-amber-500 aria-checked:text-white aria-checked:border-amber-500" },
  { value: "no", label: "No", tone: "aria-checked:bg-emerald-600 aria-checked:text-white aria-checked:border-emerald-600" },
];

type Props = {
  risks: RiskOut[];
  value: GradingMap;
  onChange: (value: GradingMap) => void;
  disabled?: boolean;
};

export function GradingTable({ risks, value, onChange, disabled }: Props) {
  const graded = risks.filter((r) => value[r.id]).length;

  const setOutcome = (riskId: string, outcome: GradingOutcome) =>
    onChange({ ...value, [riskId]: { outcome, note: value[riskId]?.note ?? "" } });
  const setNote = (riskId: string, note: string) => {
    const current = value[riskId];
    if (!current) return;
    onChange({ ...value, [riskId]: { ...current, note } });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <p className="text-muted-foreground">Did each risk actually happen?</p>
        <p className="font-medium tabular-nums">
          Graded {graded} of {risks.length}
        </p>
      </div>
      <div className="space-y-2">
        {risks.map((r) => {
          const g = value[r.id];
          return (
            <div key={r.id} className={cn("grid gap-3 rounded-lg border p-3 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,220px)] lg:items-center", !g && "border-dashed")}>
              <div>
                <p className="text-sm font-medium leading-snug">{r.statement}</p>
                <p className="mt-1 text-xs text-muted-foreground tabular-nums">
                  team predicted <span className="font-medium text-foreground">{pct100(r.aggregates?.mean_probability)}</span>
                  {r.aggregates && <> · agreement {num(r.aggregates.agreement)}</>}
                  {r.origin === "suggestion" && (
                    <Badge variant="outline" className="ml-2 text-[10px]">
                      from history
                    </Badge>
                  )}
                </p>
              </div>
              <div role="radiogroup" aria-label={`Outcome for ${r.statement}`} className="flex gap-1">
                {OUTCOMES.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    role="radio"
                    aria-checked={g?.outcome === o.value}
                    aria-label={`${r.statement}: ${o.label}`}
                    disabled={disabled}
                    onClick={() => setOutcome(r.id, o.value)}
                    className={cn("rounded-md border px-3 py-1 text-xs font-medium transition-colors hover:bg-accent", o.tone)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
              <Input
                aria-label={`Note for ${r.statement}`}
                placeholder={g ? "Optional note (what happened?)" : "Choose an outcome first"}
                value={g?.note ?? ""}
                disabled={disabled || !g}
                onChange={(e) => setNote(r.id, e.target.value)}
                className="h-8"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
