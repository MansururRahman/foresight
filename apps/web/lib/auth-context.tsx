"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { UNAUTHORIZED_EVENT } from "./api";
import { getCurrentUser, getRefreshFailure, hasSessionHint, logout as doLogout, refresh, type User } from "./auth";

/** `offline`: a session probably exists but the auth service could not be reached. */
type Status = "loading" | "authenticated" | "anonymous" | "offline";

type AuthContextValue = {
  status: Status;
  user: User | null;
  /** Called by the login/register forms after the auth library adopted the tokens. */
  signedIn: (user: User) => void;
  signOut: () => Promise<void>;
  /** Retry the silent refresh after an outage. */
  retry: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  const restore = useCallback(async () => {
    if (!hasSessionHint()) {
      setStatus("anonymous");
      return;
    }
    const token = await refresh();
    if (token) {
      setUser(getCurrentUser());
      setStatus("authenticated");
    } else {
      setStatus(getRefreshFailure() === "network" ? "offline" : "anonymous");
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!hasSessionHint()) {
        if (!cancelled) setStatus("anonymous");
        return;
      }
      const token = await refresh();
      if (cancelled) return;
      if (token) {
        setUser(getCurrentUser());
        setStatus("authenticated");
      } else {
        setStatus(getRefreshFailure() === "network" ? "offline" : "anonymous");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setStatus("anonymous");
      const next = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [pathname, router]);

  const signedIn = useCallback((u: User) => {
    setUser(u);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(async () => {
    await doLogout();
    setUser(null);
    setStatus("anonymous");
    router.replace("/login");
  }, [router]);

  const retry = useCallback(async () => {
    setStatus("loading");
    await restore();
  }, [restore]);

  const value = useMemo(() => ({ status, user, signedIn, signOut, retry }), [status, user, signedIn, signOut, retry]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
