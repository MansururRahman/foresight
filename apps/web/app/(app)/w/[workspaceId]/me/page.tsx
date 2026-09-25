"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { BrierTrend } from "@/components/charts/BrierTrend";
import { ReliabilityDiagram } from "@/components/charts/ReliabilityDiagram";
import { CalibrationSummaryTiles } from "@/components/dashboard/CalibrationSummaryTiles";
import { SampleNotice } from "@/components/dashboard/SampleNotice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";
import { num } from "@/lib/format";
import { useMyCalibration, useUserCalibration } from "@/lib/queries/calibration";
import { useWorkspaceContext } from "@/lib/workspace-context";

function MeView() {
  const { workspace, isAdmin } = useWorkspaceContext();
  const { user } = useAuth();
  const params = useSearchParams();
  const requested = params.get("user");
  const other = isAdmin && requested && requested !== user?.id ? requested : null;
  const mine = useMyCalibration(workspace.id);
  const theirs = useUserCalibration(workspace.id, other);
  const { data, isLoading, error } = other ? theirs : mine;

  if (isLoading) return <Skeleton className="h-96" />;
  if (error || !data) return <p className="text-sm text-destructive">Could not load this calibration.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{other ? `${data.user.name}'s calibration` : "My calibration"}</h1>
        <p className="text-sm text-muted-foreground">
          {data.sample.n_graded} graded predictions across {data.sample.n_projects} projects. Only you and workspace admins can see this.
          {other && (
            <>
              {" "}
              <Link href={`/w/${workspace.id}/me`} className="underline underline-offset-4">
                Back to mine
              </Link>
            </>
          )}
        </p>
      </div>
      <SampleNotice n={data.sample.n_graded} needed={data.sample.needed} sufficient={data.sample.sufficient} />
      <CalibrationSummaryTiles s={data} nGraded={data.sample.n_graded} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Reliability</CardTitle>
            <CardDescription>Dots above the line: things happened more than you expected.</CardDescription>
          </CardHeader>
          <CardContent>
            <ReliabilityDiagram bins={data.bins} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Brier trend</CardTitle>
            <CardDescription>Your rolling score, project by project.</CardDescription>
          </CardHeader>
          <CardContent>
            <BrierTrend points={data.trend.points} />
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Worst calls</CardTitle>
          <CardDescription>The predictions that cost the most Brier points. Confident and wrong is the expensive combination.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.worst_calls.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing graded yet.</p>
          ) : (
            <ul className="space-y-2">
              {data.worst_calls.map((w) => (
                <li key={w.risk_id} className="flex items-start justify-between gap-3 rounded-md border p-3 text-sm">
                  <div>
                    <div>{w.statement}</div>
                    <Link href={`/w/${workspace.id}/p/${w.project_id}`} className="text-xs text-muted-foreground underline-offset-4 hover:underline">
                      {w.project_title}
                    </Link>
                  </div>
                  <div className="whitespace-nowrap text-right tabular-nums text-muted-foreground">
                    said {w.probability}% · {w.outcome}
                    <div className="text-xs">cost {num(w.brier_contribution, 3)}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function MePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <MeView />
    </Suspense>
  );
}
