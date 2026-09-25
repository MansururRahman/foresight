"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { ProjectOut, ProjectPage, ProjectReport, ProjectStatus, TransitionResult } from "@/lib/types";

export type ProjectFilters = { status?: ProjectStatus; tag?: string; q?: string; include_archived?: boolean };

export const projectKeys = {
  list: (ws: string, filters: ProjectFilters = {}) => ["projects", ws, filters] as const,
  one: (id: string) => ["project", id] as const,
  report: (id: string) => ["report", id] as const,
};

export type ProjectInput = {
  title: string;
  description: string;
  tags: string[];
  planned_start: string | null;
  planned_end: string | null;
};

function qs(filters: ProjectFilters): string {
  const p = new URLSearchParams();
  if (filters.status) p.set("status", filters.status);
  if (filters.tag) p.set("tag", filters.tag);
  if (filters.q) p.set("q", filters.q);
  if (filters.include_archived) p.set("include_archived", "true");
  p.set("limit", "100");
  return `?${p.toString()}`;
}

export function useProjects(ws: string, filters: ProjectFilters = {}) {
  return useQuery({
    queryKey: projectKeys.list(ws, filters),
    queryFn: () => apiFetch<ProjectPage>(`/v1/workspaces/${ws}/projects${qs(filters)}`).then((r) => r.items),
    enabled: Boolean(ws),
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.one(id),
    queryFn: () => apiFetch<ProjectOut>(`/v1/projects/${id}`),
    enabled: Boolean(id),
  });
}

export function useCreateProject(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectInput) => apiFetch<ProjectOut>(`/v1/workspaces/${ws}/projects`, { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", ws] }),
  });
}

export function usePatchProject(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<ProjectInput>) => apiFetch<ProjectOut>(`/v1/projects/${id}`, { method: "PATCH", body }),
    onSuccess: (p) => {
      qc.setQueryData(projectKeys.one(id), p);
      void qc.invalidateQueries({ queryKey: ["projects", p.workspace_id] });
    },
  });
}

export function useTransitionProject(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (to: "active" | "closed") =>
      apiFetch<TransitionResult>(`/v1/projects/${id}/transition`, { method: "POST", body: { to } }),
    onSuccess: (r) => {
      qc.setQueryData(projectKeys.one(id), r.project);
      void qc.invalidateQueries({ queryKey: ["projects", r.project.workspace_id] });
      void qc.invalidateQueries({ queryKey: projectKeys.report(id) });
    },
  });
}

export function useArchiveProject(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (archived: boolean) =>
      apiFetch<ProjectOut>(`/v1/projects/${id}/${archived ? "archive" : "unarchive"}`, { method: "POST" }),
    onSuccess: (p) => {
      qc.setQueryData(projectKeys.one(id), p);
      void qc.invalidateQueries({ queryKey: ["projects", p.workspace_id] });
    },
  });
}

export function useDeleteProject(ws: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/v1/projects/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", ws] }),
  });
}

export function useProjectReport(id: string, enabled = true) {
  return useQuery({
    queryKey: projectKeys.report(id),
    queryFn: () => apiFetch<ProjectReport>(`/v1/projects/${id}/report`),
    enabled: Boolean(id) && enabled,
  });
}
