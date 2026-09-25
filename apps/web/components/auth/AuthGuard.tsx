"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth-context";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") {
      router.replace(`/login?next=${encodeURIComponent(pathname ?? "/w")}`);
    }
  }, [status, router, pathname]);

  if (status !== "authenticated") {
    return (
      <div className="mx-auto max-w-5xl space-y-4 p-6" aria-busy="true" aria-live="polite">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }
  return <>{children}</>;
}
