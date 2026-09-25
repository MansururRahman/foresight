/**
 * Only follow a `?next=` target that stays on this origin.
 * Rejects protocol-relative URLs (`//host`), absolute URLs, schemes and backslash tricks.
 */
export function safeNext(next: string | null | undefined, fallback = "/w"): string {
  if (!next) return fallback;
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return fallback;
  return next;
}
