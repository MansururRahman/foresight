/**
 * Typed fetch wrapper for the domain API. Attaches the bearer token, and on a 401 performs one
 * silent refresh and retries once. If the refresh fails the session is over: an
 * UnauthorizedError is thrown and `fs:unauthorized` is dispatched so the AuthProvider can redirect.
 */
import type { ZodType } from "zod";

import { getAccessToken, refresh } from "./auth";
import { API_URL } from "./env";

export const UNAUTHORIZED_EVENT = "fs:unauthorized";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class UnauthorizedError extends ApiError {
  constructor() {
    super(401, "unauthorized", "Your session has expired. Please sign in again.");
    this.name = "UnauthorizedError";
  }
}

export type ApiInit<T> = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  schema?: ZodType<T>;
  signal?: AbortSignal;
};

async function readError(res: Response): Promise<ApiError> {
  try {
    const data = (await res.json()) as { error?: { code?: string; message?: string; details?: Record<string, unknown> } };
    const e = data.error ?? {};
    return new ApiError(res.status, e.code ?? "api_error", e.message ?? res.statusText, e.details ?? {});
  } catch {
    return new ApiError(res.status, "api_error", res.statusText);
  }
}

function sessionOver(): never {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  throw new UnauthorizedError();
}

export async function apiFetch<T = unknown>(path: string, init: ApiInit<T> = {}): Promise<T> {
  const { method = "GET", body, schema, signal } = init;

  const send = (token: string | null) =>
    fetch(`${API_URL}${path}`, {
      method,
      signal,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  let res = await send(getAccessToken());
  if (res.status === 401) {
    const token = await refresh();
    if (!token) sessionOver();
    res = await send(token);
    if (res.status === 401) sessionOver();
  }
  if (!res.ok) throw await readError(res);
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json();
  return schema ? schema.parse(data) : (data as T);
}
