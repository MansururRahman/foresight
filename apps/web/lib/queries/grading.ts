"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { CloseoutOut, GradingOutcome, RiskOut } from "@/lib/types";

export const closeoutKey = (projectId: string) => ["closeout", projectId] as const;

function invalidateCloseout(qc: ReturnType<typeof useQueryClient>, projectId: string) {
  void qc.invalidateQueries({ queryKey: closeoutKey(projectId) });
  void qc.invalidateQueries({ queryKey: ["project", projectId] });
  void qc.invalidateQueries({ queryKey: ["report", projectId] });
  void qc.invalidateQueries({ queryKey: ["projects"] });
  void qc.invalidateQueries({ queryKey: ["calibration"] });
}

export function useCloseout(projectId: string) {
  return useQuery({
    queryKey: closeoutKey(projectId),
    queryFn: () => apiFetch<CloseoutOut>(`/v1/projects/${projectId}/closeout`),
    enabled: Boolean(projectId),
  });
}

export type GradingIn = { risk_id: string; outcome: GradingOutcome; note: string };

export function usePutGradings(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (gradings: GradingIn[]) =>
      apiFetch<CloseoutOut>(`/v1/projects/${projectId}/gradings`, { method: "PUT", body: { gradings } }),
    onSuccess: (data) => {
      qc.setQueryData(closeoutKey(projectId), data);
      invalidateCloseout(qc, projectId);
    },
  });
}

export function useDeleteGrading(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (riskId: string) => apiFetch<void>(`/v1/gradings/${riskId}`, { method: "DELETE" }),
    onSuccess: () => invalidateCloseout(qc, projectId),
  });
}

export function useAddSurprise(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { statement: string; tags: string[] }) =>
      apiFetch<RiskOut>(`/v1/projects/${projectId}/surprises`, { method: "POST", body }),
    onSuccess: () => invalidateCloseout(qc, projectId),
  });
}

export function useDeleteSurprise(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (riskId: string) => apiFetch<void>(`/v1/risks/${riskId}`, { method: "DELETE" }),
    onSuccess: () => invalidateCloseout(qc, projectId),
  });
}
