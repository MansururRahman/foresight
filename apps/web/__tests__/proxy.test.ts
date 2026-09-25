// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "@/proxy";

const BASE = "http://localhost:3000";

function req(path: string, cookie?: string) {
  return new NextRequest(`${BASE}${path}`, cookie ? { headers: { cookie } } : undefined);
}

describe("proxy", () => {
  it("runs on the landing page", () => {
    expect(config.matcher).toContain("/");
  });

  it("sends signed-in visitors from / to /w", () => {
    const res = proxy(req("/?ref=linkedin", "fs_session=1"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(`${BASE}/w`);
  });

  it("lets anonymous visitors see the landing page", () => {
    const res = proxy(req("/?ref=linkedin"));
    expect(res.headers.get("location")).toBeNull();
  });

  it("still sends anonymous visitors from /w to /login", () => {
    const res = proxy(req("/w"));
    expect(res.headers.get("location")).toBe(`${BASE}/login?next=%2Fw`);
  });
});
