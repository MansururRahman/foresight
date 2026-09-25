"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useWorkspace } from "@/lib/queries/workspaces";
import { WorkspaceContext } from "@/lib/workspace-context";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { data, isLoading, error } = useWorkspace(workspaceId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (error || !data) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="rounded-lg border p-8 text-center">
        <p className="font-medium">{notFound ? "Workspace not found" : "Could not load this workspace"}</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {notFound ? "You may not be a member. " : ""}
          <Link href="/w" className="underline underline-offset-4">
            Back to your workspaces
          </Link>
        </p>
      </div>
    );
  }
  const isOwner = data.my_role === "owner";
  const isAdmin = isOwner || data.my_role === "admin";
  return (
    <WorkspaceContext.Provider value={{ workspace: data, myRole: data.my_role, isAdmin, isOwner }}>
      {children}
    </WorkspaceContext.Provider>
  );
}
