"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { MemberOut, TagStat, WorkspaceOut, WorkspaceRole } from "@/lib/types";

export const workspaceKeys = {
  all: ["workspaces"] as const,
  one: (id: string) => ["workspace", id] as const,
  members: (id: string) => ["members", id] as const,
  tags: (id: string) => ["tags", id] as const,
};

export function useWorkspaces() {
  return useQuery({
    queryKey: workspaceKeys.all,
    queryFn: () => apiFetch<{ items: WorkspaceOut[] }>("/v1/workspaces").then((r) => r.items),
  });
}

export function useWorkspace(id: string) {
  return useQuery({
    queryKey: workspaceKeys.one(id),
    queryFn: () => apiFetch<WorkspaceOut>(`/v1/workspaces/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string }) => apiFetch<WorkspaceOut>("/v1/workspaces", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.all }),
  });
}

export function useMembers(ws: string) {
  return useQuery({
    queryKey: workspaceKeys.members(ws),
    queryFn: () => apiFetch<{ items: MemberOut[] }>(`/v1/workspaces/${ws}/members`).then((r) => r.items),
    enabled: Boolean(ws),
  });
}

export function useAddMember(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; role: WorkspaceRole }) =>
      apiFetch<MemberOut>(`/v1/workspaces/${ws}/members`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.members(ws) }),
  });
}

export function useSetRole(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: WorkspaceRole }) =>
      apiFetch<MemberOut>(`/v1/workspaces/${ws}/members/${userId}`, { method: "PUT", body: { role } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: workspaceKeys.members(ws) }),
  });
}

export function useRemoveMember(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => apiFetch<void>(`/v1/workspaces/${ws}/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: workspaceKeys.members(ws) });
      void qc.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}

export function useTags(ws: string) {
  return useQuery({
    queryKey: workspaceKeys.tags(ws),
    queryFn: () => apiFetch<{ items: TagStat[] }>(`/v1/workspaces/${ws}/tags`).then((r) => r.items),
    enabled: Boolean(ws),
  });
}
