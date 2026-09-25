"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { UNAUTHORIZED_EVENT } from "./api";
import { getCurrentUser, hasSessionHint, logout as doLogout, refresh, type User } from "./auth";

type Status = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: Status;
  user: User | null;
  /** Called by the login/register forms after the auth library adopted the tokens. */
  signedIn: (user: User) => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    let cancelled = false;
    (async () => {
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
        setStatus("anonymous");
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

  const value = useMemo(() => ({ status, user, signedIn, signOut }), [status, user, signedIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
