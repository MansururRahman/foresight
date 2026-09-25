"use client";

import { CreateWorkspaceDialog } from "@/components/workspace/CreateWorkspaceDialog";
import { WorkspaceCard } from "@/components/workspace/WorkspaceCard";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkspaces } from "@/lib/queries/workspaces";

export default function WorkspacesPage() {
  const { data, isLoading, error } = useWorkspaces();
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Workspaces</h1>
          <p className="text-sm text-muted-foreground">Each workspace is a team with its own projects and calibration history.</p>
        </div>
        <CreateWorkspaceDialog />
      </div>
      {isLoading && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      )}
      {error && <p className="text-sm text-destructive">Could not load workspaces.</p>}
      {data && data.length === 0 && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <p className="font-medium">No workspaces yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Create one for your team, or ask an admin to add you by email.</p>
        </div>
      )}
      {data && data.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((w) => (
            <WorkspaceCard key={w.id} workspace={w} />
          ))}
        </div>
      )}
    </div>
  );
}
