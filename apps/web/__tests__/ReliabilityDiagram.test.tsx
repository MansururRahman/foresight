import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReliabilityDiagram } from "@/components/charts/ReliabilityDiagram";
import type { Bin } from "@/lib/types";

function bins(): Bin[] {
  return Array.from({ length: 10 }, (_, i) => {
    const n = i % 3 === 0 ? 7 : 2;
    const reliable = n >= 5;
    return {
      index: i,
      range: [i * 10, i === 9 ? 100 : i * 10 + 9],
      n,
      mean_predicted: i / 10 + 0.05,
      observed: reliable ? i / 10 : null,
      reliable,
    };
  });
}

describe("ReliabilityDiagram", () => {
  it("renders one dot per bin and marks unreliable bins", () => {
    const { container } = render(<ReliabilityDiagram bins={bins()} />);
    const dots = container.querySelectorAll('[data-testid="bin-dot"]');
    expect(dots).toHaveLength(10);
    const reliable = Array.from(dots).filter((d) => d.getAttribute("data-reliable") === "true");
    expect(reliable).toHaveLength(4); // bins 0, 3, 6, 9
    expect(container.querySelector('[data-testid="diagonal"]')).not.toBeNull();
  });

  it("renders an empty state when there are no predictions", () => {
    const empty = bins().map((b) => ({ ...b, n: 0, mean_predicted: null, observed: null, reliable: false }));
    const { getByText } = render(<ReliabilityDiagram bins={empty} />);
    expect(getByText(/no graded predictions yet/i)).toBeInTheDocument();
  });
});
