"use client";

import { AddMemberForm } from "@/components/workspace/AddMemberForm";
import { MemberTable } from "@/components/workspace/MemberTable";
import { Skeleton } from "@/components/ui/skeleton";
import { useMembers } from "@/lib/queries/workspaces";
import { useWorkspaceContext } from "@/lib/workspace-context";

export default function MembersPage() {
  const { workspace, isAdmin } = useWorkspaceContext();
  const { data, isLoading } = useMembers(workspace.id);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Members</h1>
        <p className="text-sm text-muted-foreground">
          Admins add members by the email they registered with. Owners can grant the owner role.
        </p>
      </div>
      {isAdmin && <AddMemberForm />}
      {isLoading ? <Skeleton className="h-40" /> : <MemberTable members={data ?? []} />}
    </div>
  );
}
