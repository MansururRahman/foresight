import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { GradingTable, type GradingMap } from "@/components/grading/GradingTable";
import type { RiskOut } from "@/lib/types";

function risk(id: string, statement: string, mean: number): RiskOut {
  return {
    id,
    session_id: "s1",
    project_id: "p1",
    statement,
    tags: [],
    origin: "participant",
    duplicate_of: null,
    source_risk_id: null,
    author: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    aggregates: {
      vote_count: 2,
      mean_probability: mean,
      median_probability: mean,
      probability_stddev: 5,
      agreement: 0.9,
      mean_impact: 3,
      risk_score: 1.5,
    },
    merged_from: [],
    my_vote: null,
    grading: null,
  };
}

const RISKS = [risk("r1", "Vendor API not ready", 45), risk("r2", "Finance unavailable for UAT", 25)];

function Harness({ initial = {} as GradingMap }) {
  const [value, setValue] = useState<GradingMap>(initial);
  return (
    <div>
      <GradingTable risks={RISKS} value={value} onChange={setValue} />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </div>
  );
}

describe("GradingTable", () => {
  it("shows progress and emits the updated grading map when an outcome is chosen", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    expect(screen.getByText(/graded 0 of 2/i)).toBeInTheDocument();
    expect(screen.getByText("45%")).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: /vendor api not ready: yes/i }));
    expect(screen.getByTestId("value")).toHaveTextContent('{"r1":{"outcome":"yes","note":""}}');
    expect(screen.getByText(/graded 1 of 2/i)).toBeInTheDocument();
  });

  it("keeps the note when the outcome changes and records notes", async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ r2: { outcome: "no", note: "" } }} />);
    await user.type(screen.getByRole("textbox", { name: /note for finance unavailable/i }), "1 of 2 wks");
    expect(screen.getByTestId("value")).toHaveTextContent('"r2":{"outcome":"no","note":"1 of 2 wks"}');
    await user.click(screen.getByRole("radio", { name: /finance unavailable for uat: partial/i }));
    expect(screen.getByTestId("value")).toHaveTextContent('"r2":{"outcome":"partial","note":"1 of 2 wks"}');
  });
});
