import { Check } from "lucide-react";

import type { SessionPhase } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS: { phase: SessionPhase; label: string; hint: string }[] = [
  { phase: "collect", label: "Collect", hint: "Everyone lists risks privately" },
  { phase: "merge", label: "Merge", hint: "Facilitator dedupes and tags" },
  { phase: "vote", label: "Vote", hint: "Hidden probability and impact" },
  { phase: "sealed", label: "Sealed", hint: "Aggregates revealed" },
];

export function PhaseStepper({ phase }: { phase: SessionPhase }) {
  const current = STEPS.findIndex((s) => s.phase === phase);
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Session phase">
      {STEPS.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={s.phase} className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-medium",
                done && "border-foreground bg-foreground text-background",
                active && "border-foreground",
                !done && !active && "text-muted-foreground",
              )}
            >
              {done ? <Check className="size-3.5" aria-hidden /> : i + 1}
            </span>
            <span className={cn("text-sm", active ? "font-medium" : "text-muted-foreground")} title={s.hint}>
              {s.label}
            </span>
            {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-border" aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}
