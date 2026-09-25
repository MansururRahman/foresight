"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { ProjectReport } from "@/components/project/ProjectReport";
import { PhaseBadge, StatusBadge } from "@/components/project/StatusBadge";
import { TransitionButtons } from "@/components/project/TransitionButtons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiFetch } from "@/lib/api";
import { PHASE_LABEL, shortDate } from "@/lib/format";
import { projectKeys, useProject } from "@/lib/queries/projects";
import { useMembers } from "@/lib/queries/workspaces";
import type { SessionOut } from "@/lib/types";
import { useWorkspaceContext } from "@/lib/workspace-context";

export default function ProjectPage() {
  const { workspace } = useWorkspaceContext();
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading, error } = useProject(projectId);
  const { data: members } = useMembers(workspace.id);
  const qc = useQueryClient();

  const startSession = useMutation({
    mutationFn: () =>
      apiFetch<SessionOut>(`/v1/projects/${projectId}/session`, {
        method: "POST",
        body: { participant_ids: (members ?? []).map((m) => m.user.id) },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.one(projectId) });
      void qc.invalidateQueries({ queryKey: ["projects", workspace.id] });
      toast.success("Pre-mortem session started. Everyone in the workspace is a participant.");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not start the session"),
  });

  if (isLoading) return <Skeleton className="h-64" />;
  if (error || !project) return <p className="text-sm text-destructive">Project not found.</p>;

  const base = `/w/${workspace.id}/p/${project.id}`;
  const sess = project.session;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{project.title}</h1>
          <StatusBadge status={project.status} />
          {project.archived_at && <Badge variant="outline">archived</Badge>}
        </div>
        {project.description && <p className="max-w-3xl text-sm text-muted-foreground">{project.description}</p>}
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          {project.tags.map((t) => (
            <Badge key={t} variant="secondary" className="text-[10px]">
              {t}
            </Badge>
          ))}
          <span>
            {project.planned_start || project.planned_end
              ? `Planned ${shortDate(project.planned_start)} → ${shortDate(project.planned_end)}`
              : "No planned dates"}
          </span>
          <span>· created by {project.created_by.name}</span>
        </div>
      </div>

      <TransitionButtons project={project} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pre-mortem</CardTitle>
          <CardDescription>
            {sess
              ? `${PHASE_LABEL[sess.phase]}${sess.sealed_at ? ` · sealed ${shortDate(sess.sealed_at)}` : ""}`
              : "Imagine the project has failed. Collect why, privately, before anyone anchors on anyone else."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          {!sess && project.status !== "closed" && !project.archived_at && (
            <Button onClick={() => startSession.mutate()} disabled={startSession.isPending || !members}>
              {startSession.isPending ? "Starting…" : "Start pre-mortem session"}
            </Button>
          )}
          {sess && (
            <>
              <PhaseBadge phase={sess.phase} />
              <Button render={<Link href={`${base}/session`} />} variant={sess.phase === "sealed" ? "outline" : "default"}>
                {sess.phase === "sealed" ? "View results" : "Open session"}
              </Button>
              {sess.phase === "sealed" && (
                <Button render={<Link href={`${base}/closeout`} />} variant="outline">
                  {sess.fully_graded_at ? "Review grading" : "Grade outcomes"}
                </Button>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {sess?.phase === "sealed" && <ProjectReport projectId={project.id} />}
    </div>
  );
}
