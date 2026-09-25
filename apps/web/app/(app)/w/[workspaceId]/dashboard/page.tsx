"use client";

import { BrierTrend } from "@/components/charts/BrierTrend";
import { ReliabilityDiagram } from "@/components/charts/ReliabilityDiagram";
import { TagBiasChart } from "@/components/charts/TagBiasChart";
import { BlindSpotsList } from "@/components/dashboard/BlindSpotsList";
import { CalibrationSummaryTiles } from "@/components/dashboard/CalibrationSummaryTiles";
import { MembersTable } from "@/components/dashboard/MembersTable";
import { SampleNotice } from "@/components/dashboard/SampleNotice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { pct } from "@/lib/format";
import { useWorkspaceCalibration } from "@/lib/queries/calibration";
import { useWorkspaceContext } from "@/lib/workspace-context";

export default function DashboardPage() {
  const { workspace } = useWorkspaceContext();
  const { data, isLoading, error } = useWorkspaceCalibration(workspace.id);

  if (isLoading) return <Skeleton className="h-96" />;
  if (error || !data) return <p className="text-sm text-destructive">Could not load the dashboard.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Team calibration</h1>
        <p className="text-sm text-muted-foreground">
          {data.sample.n_graded} graded predictions across {data.sample.n_projects_graded} of {data.sample.n_projects_closed} closed projects, from{" "}
          {data.sample.n_voters} voters.
        </p>
      </div>

      <SampleNotice n={data.sample.n_graded} needed={data.sample.needed} sufficient={data.sample.sufficient} />
      <CalibrationSummaryTiles s={data} nGraded={data.sample.n_graded} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Reliability</CardTitle>
            <CardDescription>Where the team says 70%, does it happen 70% of the time?</CardDescription>
          </CardHeader>
          <CardContent>
            <ReliabilityDiagram bins={data.bins} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Brier trend</CardTitle>
            <CardDescription>Is the team getting better at predicting its own failures?</CardDescription>
          </CardHeader>
          <CardContent>
            <BrierTrend points={data.trend.points} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Blind spots</CardTitle>
            <CardDescription>Risks that happened but were predicted below 30%.</CardDescription>
          </CardHeader>
          <CardContent>
            <BlindSpotsList items={data.blind_spots} workspaceId={workspace.id} empty="No blind spots yet. Good, or too early to tell." />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">False alarms</CardTitle>
            <CardDescription>Risks predicted at 70% or more that did not happen.</CardDescription>
          </CardHeader>
          <CardContent>
            <BlindSpotsList items={data.false_alarms} workspaceId={workspace.id} empty="No false alarms recorded." />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Chronic bias by tag</CardTitle>
            <CardDescription>Which kinds of risk does the team systematically over- or under-estimate?</CardDescription>
          </CardHeader>
          <CardContent>
            <TagBiasChart tags={data.tags} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Surprises</CardTitle>
            <CardDescription>What went wrong that nobody predicted.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">
              <span className="text-2xl font-semibold tabular-nums">{data.surprises.rate_per_project.toFixed(1)}</span>{" "}
              <span className="text-muted-foreground">surprises per graded project</span>
              {data.surprises.share !== null && (
                <>
                  {" · "}
                  <span className="font-medium tabular-nums">{pct(data.surprises.share)}</span>{" "}
                  <span className="text-muted-foreground">of what went wrong was unpredicted</span>
                </>
              )}
            </p>
            {data.surprises.recent.length > 0 ? (
              <ul className="space-y-1 text-sm">
                {data.surprises.recent.map((s) => (
                  <li key={s.risk_id} className="rounded-md border px-3 py-2">
                    {s.statement} <span className="text-xs text-muted-foreground">· {s.project_title}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">No surprises recorded yet.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {data.members && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Members</CardTitle>
            <CardDescription>Visible to admins only. Individual scores are never shown to other members, so nobody games their votes.</CardDescription>
          </CardHeader>
          <CardContent>
            <MembersTable members={data.members} workspaceId={workspace.id} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
