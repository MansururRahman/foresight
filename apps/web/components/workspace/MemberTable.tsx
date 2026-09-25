"use client";

import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useRemoveMember, useSetRole } from "@/lib/queries/workspaces";
import type { MemberOut, WorkspaceRole } from "@/lib/types";
import { useWorkspaceContext } from "@/lib/workspace-context";

const ROLES: WorkspaceRole[] = ["member", "admin", "owner"];

export function MemberTable({ members }: { members: MemberOut[] }) {
  const { workspace, isAdmin, isOwner } = useWorkspaceContext();
  const { user } = useAuth();
  const setRole = useSetRole(workspace.id);
  const remove = useRemoveMember(workspace.id);

  const onRole = async (userId: string, role: WorkspaceRole) => {
    try {
      await setRole.mutateAsync({ userId, role });
      toast.success("Role updated");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update the role");
    }
  };
  const onRemove = async (m: MemberOut) => {
    const self = m.user.id === user?.id;
    if (!window.confirm(self ? "Leave this workspace?" : `Remove ${m.user.name} from the workspace?`)) return;
    try {
      await remove.mutateAsync(m.user.id);
      toast.success(self ? "You left the workspace" : "Member removed");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not remove the member");
    }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
          <TableHead className="w-24" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((m) => {
          const self = m.user.id === user?.id;
          const canEditRole = isAdmin && (isOwner || m.role !== "owner");
          return (
            <TableRow key={m.user.id}>
              <TableCell className="font-medium">
                {m.user.name}
                {self && <span className="ml-1 text-xs text-muted-foreground">(you)</span>}
              </TableCell>
              <TableCell className="text-muted-foreground">{m.user.email}</TableCell>
              <TableCell>
                {canEditRole ? (
                  <Select value={m.role} onValueChange={(v) => v && onRole(m.user.id, v as WorkspaceRole)}>
                    <SelectTrigger size="sm" aria-label={`Role for ${m.user.name}`} className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ROLES.filter((r) => isOwner || r !== "owner").map((r) => (
                        <SelectItem key={r} value={r}>
                          {r}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Badge variant="secondary">{m.role}</Badge>
                )}
              </TableCell>
              <TableCell className="text-right">
                {(isAdmin || self) && (
                  <Button variant="ghost" size="sm" onClick={() => onRemove(m)} disabled={remove.isPending}>
                    {self ? "Leave" : "Remove"}
                  </Button>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
