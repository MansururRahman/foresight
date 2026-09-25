/**
 * Auth client for the separate auth service.
 *
 * The access token lives only in memory (XSS-resistant); the refresh token is an httpOnly cookie
 * scoped to the auth origin, so a page reload re-establishes the session with one silent refresh.
 * A non-httpOnly hint cookie lets the Next.js proxy redirect unauthenticated navigations early.
 */
import { AUTH_URL } from "./env";

export type User = { id: string; email: string; name: string };
type TokenOut = { access_token: string; token_type: string; expires_in: number; user: User };

const HINT_COOKIE = "fs_session";

let accessToken: string | null = null;
let currentUser: User | null = null;
let inflightRefresh: Promise<string | null> | null = null;

export class AuthError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "AuthError";
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getCurrentUser(): User | null {
  return currentUser;
}

export function setSessionHint(on: boolean): void {
  if (typeof document === "undefined") return;
  document.cookie = on
    ? `${HINT_COOKIE}=1; Path=/; SameSite=Lax`
    : `${HINT_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function hasSessionHint(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie.split(";").some((c) => c.trim() === `${HINT_COOKIE}=1`);
}

async function readError(res: Response): Promise<AuthError> {
  try {
    const data = (await res.json()) as { error?: { code?: string; message?: string; details?: Record<string, unknown> } };
    const e = data.error ?? {};
    return new AuthError(res.status, e.code ?? "auth_error", e.message ?? res.statusText, e.details ?? {});
  } catch {
    return new AuthError(res.status, "auth_error", res.statusText);
  }
}

async function authPost(path: string, body?: unknown): Promise<TokenOut> {
  const res = await fetch(`${AUTH_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json", ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await readError(res);
  return (await res.json()) as TokenOut;
}

function adopt(tokens: TokenOut): User {
  accessToken = tokens.access_token;
  currentUser = tokens.user;
  setSessionHint(true);
  return tokens.user;
}

function clearSession(): void {
  accessToken = null;
  currentUser = null;
  setSessionHint(false);
}

export async function login(email: string, password: string): Promise<User> {
  return adopt(await authPost("/auth/login", { email, password }));
}

export async function register(email: string, name: string, password: string): Promise<User> {
  return adopt(await authPost("/auth/register", { email, name, password }));
}

/** Exchange the refresh cookie for a new access token. Concurrent callers share one request. */
export function refresh(): Promise<string | null> {
  if (inflightRefresh) return inflightRefresh;
  inflightRefresh = (async () => {
    try {
      const tokens = await authPost("/auth/refresh");
      adopt(tokens);
      return tokens.access_token;
    } catch {
      clearSession();
      return null;
    } finally {
      inflightRefresh = null;
    }
  })();
  return inflightRefresh;
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${AUTH_URL}/auth/logout`, { method: "POST", credentials: "include" });
  } catch {
    // Local state is cleared regardless; the server-side family expires on its own.
  }
  clearSession();
}

/** Test hook: reset module state between tests. */
export function _resetForTests(): void {
  clearSession();
  inflightRefresh = null;
}
