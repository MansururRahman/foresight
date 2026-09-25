"use client";

import { useState } from "react";
import { toast } from "sonner";

import { TagInput } from "@/components/project/TagInput";
import { ParticipantsDialog } from "@/components/session/ParticipantsDialog";
import { SuggestionsPanel } from "@/components/session/SuggestionsPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useAdoptRisk, useDeleteRisk, usePatchRisk, useRisks, useTransitionSession } from "@/lib/queries/sessions";
import type { ProjectOut, RiskOut, SessionOut } from "@/lib/types";
import { cn } from "@/lib/utils";

const NONE = "__none__";

function MergeRow({ risk, canonical, sessionId }: { risk: RiskOut; canonical: RiskOut[]; sessionId: string }) {
  const [text, setText] = useState(risk.statement);
  const patch = usePatchRisk(sessionId);
  const del = useDeleteRisk(sessionId);
  const dirty = text.trim() !== risk.statement;
  const isDup = risk.duplicate_of !== null;

  const run = async (body: Parameters<typeof patch.mutateAsync>[0]["body"]) => {
    try {
      await patch.mutateAsync({ riskId: risk.id, body });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update the risk");
    }
  };

  return (
    <div className={cn("space-y-2 rounded-lg border p-3", isDup && "bg-muted/40")}>
      <div className="flex items-start gap-3">
        <div className="flex-1 space-y-2">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} aria-label={`Statement for risk by ${risk.author?.name ?? "unknown"}`} disabled={isDup} />
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>by {risk.author?.name ?? "—"}</span>
            {risk.origin === "suggestion" && <Badge variant="outline">from history</Badge>}
          </div>
        </div>
        <div className="flex shrink-0 flex-col gap-1">
          <Button size="sm" variant="outline" disabled={!dirty || patch.isPending || text.trim().length < 3} onClick={() => run({ statement: text.trim() })}>
            Save wording
          </Button>
          <Button size="sm" variant="ghost" className="text-destructive" disabled={del.isPending} onClick={() => del.mutate(risk.id)}>
            Delete
          </Button>
        </div>
      </div>
      {!isDup && (
        <div className="grid gap-2 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Tags</p>
            <TagInput value={risk.tags} onChange={(tags) => run({ tags })} />
          </div>
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Duplicate of</p>
            <Select value={NONE} onValueChange={(v) => v && v !== NONE && run({ duplicate_of: v })}>
              <SelectTrigger className="w-full" aria-label={`Mark as duplicate: ${risk.statement}`}>
                <SelectValue placeholder="Keep as its own risk" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Keep as its own risk</SelectItem>
                {canonical
                  .filter((c) => c.id !== risk.id)
                  .map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.statement.length > 70 ? `${c.statement.slice(0, 70)}…` : c.statement}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      )}
      {isDup && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">
            Merged into: {canonical.find((c) => c.id === risk.duplicate_of)?.statement ?? "another risk"}
          </span>
          <Button size="sm" variant="ghost" onClick={() => run({ duplicate_of: null })}>
            Un-merge
          </Button>
        </div>
      )}
      {risk.merged_from.length > 0 && (
        <p className="text-xs text-muted-foreground">Absorbs: {risk.merged_from.map((m) => m.statement).join(" · ")}</p>
      )}
    </div>
  );
}

export function MergeView({ session, project }: { session: SessionOut; project: ProjectOut }) {
  const { data, error } = useRisks(session.id, session.phase);
  const transition = useTransitionSession(session.id, project.id);
  const adopt = useAdoptRisk(session.id);

  if (!session.me.is_facilitator) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">
          {session.facilitator.name} is merging duplicate risks. Voting opens when they are done.
        </CardContent>
      </Card>
    );
  }
  if (error) return <p className="text-sm text-destructive">Could not load the risks.</p>;

  const items = data?.items ?? [];
  const canonical = items.filter((r) => r.duplicate_of === null);
  const advance = async () => {
    try {
      await transition.mutateAsync("vote");
      toast.success("Voting is open. Participants now rate each risk privately.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not advance");
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Merge and tag</CardTitle>
          <CardDescription>
            {canonical.length} canonical of {items.length} submitted. Fix wording, add tags, and mark duplicates. Original wording is kept.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {items.map((r) => (
            <MergeRow key={r.id} risk={r} canonical={canonical} sessionId={session.id} />
          ))}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <ParticipantsDialog session={session} />
            <Button onClick={advance} disabled={transition.isPending || canonical.length === 0}>
              Advance to vote →
            </Button>
          </div>
        </CardContent>
      </Card>
      <SuggestionsPanel
        workspaceId={session.workspace_id}
        title={project.title}
        description={project.description}
        tags={project.tags}
        excludeProjectId={project.id}
        adopting={adopt.isPending}
        onAdopt={async (s) => {
          const src = s.sources[0];
          if (!src) return;
          try {
            await adopt.mutateAsync({ source_risk_id: src.risk_id, statement: s.statement, tags: s.tags });
            toast.success("Suggestion adopted as a canonical risk");
          } catch (e) {
            toast.error(e instanceof ApiError ? e.message : "Could not adopt the suggestion");
          }
        }}
      />
    </div>
  );
}
