"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api";
import { useAddMember } from "@/lib/queries/workspaces";
import type { WorkspaceRole } from "@/lib/types";
import { useWorkspaceContext } from "@/lib/workspace-context";

export function AddMemberForm() {
  const { workspace, isOwner } = useWorkspaceContext();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("member");
  const [error, setError] = useState<string | null>(null);
  const add = useAddMember(workspace.id);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const m = await add.mutateAsync({ email: email.trim(), role });
      toast.success(`${m.user.name} added as ${m.role}`);
      setEmail("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add the member");
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3 rounded-lg border p-4">
      <div className="min-w-64 flex-1 space-y-1.5">
        <Label htmlFor="member-email">Email of a registered user</Label>
        <Input id="member-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="grace@demo.local" required />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="member-role">Role</Label>
        <Select value={role} onValueChange={(v) => v && setRole(v as WorkspaceRole)}>
          <SelectTrigger id="member-role" className="w-32" aria-label="Role">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="member">member</SelectItem>
            <SelectItem value="admin">admin</SelectItem>
            {isOwner && <SelectItem value="owner">owner</SelectItem>}
          </SelectContent>
        </Select>
      </div>
      <Button type="submit" disabled={add.isPending || !email.trim()}>
        {add.isPending ? "Adding…" : "Add member"}
      </Button>
      {error && (
        <p role="alert" className="basis-full text-sm text-destructive">
          {error}
        </p>
      )}
    </form>
  );
}
