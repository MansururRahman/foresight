"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

function NavLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground",
        active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground",
      )}
      aria-current={active ? "page" : undefined}
    >
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth();
  const pathname = usePathname() ?? "";
  const params = useParams<{ workspaceId?: string }>();
  const ws = params?.workspaceId;

  const nav = ws
    ? [
        { href: `/w/${ws}`, label: "Projects", match: (p: string) => p === `/w/${ws}` || p.startsWith(`/w/${ws}/p`) },
        { href: `/w/${ws}/members`, label: "Members", match: (p: string) => p.startsWith(`/w/${ws}/members`) },
        { href: `/w/${ws}/dashboard`, label: "Dashboard", match: (p: string) => p.startsWith(`/w/${ws}/dashboard`) },
        { href: `/w/${ws}/me`, label: "Me", match: (p: string) => p.startsWith(`/w/${ws}/me`) },
      ]
    : [];

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4">
          <Link href="/w" className="font-semibold tracking-tight">
            Foresight
          </Link>
          <nav className="flex items-center gap-1" aria-label="Workspace">
            {nav.map((n) => (
              <NavLink key={n.href} href={n.href} label={n.label} active={n.match(pathname)} />
            ))}
          </nav>
          <div className="ml-auto">
            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button variant="ghost" size="sm" aria-label="Account menu" />}
              >
                {user?.name ?? "Account"}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel className="font-normal">
                  <div className="text-sm font-medium">{user?.name}</div>
                  <div className="text-xs text-muted-foreground">{user?.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem render={<Link href="/w" />}>All workspaces</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => void signOut()}>Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
    </div>
  );
}
