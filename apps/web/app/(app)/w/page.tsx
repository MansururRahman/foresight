"use client";

import { useAuth } from "@/lib/auth-context";

// Placeholder landing page; the workspace list is built in the next task.
export default function WorkspacesPage() {
  const { user } = useAuth();
  return (
    <div>
      <h1 className="text-xl font-semibold">Welcome, {user?.name}</h1>
      <p className="mt-2 text-sm text-muted-foreground">Your workspaces will appear here.</p>
    </div>
  );
}
