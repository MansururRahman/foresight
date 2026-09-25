import Link from "next/link";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { num, signed } from "@/lib/format";
import type { WorkspaceCalibration } from "@/lib/types";

export function MembersTable({ members, workspaceId }: { members: NonNullable<WorkspaceCalibration["members"]>; workspaceId: string }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Member</TableHead>
          <TableHead className="text-right">Graded</TableHead>
          <TableHead className="text-right">Brier</TableHead>
          <TableHead className="text-right">Bias</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((m) => (
          <TableRow key={m.user.id}>
            <TableCell>
              <Link href={`/w/${workspaceId}/me?user=${m.user.id}`} className="underline-offset-4 hover:underline">
                {m.user.name}
              </Link>
            </TableCell>
            <TableCell className="text-right tabular-nums">{m.n_graded}</TableCell>
            <TableCell className="text-right tabular-nums">{m.brier === null ? <span className="text-muted-foreground">needs 10</span> : num(m.brier, 3)}</TableCell>
            <TableCell className="text-right tabular-nums">{signed(m.bias)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
