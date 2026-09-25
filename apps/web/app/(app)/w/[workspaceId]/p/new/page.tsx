"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { ProjectForm, type ProjectFormValues } from "@/components/project/ProjectForm";
import { SuggestionsPanel } from "@/components/session/SuggestionsPanel";
import { ApiError } from "@/lib/api";
import { useCreateProject } from "@/lib/queries/projects";
import { useWorkspaceContext } from "@/lib/workspace-context";

export default function NewProjectPage() {
  const { workspace } = useWorkspaceContext();
  const router = useRouter();
  const create = useCreateProject(workspace.id);
  const [live, setLive] = useState<ProjectFormValues>({ title: "", description: "", tags: [], planned_start: "", planned_end: "" });
  const [serverError, setServerError] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">New project</h1>
        <p className="text-sm text-muted-foreground">As you type, Foresight surfaces risks from similar past projects and how often they came true.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <ProjectForm
          submitLabel="Create project"
          pending={create.isPending}
          serverError={serverError}
          onValuesChange={setLive}
          onSubmit={async (values) => {
            setServerError(null);
            try {
              const p = await create.mutateAsync(values);
              toast.success("Project created");
              router.push(`/w/${workspace.id}/p/${p.id}`);
            } catch (e) {
              setServerError(e instanceof ApiError ? e.message : "Could not create the project");
            }
          }}
        />
        <SuggestionsPanel workspaceId={workspace.id} title={live.title} description={live.description} tags={live.tags} />
      </div>
    </div>
  );
}
