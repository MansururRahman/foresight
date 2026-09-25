import { Badge } from "@/components/ui/badge";
import { PHASE_LABEL, STATUS_LABEL } from "@/lib/format";
import type { ProjectStatus, SessionPhase } from "@/lib/types";

const STATUS_CLASS: Record<ProjectStatus, string> = {
  planning: "bg-muted text-muted-foreground",
  active: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  closed: "bg-slate-200 text-slate-900 dark:bg-slate-800 dark:text-slate-200",
};

export function StatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge variant="outline" className={`border-transparent ${STATUS_CLASS[status]}`}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export function PhaseBadge({ phase }: { phase: SessionPhase }) {
  return (
    <Badge variant="outline" className="text-xs">
      {PHASE_LABEL[phase]}
    </Badge>
  );
}
