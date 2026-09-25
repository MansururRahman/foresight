import Link from "next/link";

import { PhaseBadge, StatusBadge } from "@/components/project/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { shortDate } from "@/lib/format";
import type { ProjectOut } from "@/lib/types";

export function ProjectCard({ project, workspaceId }: { project: ProjectOut; workspaceId: string }) {
  const needsGrading = project.status === "closed" && project.session && !project.session.fully_graded_at;
  return (
    <Link href={`/w/${workspaceId}/p/${project.id}`} className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
      <Card className="h-full transition-colors hover:bg-accent/40">
        <CardContent className="space-y-2 p-4">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-medium leading-snug">{project.title}</h3>
            <StatusBadge status={project.status} />
          </div>
          {project.description && <p className="line-clamp-2 text-sm text-muted-foreground">{project.description}</p>}
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            {project.session ? <PhaseBadge phase={project.session.phase} /> : <span>No pre-mortem yet</span>}
            {needsGrading && (
              <Badge variant="destructive" className="text-[10px]">
                needs grading
              </Badge>
            )}
            {project.planned_end && <span>· due {shortDate(project.planned_end)}</span>}
          </div>
          {project.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {project.tags.map((t) => (
                <Badge key={t} variant="secondary" className="text-[10px]">
                  {t}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
