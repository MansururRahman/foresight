import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { VoteRow, type VoteValue } from "@/components/session/VoteRow";
import type { RiskOut } from "@/lib/types";

const RISK: RiskOut = {
  id: "r1",
  session_id: "s1",
  project_id: "p1",
  statement: "Vendor API not ready",
  tags: ["vendor"],
  origin: "participant",
  duplicate_of: null,
  source_risk_id: null,
  author: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  aggregates: null,
  merged_from: [],
  my_vote: null,
  grading: null,
};

function Harness({ initial }: { initial: VoteValue | null }) {
  const [value, setValue] = useState<VoteValue | null>(initial);
  return (
    <div>
      <VoteRow risk={RISK} value={value} onChange={setValue} />
      <output data-testid="value">{value ? `${value.probability}/${value.impact}` : "none"}</output>
    </div>
  );
}

describe("VoteRow", () => {
  it("keeps the number input and slider in sync and clamps to 0..100", async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ probability: 45, impact: 3 }} />);
    const number = screen.getByRole("spinbutton", { name: /probability/i });
    expect(number).toHaveValue(45);
    // Base UI keeps the thumb visibility:hidden until it can measure the track, which jsdom never does.
    expect(screen.getByRole("slider", { hidden: true })).toHaveAttribute("aria-valuenow", "45");

    await user.clear(number);
    await user.type(number, "150");
    await user.tab();
    expect(screen.getByTestId("value")).toHaveTextContent("100/3");
    expect(screen.getByRole("slider", { hidden: true })).toHaveAttribute("aria-valuenow", "100");
  });

  it("starts unanswered and defaults impact to 3 when a probability is entered", async () => {
    const user = userEvent.setup();
    render(<Harness initial={null} />);
    expect(screen.getByTestId("value")).toHaveTextContent("none");
    const number = screen.getByRole("spinbutton", { name: /probability/i });
    await user.type(number, "70");
    expect(screen.getByTestId("value")).toHaveTextContent("70/3");
  });

  it("changes impact with the rating buttons", async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ probability: 20, impact: 2 }} />);
    await user.click(screen.getByRole("radio", { name: /impact 5/i }));
    expect(screen.getByTestId("value")).toHaveTextContent("20/5");
    expect(screen.getByRole("radio", { name: /impact 5/i })).toBeChecked();
  });
});
