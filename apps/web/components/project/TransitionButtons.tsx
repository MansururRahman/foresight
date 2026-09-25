"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useArchiveProject, useDeleteProject, useTransitionProject } from "@/lib/queries/projects";
import type { ProjectOut } from "@/lib/types";
import { useWorkspaceContext } from "@/lib/workspace-context";

export function TransitionButtons({ project }: { project: ProjectOut }) {
  const { workspace, isAdmin } = useWorkspaceContext();
  const { user } = useAuth();
  const router = useRouter();
  const transition = useTransitionProject(project.id);
  const archive = useArchiveProject(project.id);
  const del = useDeleteProject(workspace.id);

  const canEdit = isAdmin || project.created_by.id === user?.id;
  const sessionSealed = !project.session || project.session.phase === "sealed";

  const run = async (to: "active" | "closed") => {
    if (to === "closed" && !window.confirm("Close this project? Status changes are permanent; grading stays editable.")) return;
    try {
      const r = await transition.mutateAsync(to);
      const ungraded = r.warnings.find((w) => w.code === "ungraded_risks");
      if (ungraded) toast.warning(`Project closed. ${ungraded.count} risk${ungraded.count === 1 ? "" : "s"} still need grading.`);
      else toast.success(to === "active" ? "Project activated" : "Project closed");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Transition failed");
    }
  };

  const onArchive = async () => {
    try {
      await archive.mutateAsync(!project.archived_at);
      toast.success(project.archived_at ? "Project restored" : "Project archived");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not archive");
    }
  };

  const onDelete = async () => {
    if (!window.confirm("Delete this project permanently? Projects with graded history cannot be deleted; archive them instead.")) return;
    try {
      await del.mutateAsync(project.id);
      toast.success("Project deleted");
      router.replace(`/w/${workspace.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete");
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {project.status === "planning" && canEdit && (
        <Button onClick={() => run("active")} disabled={transition.isPending}>
          Activate project
        </Button>
      )}
      {project.status === "active" && canEdit && (
        <Button
          onClick={() => run("closed")}
          disabled={transition.isPending || !sessionSealed}
          title={sessionSealed ? undefined : "Seal the pre-mortem session before closing"}
        >
          Close project
        </Button>
      )}
      {isAdmin && (
        <>
          <Button variant="outline" onClick={onArchive} disabled={archive.isPending}>
            {project.archived_at ? "Unarchive" : "Archive"}
          </Button>
          <Button variant="ghost" className="text-destructive" onClick={onDelete} disabled={del.isPending}>
            Delete
          </Button>
        </>
      )}
    </div>
  );
}
