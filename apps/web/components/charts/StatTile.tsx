import { cn } from "@/lib/utils";

type Props = {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "good" | "warn";
};

export function StatTile({ label, value, hint, tone = "neutral" }: Props) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold tabular-nums", tone === "warn" && "text-amber-700 dark:text-amber-400", tone === "good" && "text-emerald-700 dark:text-emerald-400")}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}
