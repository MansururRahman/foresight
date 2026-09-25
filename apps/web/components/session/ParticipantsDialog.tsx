"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { useAddParticipants, useRemoveParticipant } from "@/lib/queries/sessions";
import { useMembers } from "@/lib/queries/workspaces";
import type { SessionOut } from "@/lib/types";

export function ParticipantsDialog({ session }: { session: SessionOut }) {
  const [open, setOpen] = useState(false);
  const { data: members } = useMembers(session.workspace_id);
  const add = useAddParticipants(session.id);
  const remove = useRemoveParticipant(session.id);
  const participantIds = new Set(session.participants.map((p) => p.id));
  const candidates = (members ?? []).filter((m) => !participantIds.has(m.user.id));

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      toast.success(ok);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Something went wrong");
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        Participants ({session.participants.length})
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Participants</DialogTitle>
          <DialogDescription>Participants submit risks and vote. Everyone in the workspace sees the results once sealed.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <ul className="divide-y rounded-md border">
            {session.participants.map((p) => (
              <li key={p.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <span>
                  {p.name} <span className="text-muted-foreground">· {p.email}</span>
                  {p.id === session.facilitator.id && <span className="ml-1 text-xs text-muted-foreground">(facilitator)</span>}
                </span>
                {p.id !== session.facilitator.id && session.phase !== "sealed" && (
                  <Button variant="ghost" size="sm" disabled={remove.isPending} onClick={() => run(() => remove.mutateAsync(p.id), "Participant removed")}>
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {candidates.length > 0 && session.phase !== "sealed" && (
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Add from the workspace</p>
              <ul className="divide-y rounded-md border">
                {candidates.map((m) => (
                  <li key={m.user.id} className="flex items-center justify-between px-3 py-2 text-sm">
                    <span>
                      {m.user.name} <span className="text-muted-foreground">· {m.user.email}</span>
                    </span>
                    <Button variant="outline" size="sm" disabled={add.isPending} onClick={() => run(() => add.mutateAsync([m.user.id]), `${m.user.name} added`)}>
                      Add
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
