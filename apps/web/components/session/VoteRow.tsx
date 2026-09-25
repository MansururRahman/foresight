"use client";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import type { RiskOut } from "@/lib/types";
import { cn } from "@/lib/utils";

export type VoteValue = { probability: number; impact: number };

const IMPACT_LABELS = ["Negligible", "Minor", "Moderate", "Major", "Severe"];
const DEFAULT_IMPACT = 3;

function clamp(n: number): number {
  if (Number.isNaN(n)) return 0;
  return Math.max(0, Math.min(100, Math.round(n)));
}

type Props = {
  risk: RiskOut;
  value: VoteValue | null;
  onChange: (value: VoteValue) => void;
  disabled?: boolean;
};

export function VoteRow({ risk, value, onChange, disabled }: Props) {
  const probability = value?.probability ?? 0;
  const impact = value?.impact ?? DEFAULT_IMPACT;

  const setProbability = (p: number) => onChange({ probability: clamp(p), impact });
  const setImpact = (i: number) => onChange({ probability, impact: i });

  return (
    <div className={cn("grid gap-3 rounded-lg border p-3 md:grid-cols-[minmax(0,1fr)_240px_auto] md:items-center", value === null && "border-dashed")}>
      <div>
        <p className="text-sm font-medium leading-snug">{risk.statement}</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {risk.origin === "suggestion" && (
            <Badge variant="outline" className="text-[10px]">
              from history
            </Badge>
          )}
          {risk.tags.map((t) => (
            <Badge key={t} variant="secondary" className="text-[10px]">
              {t}
            </Badge>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Slider
          aria-label={`Probability slider for ${risk.statement}`}
          min={0}
          max={100}
          step={1}
          value={[probability]}
          disabled={disabled}
          onValueChange={(v) => setProbability(Array.isArray(v) ? Number(v[0]) : Number(v))}
          className="flex-1"
        />
        <div className="flex items-center gap-1">
          <Input
            type="number"
            inputMode="numeric"
            min={0}
            max={100}
            aria-label={`Probability for ${risk.statement}`}
            className="h-8 w-16 text-right tabular-nums"
            value={value === null ? "" : probability}
            placeholder="—"
            disabled={disabled}
            onChange={(e) => {
              if (e.target.value === "") return;
              setProbability(Number(e.target.value));
            }}
          />
          <span className="text-sm text-muted-foreground">%</span>
        </div>
      </div>

      <div role="radiogroup" aria-label={`Impact for ${risk.statement}`} className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <button
            key={i}
            type="button"
            role="radio"
            aria-checked={impact === i}
            aria-label={`Impact ${i}: ${IMPACT_LABELS[i - 1]}`}
            title={IMPACT_LABELS[i - 1]}
            disabled={disabled}
            onClick={() => setImpact(i)}
            className={cn(
              "size-7 rounded-full border text-xs tabular-nums transition-colors",
              impact === i ? "border-foreground bg-foreground text-background" : "border-input hover:bg-accent",
            )}
          >
            {i}
          </button>
        ))}
      </div>
    </div>
  );
}
