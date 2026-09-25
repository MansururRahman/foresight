"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { GradingTable, type GradingMap } from "@/components/grading/GradingTable";
import { SurprisesPanel } from "@/components/grading/SurprisesPanel";
import { StatusBadge } from "@/components/project/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useCloseout, usePutGradings } from "@/lib/queries/grading";
import { useWorkspaceContext } from "@/lib/workspace-context";

export default function CloseoutPage() {
  const { workspace, isAdmin } = useWorkspaceContext();
  const { user } = useAuth();
  const { projectId } = useParams<{ projectId: string }>();
  const { data, isLoading, error } = useCloseout(projectId);
  const put = usePutGradings(projectId);
  const [map, setMap] = useState<GradingMap>({});
  const hydratedFor = useRef<string | null>(null);

  useEffect(() => {
    if (!data) return;
    const key = data.risks.map((r) => `${r.id}:${r.grading?.outcome ?? ""}:${r.grading?.note ?? ""}`).join("|");
    if (hydratedFor.current === key) return;
    hydratedFor.current = key;
    const next: GradingMap = {};
    for (const r of data.risks) if (r.grading) next[r.id] = { outcome: r.grading.outcome, note: r.grading.note };
    setMap(next);
  }, [data]);

  if (isLoading) return <Skeleton className="h-64" />;
  if (error || !data) return <p className="text-sm text-destructive">Could not load the close-out.</p>;

  const canEdit = isAdmin || data.session?.facilitator.id === user?.id || (!data.session && data.project.created_by.id === user?.id);
  const sealed = data.session?.phase === "sealed";
  const changed = Object.entries(map).filter(([id, g]) => {
    const server = data.risks.find((r) => r.id === id)?.grading;
    return !server || server.outcome !== g.outcome || server.note !== g.note;
  });

  const save = async () => {
    try {
      const r = await put.mutateAsync(changed.map(([id, g]) => ({ risk_id: id, outcome: g.outcome, note: g.note })));
      toast.success(r.ungraded_count === 0 ? "All risks graded. Calibration updated." : `Saved. ${r.ungraded_count} still ungraded.`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save the gradings");
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">
          <Link href={`/w/${workspace.id}/p/${projectId}`} className="underline underline-offset-4">
            {data.project.title}
          </Link>{" "}
          · Close-out
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">Grade against reality</h1>
          <StatusBadge status={data.project.status} />
        </div>
        <p className="text-sm text-muted-foreground">
          Each grade turns the team’s predictions into calibration data. Partial counts as half. You can revise grades later.
        </p>
      </div>

      {!sealed ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            {data.session ? "Seal the pre-mortem session before grading." : "This project has no pre-mortem session, so there is nothing to grade. You can still record surprises."}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="space-y-4 p-4">
            <GradingTable risks={data.risks} value={map} onChange={setMap} disabled={!canEdit} />
            {canEdit && (
              <div className="flex items-center justify-end gap-3">
                {changed.length > 0 && <span className="text-xs text-muted-foreground tabular-nums">{changed.length} unsaved</span>}
                <Button onClick={save} disabled={put.isPending || changed.length === 0}>
                  {put.isPending ? "Saving…" : "Save gradings"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {data.project.status !== "planning" && <SurprisesPanel closeout={data} canEdit={canEdit} />}
    </div>
  );
}
