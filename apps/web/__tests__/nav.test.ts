import { describe, expect, it } from "vitest";

import { safeNext } from "@/lib/nav";

describe("safeNext", () => {
  it("accepts same-origin paths", () => {
    expect(safeNext("/w/abc?x=1")).toBe("/w/abc?x=1");
    expect(safeNext("/w")).toBe("/w");
  });

  it("falls back for anything that could leave the origin", () => {
    expect(safeNext("//evil.example")).toBe("/w");
    expect(safeNext("http://evil.example/w")).toBe("/w");
    expect(safeNext("/\\evil.example")).toBe("/w");
    expect(safeNext("javascript:alert(1)")).toBe("/w");
    expect(safeNext("w/abc")).toBe("/w");
  });

  it("falls back for empty input and honours a custom fallback", () => {
    expect(safeNext(null)).toBe("/w");
    expect(safeNext("", "/login")).toBe("/login");
  });
});
