"use client";

import { useState } from "react";
import { toast } from "sonner";

import { TagInput } from "@/components/project/TagInput";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useAddSurprise, useDeleteSurprise } from "@/lib/queries/grading";
import type { CloseoutOut } from "@/lib/types";

export function SurprisesPanel({ closeout, canEdit }: { closeout: CloseoutOut; canEdit: boolean }) {
  const [statement, setStatement] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const add = useAddSurprise(closeout.project.id);
  const del = useDeleteSurprise(closeout.project.id);
  const dupOf = new Map(closeout.possible_duplicates.map((d) => [d.surprise_id, d]));
  const riskById = new Map(closeout.risks.map((r) => [r.id, r]));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (statement.trim().length < 3) return;
    try {
      await add.mutateAsync({ statement: statement.trim(), tags });
      setStatement("");
      setTags([]);
      toast.success("Surprise recorded. It will inform suggestions for similar future projects.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add the surprise");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Surprises</CardTitle>
        <CardDescription>Things that went wrong that nobody predicted. These are the most valuable lessons for the next pre-mortem.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ul className="space-y-2">
          {closeout.surprises.map((s) => {
            const dup = dupOf.get(s.id);
            return (
              <li key={s.id} className="rounded-md border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm">{s.statement}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {s.tags.map((t) => (
                        <Badge key={t} variant="secondary" className="text-[10px]">
                          {t}
                        </Badge>
                      ))}
                    </div>
                    {dup && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                        Looks similar to a predicted risk: “{riskById.get(dup.risk_id)?.statement}”. If it is the same thing, grade that risk instead.
                      </p>
                    )}
                  </div>
                  {canEdit && (
                    <Button size="sm" variant="ghost" className="text-destructive" disabled={del.isPending} onClick={() => del.mutate(s.id)}>
                      Remove
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
          {closeout.surprises.length === 0 && <li className="text-sm text-muted-foreground">No surprises recorded.</li>}
        </ul>
        {canEdit && (
          <form onSubmit={submit} className="space-y-2 rounded-md border border-dashed p-3">
            <Textarea value={statement} onChange={(e) => setStatement(e.target.value)} rows={2} placeholder="Legal blocked the data-residency clause for three weeks" aria-label="New surprise" />
            <TagInput value={tags} onChange={setTags} placeholder="legal, external…" />
            <Button type="submit" size="sm" disabled={add.isPending || statement.trim().length < 3}>
              Add surprise
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
