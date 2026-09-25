"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { num, pct100, signed } from "@/lib/format";
import { useProjectReport } from "@/lib/queries/projects";

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const OUTCOME_LABEL = { yes: "happened", no: "did not happen", partial: "partly happened" } as const;

export function ProjectReport({ projectId }: { projectId: string }) {
  const { data, isLoading } = useProjectReport(projectId);
  if (isLoading || !data) return null;
  const s = data.summary;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Predicted vs actual</CardTitle>
        <CardDescription>
          {s.n_graded} of {s.n_canonical} risks graded · {s.n_voters} voters · {s.n_predictions} predictions
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Tile label="Expected to materialize" value={num(s.expected_materialized, 1)} hint="sum of mean probabilities" />
          <Tile label="Actually materialized" value={num(s.actual_materialized, 1)} hint="partial counts half" />
          <Tile label="Project Brier" value={num(s.project_brier, 3)} hint="0 is perfect, lower is better" />
        </div>
        {data.biggest_misses.length > 0 && (
          <div>
            <h4 className="mb-2 text-sm font-medium">Biggest misses</h4>
            <ul className="space-y-1 text-sm">
              {data.biggest_misses.map((m) => (
                <li key={m.risk_id} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                  <span>{m.statement}</span>
                  <span className="whitespace-nowrap text-muted-foreground tabular-nums">
                    predicted {pct100(m.mean_predicted)} · {m.outcome ? OUTCOME_LABEL[m.outcome] : "ungraded"} · miss {signed(m.miss)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Risk</TableHead>
              <TableHead className="text-right">Predicted</TableHead>
              <TableHead className="text-right">Agreement</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead className="text-right">Miss</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.risks.map((r) => (
              <TableRow key={r.risk_id}>
                <TableCell>
                  <div>{r.statement}</div>
                  {r.note && <div className="text-xs text-muted-foreground">{r.note}</div>}
                </TableCell>
                <TableCell className="text-right tabular-nums">{pct100(r.mean_predicted)}</TableCell>
                <TableCell className="text-right tabular-nums">{num(r.agreement)}</TableCell>
                <TableCell>{r.outcome ? <Badge variant="outline">{OUTCOME_LABEL[r.outcome]}</Badge> : <span className="text-muted-foreground">—</span>}</TableCell>
                <TableCell className="text-right tabular-nums">{signed(r.miss)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {data.surprises.length > 0 && (
          <div>
            <h4 className="mb-2 text-sm font-medium">Surprises nobody predicted</h4>
            <ul className="list-inside list-disc text-sm">
              {data.surprises.map((x) => (
                <li key={x.risk_id}>{x.statement}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
