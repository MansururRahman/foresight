"use client";

import { Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDebouncedValue, useSuggestions } from "@/lib/queries/suggestions";
import type { Suggestion } from "@/lib/types";

type Props = {
  workspaceId: string;
  title: string;
  description?: string;
  tags: string[];
  excludeProjectId?: string;
  onAdopt?: (s: Suggestion) => void;
  debounceMs?: number;
  adopting?: boolean;
};

export function SuggestionsPanel({
  workspaceId,
  title,
  description = "",
  tags,
  excludeProjectId,
  onAdopt,
  debounceMs = 400,
  adopting = false,
}: Props) {
  const input = useDebouncedValue(
    { title: title.trim(), description: description.trim(), tags, exclude_project_id: excludeProjectId },
    debounceMs,
  );
  const enabled = input.title.length > 0 || input.tags.length > 0;
  const { data } = useSuggestions(workspaceId, input, enabled);

  if (!enabled || !data || data.query.matched_projects === 0 || data.suggestions.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="size-4 text-muted-foreground" aria-hidden />
          Suggested risks
        </CardTitle>
        <CardDescription>
          From {data.query.matched_projects} similar past project{data.query.matched_projects === 1 ? "" : "s"} in this
          workspace, weighted by what actually happened.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.suggestions.map((s) => {
          const materialized = Math.round(s.materialization_rate * s.occurrences);
          const hadSurprise = s.sources.some((src) => src.origin === "surprise");
          const projectTitles = Array.from(new Set(s.sources.map((src) => src.project_title))).join(", ");
          return (
            <div key={s.statement} className="rounded-md border p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium leading-snug">{s.statement}</p>
                {onAdopt && (
                  <Button size="sm" variant="outline" onClick={() => onAdopt(s)} disabled={adopting}>
                    Adopt
                  </Button>
                )}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                materialized {materialized} of {s.occurrences}
                {s.mean_predicted_probability !== null && <> · predicted {Math.round(s.mean_predicted_probability)}%</>}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">from: {projectTitles}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {hadSurprise && (
                  <Badge variant="destructive" className="text-[10px]">
                    surprise last time
                  </Badge>
                )}
                {s.tags.map((t) => (
                  <Badge key={t} variant="outline" className="text-[10px]">
                    {t}
                  </Badge>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
