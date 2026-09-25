"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { MyVotes, ResultsOut, RiskList, RiskOut, SessionOut, SessionTransitionResult } from "@/lib/types";

export const sessionKeys = {
  one: (id: string) => ["session", id] as const,
  risks: (id: string) => ["risks", id] as const,
  myVotes: (id: string) => ["my-votes", id] as const,
  results: (id: string) => ["results", id] as const,
};

function invalidateSession(qc: ReturnType<typeof useQueryClient>, sessionId: string, projectId?: string) {
  void qc.invalidateQueries({ queryKey: sessionKeys.one(sessionId) });
  void qc.invalidateQueries({ queryKey: sessionKeys.risks(sessionId) });
  void qc.invalidateQueries({ queryKey: sessionKeys.myVotes(sessionId) });
  void qc.invalidateQueries({ queryKey: sessionKeys.results(sessionId) });
  if (projectId) void qc.invalidateQueries({ queryKey: ["project", projectId] });
}

export function useSession(id: string | undefined) {
  return useQuery({
    queryKey: sessionKeys.one(id ?? ""),
    queryFn: () => apiFetch<SessionOut>(`/v1/sessions/${id}`),
    enabled: Boolean(id),
    // Participants see phase changes made by the facilitator without reloading.
    refetchInterval: (q) => (q.state.data && q.state.data.phase !== "sealed" ? 5000 : false),
  });
}

export function useTransitionSession(sessionId: string, projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (to: "merge" | "vote" | "sealed") =>
      apiFetch<SessionTransitionResult>(`/v1/sessions/${sessionId}/transition`, { method: "POST", body: { to } }),
    onSuccess: () => invalidateSession(qc, sessionId, projectId),
  });
}

export function useRisks(sessionId: string | undefined, phase?: string) {
  return useQuery({
    queryKey: [...sessionKeys.risks(sessionId ?? ""), phase] as const,
    queryFn: () => apiFetch<RiskList>(`/v1/sessions/${sessionId}/risks`),
    enabled: Boolean(sessionId),
    retry: false,
  });
}

export function useCreateRisk(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (statement: string) => apiFetch<RiskOut>(`/v1/sessions/${sessionId}/risks`, { method: "POST", body: { statement } }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}

export type RiskPatchBody = { statement?: string; tags?: string[]; duplicate_of?: string | null };

export function usePatchRisk(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ riskId, body }: { riskId: string; body: RiskPatchBody }) =>
      apiFetch<RiskOut>(`/v1/risks/${riskId}`, { method: "PATCH", body }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}

export function useDeleteRisk(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (riskId: string) => apiFetch<void>(`/v1/risks/${riskId}`, { method: "DELETE" }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}

export function useAdoptRisk(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { source_risk_id: string; statement?: string; tags?: string[] }) =>
      apiFetch<RiskOut>(`/v1/sessions/${sessionId}/risks/adopt`, { method: "POST", body }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}

export function useMyVotes(sessionId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: sessionKeys.myVotes(sessionId ?? ""),
    queryFn: () => apiFetch<MyVotes>(`/v1/sessions/${sessionId}/votes/me`),
    enabled: Boolean(sessionId) && enabled,
  });
}

export function usePutVotes(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (votes: { risk_id: string; probability: number; impact: number }[]) =>
      apiFetch<MyVotes>(`/v1/sessions/${sessionId}/votes`, { method: "PUT", body: { votes } }),
    onSuccess: (data) => {
      qc.setQueryData(sessionKeys.myVotes(sessionId), data);
      void qc.invalidateQueries({ queryKey: sessionKeys.one(sessionId) });
    },
  });
}

export function useResults(sessionId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: sessionKeys.results(sessionId ?? ""),
    queryFn: () => apiFetch<ResultsOut>(`/v1/sessions/${sessionId}/results`),
    enabled: Boolean(sessionId) && enabled,
  });
}

export function useAddParticipants(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (user_ids: string[]) => apiFetch<SessionOut>(`/v1/sessions/${sessionId}/participants`, { method: "POST", body: { user_ids } }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}

export function useRemoveParticipant(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => apiFetch<void>(`/v1/sessions/${sessionId}/participants/${userId}`, { method: "DELETE" }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}

export function useSetFacilitator(sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (facilitator_id: string) => apiFetch<SessionOut>(`/v1/sessions/${sessionId}`, { method: "PATCH", body: { facilitator_id } }),
    onSuccess: () => invalidateSession(qc, sessionId),
  });
}
