"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { CollectView } from "@/components/session/CollectView";
import { MergeView } from "@/components/session/MergeView";
import { PhaseStepper } from "@/components/session/PhaseStepper";
import { SealedView } from "@/components/session/SealedView";
import { VoteView } from "@/components/session/VoteView";
import { Skeleton } from "@/components/ui/skeleton";
import { useProject } from "@/lib/queries/projects";
import { useSession } from "@/lib/queries/sessions";
import { useWorkspaceContext } from "@/lib/workspace-context";

export default function SessionPage() {
  const { workspace } = useWorkspaceContext();
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading: loadingProject } = useProject(projectId);
  const { data: session, isLoading: loadingSession, error } = useSession(project?.session?.id);

  if (loadingProject || (project?.session && loadingSession)) return <Skeleton className="h-64" />;
  if (!project) return <p className="text-sm text-destructive">Project not found.</p>;
  if (!project.session || error || !session) {
    return (
      <p className="text-sm text-muted-foreground">
        This project has no pre-mortem session yet.{" "}
        <Link href={`/w/${workspace.id}/p/${project.id}`} className="underline underline-offset-4">
          Back to the project
        </Link>
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          <Link href={`/w/${workspace.id}/p/${project.id}`} className="underline underline-offset-4">
            {project.title}
          </Link>{" "}
          · Pre-mortem
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-semibold">Pre-mortem session</h1>
          <PhaseStepper phase={session.phase} />
        </div>
        <p className="text-xs text-muted-foreground">
          Facilitator {session.facilitator.name} · {session.participants.length} participants · {session.counts.risks_canonical} canonical risk
          {session.counts.risks_canonical === 1 ? "" : "s"}
        </p>
      </div>

      {session.phase === "collect" && <CollectView session={session} project={project} />}
      {session.phase === "merge" && <MergeView session={session} project={project} />}
      {session.phase === "vote" && <VoteView session={session} project={project} />}
      {session.phase === "sealed" && <SealedView session={session} project={project} workspaceId={workspace.id} />}
    </div>
  );
}
