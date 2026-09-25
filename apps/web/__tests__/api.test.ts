import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ApiError, UNAUTHORIZED_EVENT, UnauthorizedError, apiFetch } from "@/lib/api";
import { _resetForTests, getAccessToken, setAccessToken } from "@/lib/auth";
import { API_URL, AUTH_URL } from "@/lib/env";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  _resetForTests();
});
afterAll(() => server.close());

describe("apiFetch", () => {
  it("attaches the in-memory bearer token", async () => {
    let seen: string | null = null;
    server.use(
      http.get(`${API_URL}/v1/me`, ({ request }) => {
        seen = request.headers.get("authorization");
        return HttpResponse.json({ ok: true });
      }),
    );
    setAccessToken("tok1");
    const result = await apiFetch<{ ok: boolean }>("/v1/me");
    expect(result).toEqual({ ok: true });
    expect(seen).toBe("Bearer tok1");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    const calls: string[] = [];
    let refreshCredentials: RequestCredentials | null = null;
    server.use(
      http.get(`${API_URL}/v1/me`, ({ request }) => {
        const auth = request.headers.get("authorization");
        calls.push(auth ?? "none");
        if (auth !== "Bearer tok2") {
          return HttpResponse.json(
            { error: { code: "invalid_token", message: "expired", details: {} } },
            { status: 401 },
          );
        }
        return HttpResponse.json({ user: { id: "u1" } });
      }),
      http.post(`${AUTH_URL}/auth/refresh`, ({ request }) => {
        refreshCredentials = request.credentials;
        return HttpResponse.json({
          access_token: "tok2",
          token_type: "bearer",
          expires_in: 900,
          user: { id: "u1", email: "a@b.c", name: "A" },
        });
      }),
    );
    setAccessToken("tok1");
    const result = await apiFetch<{ user: { id: string } }>("/v1/me");
    expect(result.user.id).toBe("u1");
    expect(calls).toEqual(["Bearer tok1", "Bearer tok2"]);
    expect(refreshCredentials).toBe("include");
    expect(getAccessToken()).toBe("tok2");
  });

  it("deduplicates concurrent refreshes", async () => {
    let refreshes = 0;
    server.use(
      http.get(`${API_URL}/v1/a`, ({ request }) =>
        request.headers.get("authorization") === "Bearer fresh"
          ? HttpResponse.json({ a: 1 })
          : HttpResponse.json({ error: { code: "invalid_token", message: "", details: {} } }, { status: 401 }),
      ),
      http.get(`${API_URL}/v1/b`, ({ request }) =>
        request.headers.get("authorization") === "Bearer fresh"
          ? HttpResponse.json({ b: 2 })
          : HttpResponse.json({ error: { code: "invalid_token", message: "", details: {} } }, { status: 401 }),
      ),
      http.post(`${AUTH_URL}/auth/refresh`, async () => {
        refreshes += 1;
        await new Promise((r) => setTimeout(r, 20));
        return HttpResponse.json({ access_token: "fresh", token_type: "bearer", expires_in: 900, user: { id: "u1", email: "a@b.c", name: "A" } });
      }),
    );
    setAccessToken("stale");
    const [a, b] = await Promise.all([apiFetch<{ a: number }>("/v1/a"), apiFetch<{ b: number }>("/v1/b")]);
    expect(a).toEqual({ a: 1 });
    expect(b).toEqual({ b: 2 });
    expect(refreshes).toBe(1);
  });

  it("throws UnauthorizedError and dispatches an event when refresh fails", async () => {
    server.use(
      http.get(`${API_URL}/v1/me`, () =>
        HttpResponse.json({ error: { code: "invalid_token", message: "", details: {} } }, { status: 401 }),
      ),
      http.post(`${AUTH_URL}/auth/refresh`, () =>
        HttpResponse.json({ error: { code: "invalid_refresh", message: "", details: {} } }, { status: 401 }),
      ),
    );
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);
    setAccessToken("tok1");
    await expect(apiFetch("/v1/me")).rejects.toBeInstanceOf(UnauthorizedError);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("surfaces the error envelope as ApiError", async () => {
    server.use(
      http.post(`${API_URL}/v1/workspaces`, () =>
        HttpResponse.json(
          { error: { code: "validation_error", message: "Request validation failed", details: { errors: [] } } },
          { status: 422 },
        ),
      ),
    );
    setAccessToken("tok1");
    const err = (await apiFetch("/v1/workspaces", { method: "POST", body: { name: "" } }).catch(
      (e: unknown) => e,
    )) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("validation_error");
    expect(err.message).toBe("Request validation failed");
  });

  it("sends JSON bodies and returns undefined for 204", async () => {
    let received: unknown = null;
    server.use(
      http.delete(`${API_URL}/v1/projects/p1`, async ({ request }) => {
        received = request.headers.get("content-type");
        return new HttpResponse(null, { status: 204 });
      }),
      http.put(`${API_URL}/v1/x`, async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    setAccessToken("tok1");
    await expect(apiFetch("/v1/projects/p1", { method: "DELETE" })).resolves.toBeUndefined();
    await apiFetch("/v1/x", { method: "PUT", body: { votes: [1] } });
    expect(received).toEqual({ votes: [1] });
  });
});
