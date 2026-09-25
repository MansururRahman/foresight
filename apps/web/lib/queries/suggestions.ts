"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type { SuggestionsOut } from "@/lib/types";

export type SuggestionInput = {
  title: string;
  description?: string;
  tags: string[];
  exclude_project_id?: string;
};

/** Returns `value` after it has been stable for `delayMs`. A delay of 0 passes the value through. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  const serialized = JSON.stringify(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), Math.max(delayMs, 0));
    return () => clearTimeout(t);
    // `serialized` stands in for `value` so structurally equal objects do not retrigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serialized, delayMs]);
  return delayMs <= 0 ? value : debounced;
}

export function useSuggestions(ws: string, input: SuggestionInput, enabled: boolean) {
  return useQuery({
    queryKey: ["suggestions", ws, input] as const,
    queryFn: () =>
      apiFetch<SuggestionsOut>(`/v1/workspaces/${ws}/suggestions`, {
        method: "POST",
        body: {
          title: input.title,
          description: input.description ?? "",
          tags: input.tags,
          exclude_project_id: input.exclude_project_id ?? null,
        },
      }),
    enabled: Boolean(ws) && enabled,
    staleTime: 30_000,
  });
}
