"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useCreateWorkspace } from "@/lib/queries/workspaces";

export function CreateWorkspaceDialog({ triggerLabel = "New workspace" }: { triggerLabel?: string }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const create = useCreateWorkspace();
  const router = useRouter();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const ws = await create.mutateAsync({ name: name.trim() });
      setOpen(false);
      setName("");
      toast.success(`Workspace “${ws.name}” created`);
      router.push(`/w/${ws.id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create the workspace");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button />}>{triggerLabel}</DialogTrigger>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>New workspace</DialogTitle>
            <DialogDescription>A workspace holds a team’s projects, pre-mortems and calibration history.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5 py-4">
            <Label htmlFor="ws-name">Name</Label>
            <Input id="ws-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Platform team" autoFocus maxLength={120} />
          </div>
          <DialogFooter>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
