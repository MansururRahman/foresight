import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { WorkspaceOut } from "@/lib/types";

export function WorkspaceCard({ workspace }: { workspace: WorkspaceOut }) {
  return (
    <Link href={`/w/${workspace.id}`} className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <Card className="transition-colors hover:bg-accent/40">
        <CardContent className="flex items-center justify-between p-4">
          <div>
            <div className="font-medium">{workspace.name}</div>
            <div className="text-xs text-muted-foreground">/{workspace.slug}</div>
          </div>
          <Badge variant="secondary">{workspace.my_role}</Badge>
        </CardContent>
      </Card>
    </Link>
  );
}
