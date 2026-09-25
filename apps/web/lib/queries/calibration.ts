"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { UserCalibration, WorkspaceCalibration } from "@/lib/types";

export function useMyCalibration(ws: string) {
  return useQuery({
    queryKey: ["calibration", ws, "me"] as const,
    queryFn: () => apiFetch<UserCalibration>(`/v1/workspaces/${ws}/calibration/me`),
    enabled: Boolean(ws),
  });
}

export function useUserCalibration(ws: string, userId: string | null) {
  return useQuery({
    queryKey: ["calibration", ws, "user", userId] as const,
    queryFn: () => apiFetch<UserCalibration>(`/v1/workspaces/${ws}/calibration/users/${userId}`),
    enabled: Boolean(ws) && Boolean(userId),
  });
}

export function useWorkspaceCalibration(ws: string) {
  return useQuery({
    queryKey: ["calibration", ws, "workspace"] as const,
    queryFn: () => apiFetch<WorkspaceCalibration>(`/v1/workspaces/${ws}/calibration`),
    enabled: Boolean(ws),
  });
}
