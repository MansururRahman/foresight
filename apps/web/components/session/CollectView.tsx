"use client";

import { useState } from "react";
import { toast } from "sonner";

import { ParticipantsDialog } from "@/components/session/ParticipantsDialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useCreateRisk, useDeleteRisk, usePatchRisk, useRisks, useTransitionSession } from "@/lib/queries/sessions";
import type { ProjectOut, RiskOut, SessionOut } from "@/lib/types";

function RiskItem({ risk, sessionId }: { risk: RiskOut; sessionId: string }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(risk.statement);
  const patch = usePatchRisk(sessionId);
  const del = useDeleteRisk(sessionId);

  const save = async () => {
    try {
      await patch.mutateAsync({ riskId: risk.id, body: { statement: text.trim() } });
      setEditing(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save");
    }
  };

  return (
    <li className="rounded-md border p-3">
      {editing ? (
        <div className="space-y-2">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} aria-label="Edit risk" />
          <div className="flex gap-2">
            <Button size="sm" onClick={save} disabled={patch.isPending || text.trim().length < 3}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-3">
          <p className="text-sm">{risk.statement}</p>
          <div className="flex shrink-0 gap-1">
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button size="sm" variant="ghost" className="text-destructive" disabled={del.isPending} onClick={() => del.mutate(risk.id)}>
              Delete
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}

export function CollectView({ session, project }: { session: SessionOut; project: ProjectOut }) {
  const { data, error } = useRisks(session.id, session.phase);
  const create = useCreateRisk(session.id);
  const transition = useTransitionSession(session.id, project.id);
  const [draft, setDraft] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const statement = draft.trim();
    if (statement.length < 3) return;
    try {
      await create.mutateAsync(statement);
      setDraft("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add the risk");
    }
  };

  const advance = async () => {
    try {
      await transition.mutateAsync("merge");
      toast.success("Collection closed. You can now merge duplicates.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not advance");
    }
  };

  const due = project.planned_end ? new Date(project.planned_end).toLocaleDateString(undefined, { month: "long", day: "numeric" }) : "the deadline";

  if (!session.me.is_participant) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          Risks are being collected privately by the participants. You will see the results once the session is sealed.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">“Imagine it is {due} and this project has failed. Why?”</CardTitle>
          <CardDescription>Your risks are private until the facilitator advances, so nobody anchors on anyone else.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={submit} className="space-y-2">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={2}
              placeholder="The vendor API is not ready when integration starts"
              aria-label="New risk"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit(e);
                }
              }}
            />
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">One risk per entry. Enter to add, Shift+Enter for a new line.</p>
              <Button type="submit" size="sm" disabled={create.isPending || draft.trim().length < 3}>
                Add risk
              </Button>
            </div>
          </form>
          {error && <p className="text-sm text-destructive">Could not load your risks.</p>}
          <ul className="space-y-2">
            {(data?.items ?? []).map((r) => (
              <RiskItem key={r.id} risk={r} sessionId={session.id} />
            ))}
            {data && data.items.length === 0 && <li className="text-sm text-muted-foreground">Nothing yet. What could go wrong?</li>}
          </ul>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {session.me.is_facilitator && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Facilitator</CardTitle>
              <CardDescription>You see counts, not content, until you advance.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="space-y-1 text-sm">
                {session.participants.map((p) => {
                  const count = data?.submission_counts?.find((c) => c.user.id === p.id)?.count ?? 0;
                  return (
                    <li key={p.id} className="flex justify-between">
                      <span>{p.name}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {count} risk{count === 1 ? "" : "s"}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <div className="flex flex-wrap gap-2">
                <ParticipantsDialog session={session} />
                <Button size="sm" onClick={advance} disabled={transition.isPending || session.counts.risks_total === 0}>
                  Advance to merge →
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
        {!session.me.is_facilitator && (
          <Card>
            <CardContent className="p-4 text-sm text-muted-foreground">
              {session.facilitator.name} facilitates this session and will advance it when everyone has submitted.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
