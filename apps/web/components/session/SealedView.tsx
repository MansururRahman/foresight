"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { num, pct100 } from "@/lib/format";
import { useResults } from "@/lib/queries/sessions";
import type { ProjectOut, SessionOut } from "@/lib/types";

function Histogram({ buckets }: { buckets: number[] }) {
  const max = Math.max(1, ...buckets);
  return (
    <div className="flex h-6 items-end gap-px" aria-label={`Vote distribution: ${buckets.join(", ")}`} role="img">
      {buckets.map((b, i) => (
        <span key={i} className="w-1.5 rounded-sm bg-foreground/70" style={{ height: `${Math.max(2, (b / max) * 100)}%`, opacity: b ? 1 : 0.15 }} />
      ))}
    </div>
  );
}

function AgreementBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded bg-muted">
        <div className="h-full bg-foreground/70" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="tabular-nums text-xs text-muted-foreground">{num(value)}</span>
    </div>
  );
}

export function SealedView({ session, project, workspaceId }: { session: SessionOut; project: ProjectOut; workspaceId: string }) {
  const { data, isLoading, error } = useResults(session.id);
  if (isLoading) return <Skeleton className="h-64" />;
  if (error || !data) return <p className="text-sm text-destructive">Could not load the results.</p>;
  const p = data.participation;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">Sealed results</CardTitle>
              <CardDescription>
                {p.participants} participants · {p.voters_complete} complete · {p.voters_partial} partial · {p.voters_none} did not vote. Individual votes are never shown.
              </CardDescription>
            </div>
            {session.me.is_facilitator && (
              <Button render={<Link href={`/w/${workspaceId}/p/${project.id}/closeout`} />} variant={project.status === "closed" ? "default" : "outline"}>
                {session.fully_graded_at ? "Review grading" : "Grade outcomes"}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Risk</TableHead>
                <TableHead className="text-right">Mean</TableHead>
                <TableHead className="text-right">Median</TableHead>
                <TableHead>Agreement</TableHead>
                <TableHead className="text-right">Impact</TableHead>
                <TableHead className="text-right">Score</TableHead>
                <TableHead>Votes</TableHead>
                <TableHead className="text-right">You</TableHead>
                <TableHead>Outcome</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.risks.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="max-w-md">
                    <div className="text-sm">{r.statement}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {r.origin === "suggestion" && (
                        <Badge variant="outline" className="text-[10px]">
                          from history
                        </Badge>
                      )}
                      {r.tags.map((t) => (
                        <Badge key={t} variant="secondary" className="text-[10px]">
                          {t}
                        </Badge>
                      ))}
                    </div>
                    {r.merged_from.length > 0 && (
                      <details className="mt-1 text-xs text-muted-foreground">
                        <summary className="cursor-pointer">Merged {r.merged_from.length}</summary>
                        <ul className="list-inside list-disc">
                          {r.merged_from.map((m) => (
                            <li key={m.id}>{m.statement}</li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{pct100(r.aggregates?.mean_probability)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct100(r.aggregates?.median_probability)}</TableCell>
                  <TableCell>{r.aggregates ? <AgreementBar value={r.aggregates.agreement} /> : "—"}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.aggregates?.mean_impact, 1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.aggregates?.risk_score, 2)}</TableCell>
                  <TableCell>
                    {r.histogram ? (
                      <Histogram buckets={r.histogram} />
                    ) : (
                      <span className="text-xs text-muted-foreground" title="Hidden with fewer than three voters">
                        —
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {r.my_vote ? `${r.my_vote.probability}% · ${r.my_vote.impact}` : "—"}
                  </TableCell>
                  <TableCell>
                    {r.grading ? (
                      <Badge variant={r.grading.outcome === "no" ? "secondary" : "destructive"}>{r.grading.outcome}</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">ungraded</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
