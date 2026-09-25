"use client";

import Link from "next/link";

import { ProjectCard } from "@/components/project/ProjectCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjects } from "@/lib/queries/projects";
import type { ProjectOut } from "@/lib/types";
import { useWorkspaceContext } from "@/lib/workspace-context";

function Section({ title, projects, workspaceId, empty }: { title: string; projects: ProjectOut[]; workspaceId: string; empty: string }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">
        {title} <span className="tabular-nums">({projects.length})</span>
      </h2>
      {projects.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} workspaceId={workspaceId} />
          ))}
        </div>
      )}
    </section>
  );
}

export default function WorkspaceOverviewPage() {
  const { workspace } = useWorkspaceContext();
  const { data, isLoading } = useProjects(workspace.id);
  const projects = data ?? [];
  const needsGrading = projects.filter((p) => p.status === "closed" && p.session && !p.session.fully_graded_at);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{workspace.name}</h1>
          <p className="text-sm text-muted-foreground">Projects and their pre-mortems.</p>
        </div>
        <Button render={<Link href={`/w/${workspace.id}/p/new`} />}>New project</Button>
      </div>
      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      )}
      {!isLoading && needsGrading.length > 0 && (
        <Section title="Needs grading" projects={needsGrading} workspaceId={workspace.id} empty="" />
      )}
      {!isLoading && (
        <>
          <Section title="Active" projects={projects.filter((p) => p.status === "active")} workspaceId={workspace.id} empty="Nothing in flight." />
          <Section
            title="Planning"
            projects={projects.filter((p) => p.status === "planning")}
            workspaceId={workspace.id}
            empty="Create a project to run its pre-mortem before it starts."
          />
          <Section title="Closed" projects={projects.filter((p) => p.status === "closed")} workspaceId={workspace.id} empty="No closed projects yet." />
        </>
      )}
    </div>
  );
}
