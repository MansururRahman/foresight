"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ParticipantsDialog } from "@/components/session/ParticipantsDialog";
import { VoteRow, type VoteValue } from "@/components/session/VoteRow";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { useMyVotes, usePutVotes, useRisks, useTransitionSession } from "@/lib/queries/sessions";
import type { ProjectOut, SessionOut } from "@/lib/types";

const AUTOSAVE_MS = 600;

export function VoteView({ session, project }: { session: SessionOut; project: ProjectOut }) {
  const { data: risks, error } = useRisks(session.id, session.phase);
  const { data: myVotes } = useMyVotes(session.id, session.me.is_participant);
  const put = usePutVotes(session.id);
  const transition = useTransitionSession(session.id, project.id);

  const [local, setLocal] = useState<Record<string, VoteValue>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const hydrated = useRef(false);

  // Hydrate once from the server copy of my votes.
  useEffect(() => {
    if (hydrated.current || !myVotes) return;
    hydrated.current = true;
    const initial: Record<string, VoteValue> = {};
    for (const v of myVotes.items) initial[v.risk_id] = { probability: v.probability, impact: v.impact };
    setLocal(initial);
  }, [myVotes]);

  // Debounced autosave of whatever changed.
  useEffect(() => {
    if (dirty.size === 0) return;
    const t = setTimeout(async () => {
      const ids = Array.from(dirty);
      const payload = ids.filter((id) => local[id]).map((id) => ({ risk_id: id, ...local[id] }));
      setDirty(new Set());
      if (payload.length === 0) return;
      try {
        await put.mutateAsync(payload);
      } catch (e) {
        toast.error(e instanceof ApiError ? e.message : "Could not save your votes");
        setDirty((d) => new Set([...d, ...ids]));
      }
    }, AUTOSAVE_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dirty, local]);

  if (!session.me.is_participant) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">Participants are voting privately. Results appear once the facilitator seals the session.</CardContent>
      </Card>
    );
  }
  if (error) return <p className="text-sm text-destructive">Could not load the risks.</p>;

  const items = risks?.items ?? [];
  const saved = myVotes?.items.length ?? 0;
  const status = put.isPending ? "Saving…" : dirty.size > 0 ? "Unsaved changes" : `Saved ${saved} of ${items.length}`;
  const incomplete = session.counts.participants - session.counts.voters_complete;

  const seal = async () => {
    if (incomplete > 0 && !window.confirm(`${incomplete} participant${incomplete === 1 ? " has" : "s have"} not finished voting. Seal anyway?`)) return;
    try {
      const r = await transition.mutateAsync("sealed");
      if (r.incomplete_voters.length) toast.warning(`Sealed. Incomplete voters: ${r.incomplete_voters.map((u) => u.name).join(", ")}`);
      else toast.success("Session sealed. Aggregates are now visible to everyone.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not seal");
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">Rate each risk</CardTitle>
              <CardDescription>How likely is it to actually happen, and how bad would it be? Your answers stay hidden until the seal.</CardDescription>
            </div>
            <span className="text-sm tabular-nums text-muted-foreground" aria-live="polite">
              {status}
            </span>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {items.map((r) => (
            <VoteRow
              key={r.id}
              risk={r}
              value={local[r.id] ?? null}
              onChange={(v) => {
                setLocal((prev) => ({ ...prev, [r.id]: v }));
                setDirty((d) => new Set(d).add(r.id));
              }}
            />
          ))}
        </CardContent>
      </Card>
      {session.me.is_facilitator && (
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <p className="text-sm text-muted-foreground tabular-nums">
              {session.counts.voters_complete} of {session.counts.participants} voters complete
            </p>
            <div className="flex gap-2">
              <ParticipantsDialog session={session} />
              <Button onClick={seal} disabled={transition.isPending || dirty.size > 0 || put.isPending}>
                Seal session
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
