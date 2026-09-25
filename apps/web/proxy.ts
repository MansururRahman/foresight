import { NextResponse, type NextRequest } from "next/server";

import { safeNext } from "@/lib/nav";

const HINT_COOKIE = "fs_session";

/**
 * Optimistic redirects based on the non-httpOnly session hint cookie.
 * Real authorization happens in the API (401 -> refresh -> redirect in AuthProvider).
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasHint = request.cookies.get(HINT_COOKIE)?.value === "1";

  if (pathname === "/" && hasHint) {
    const url = request.nextUrl.clone();
    url.pathname = "/w";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (pathname.startsWith("/w") && !hasHint) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  if ((pathname === "/login" || pathname === "/register") && hasHint) {
    const url = request.nextUrl.clone();
    url.pathname = safeNext(request.nextUrl.searchParams.get("next")).split("?")[0];
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/w/:path*", "/login", "/register"],
};
