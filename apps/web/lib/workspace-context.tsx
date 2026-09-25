"use client";

import { createContext, useContext } from "react";

import type { WorkspaceOut, WorkspaceRole } from "@/lib/types";

export type WorkspaceContextValue = {
  workspace: WorkspaceOut;
  myRole: WorkspaceRole;
  isAdmin: boolean;
  isOwner: boolean;
};

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspaceContext(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspaceContext must be used inside a workspace layout");
  return ctx;
}
