import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import {
  AuthError,
  _resetForTests,
  getAccessToken,
  getRefreshFailure,
  hasSessionHint,
  login,
  logout,
  refresh,
  register,
} from "@/lib/auth";
import { AUTH_URL } from "@/lib/env";

const server = setupServer();
const USER = { id: "u1", email: "ada@demo.local", name: "Ada" };
const TOKENS = { access_token: "tok1", token_type: "bearer", expires_in: 900, user: USER };

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  _resetForTests();
});
afterAll(() => server.close());

describe("auth library", () => {
  it("login stores the token, returns the user and sets the session hint cookie", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${AUTH_URL}/auth/login`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(TOKENS);
      }),
    );
    const user = await login("Ada@Demo.local", "demo1234");
    expect(user).toEqual(USER);
    expect(body).toEqual({ email: "Ada@Demo.local", password: "demo1234" });
    expect(getAccessToken()).toBe("tok1");
    expect(hasSessionHint()).toBe(true);
    expect(document.cookie).toContain("fs_session=1");
  });

  it("register behaves like login", async () => {
    server.use(http.post(`${AUTH_URL}/auth/register`, () => HttpResponse.json(TOKENS, { status: 201 })));
    const user = await register("ada@demo.local", "Ada", "demo1234");
    expect(user.name).toBe("Ada");
    expect(getAccessToken()).toBe("tok1");
  });

  it("login surfaces the API error code", async () => {
    server.use(
      http.post(`${AUTH_URL}/auth/login`, () =>
        HttpResponse.json({ error: { code: "invalid_credentials", message: "Email or password is incorrect", details: {} } }, { status: 401 }),
      ),
    );
    const err = (await login("a@b.c", "nope").catch((e: unknown) => e)) as AuthError;
    expect(err).toBeInstanceOf(AuthError);
    expect(err.code).toBe("invalid_credentials");
    expect(getAccessToken()).toBeNull();
  });

  it("logout revokes, clears the token and the hint cookie", async () => {
    server.use(
      http.post(`${AUTH_URL}/auth/login`, () => HttpResponse.json(TOKENS)),
      http.post(`${AUTH_URL}/auth/logout`, () => new HttpResponse(null, { status: 204 })),
    );
    await login("ada@demo.local", "demo1234");
    await logout();
    expect(getAccessToken()).toBeNull();
    expect(hasSessionHint()).toBe(false);
  });

  it("refresh returns null (and clears state) when the cookie is rejected", async () => {
    server.use(
      http.post(`${AUTH_URL}/auth/refresh`, () =>
        HttpResponse.json({ error: { code: "invalid_refresh", message: "", details: {} } }, { status: 401 }),
      ),
    );
    document.cookie = "fs_session=1; Path=/";
    expect(await refresh()).toBeNull();
    expect(hasSessionHint()).toBe(false);
  });

  it("refresh returns the new token and user", async () => {
    server.use(http.post(`${AUTH_URL}/auth/refresh`, () => HttpResponse.json({ ...TOKENS, access_token: "tok9" })));
    expect(await refresh()).toBe("tok9");
    expect(getAccessToken()).toBe("tok9");
  });
});

describe("refresh failure modes", () => {
  it("keeps the session hint on a network error so a transient outage does not sign the user out", async () => {
    server.use(http.post(`${AUTH_URL}/auth/refresh`, () => HttpResponse.error()));
    document.cookie = "fs_session=1; Path=/";
    expect(await refresh()).toBeNull();
    expect(getAccessToken()).toBeNull();
    expect(hasSessionHint()).toBe(true);
    expect(getRefreshFailure()).toBe("network");
  });

  it("reports an unauthorized failure after a 401", async () => {
    server.use(
      http.post(`${AUTH_URL}/auth/refresh`, () =>
        HttpResponse.json({ error: { code: "invalid_refresh", message: "", details: {} } }, { status: 401 }),
      ),
    );
    document.cookie = "fs_session=1; Path=/";
    expect(await refresh()).toBeNull();
    expect(getRefreshFailure()).toBe("unauthorized");
    expect(hasSessionHint()).toBe(false);
  });
});
