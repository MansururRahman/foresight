import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { pct, signed } from "@/lib/format";
import type { BlindSpot } from "@/lib/types";

export function BlindSpotsList({ items, workspaceId, empty }: { items: BlindSpot[]; workspaceId: string; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <ul className="space-y-2">
      {items.map((b) => (
        <li key={b.risk_id} className="rounded-md border p-3 text-sm">
          <div className="flex items-start justify-between gap-3">
            <span>{b.statement}</span>
            <span className="whitespace-nowrap tabular-nums text-muted-foreground">
              {pct(b.mean_predicted)} → {b.outcome} · miss {signed(b.miss)}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            <Link href={`/w/${workspaceId}/p/${b.project_id}`} className="underline underline-offset-4">
              {b.project_title}
            </Link>
            {b.tags.map((t) => (
              <Badge key={t} variant="secondary" className="text-[10px]">
                {t}
              </Badge>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}
