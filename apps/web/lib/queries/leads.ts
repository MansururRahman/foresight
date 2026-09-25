"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import type { LeadCreate } from "@/lib/types";

export function useSubmitLead() {
  return useMutation({
    mutationFn: (body: LeadCreate) =>
      apiFetch<{ status: "received" }>("/v1/leads", { method: "POST", body, auth: false }),
  });
}
