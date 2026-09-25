export function SampleNotice({ n, needed, sufficient }: { n: number; needed: number; sufficient: boolean }) {
  if (sufficient) return null;
  return (
    <p className="rounded-md border border-dashed bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
      <span className="tabular-nums">
        {n} of {needed}
      </span>{" "}
      graded predictions so far. Scores appear once {needed} predictions have been graded, so a lucky guess or two cannot masquerade as skill.
    </p>
  );
}
