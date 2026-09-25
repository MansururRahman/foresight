import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { SuggestionsPanel } from "@/components/session/SuggestionsPanel";
import { _resetForTests, setAccessToken } from "@/lib/auth";
import { API_URL } from "@/lib/env";
import type { SuggestionsOut } from "@/lib/types";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  _resetForTests();
});
afterAll(() => server.close());

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const EMPTY: SuggestionsOut = { query: { tags: ["vendor"], matched_projects: 0 }, suggestions: [] };
const FULL: SuggestionsOut = {
  query: { tags: ["vendor"], matched_projects: 3 },
  suggestions: [
    {
      statement: "Vendor API not ready by integration start",
      score: 1.42,
      materialization_rate: 0.75,
      occurrences: 4,
      mean_predicted_probability: 41.7,
      tags: ["vendor", "integration"],
      sources: [
        { risk_id: "r1", project_id: "p1", project_title: "Payments v2", project_similarity: 0.71, outcome: "yes", mean_predicted_probability: 35, origin: "participant", closed_at: null },
        { risk_id: "r2", project_id: "p2", project_title: "Warehouse API", project_similarity: 0.39, outcome: "yes", mean_predicted_probability: null, origin: "surprise", closed_at: null },
      ],
    },
    {
      statement: "Rate limits hit during load test",
      score: 0.5,
      materialization_rate: 0.5,
      occurrences: 2,
      mean_predicted_probability: 65,
      tags: ["vendor"],
      sources: [
        { risk_id: "r3", project_id: "p1", project_title: "Payments v2", project_similarity: 0.71, outcome: "no", mean_predicted_probability: 65, origin: "participant", closed_at: null },
      ],
    },
  ],
};

describe("SuggestionsPanel", () => {
  it("renders nothing when no similar projects exist", async () => {
    let called = 0;
    server.use(
      http.post(`${API_URL}/v1/workspaces/ws1/suggestions`, () => {
        called += 1;
        return HttpResponse.json(EMPTY);
      }),
    );
    setAccessToken("tok");
    const { container } = wrap(<SuggestionsPanel workspaceId="ws1" title="Vendor work" tags={["vendor"]} debounceMs={0} />);
    await waitFor(() => expect(called).toBe(1));
    expect(screen.queryByText(/suggested risks/i)).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders suggestions with provenance and a surprise badge", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API_URL}/v1/workspaces/ws1/suggestions`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(FULL);
      }),
    );
    setAccessToken("tok");
    wrap(<SuggestionsPanel workspaceId="ws1" title="Vendor work" description="Billing" tags={["Vendor"]} debounceMs={0} />);
    expect(await screen.findByText(/suggested risks/i)).toBeInTheDocument();
    expect(screen.getByText(/from 3 similar past projects/i)).toBeInTheDocument();
    expect(screen.getByText("Vendor API not ready by integration start")).toBeInTheDocument();
    expect(screen.getByText(/materialized 3 of 4/i)).toBeInTheDocument();
    expect(screen.getByText(/predicted 42%/i)).toBeInTheDocument();
    expect(screen.getByText(/surprise last time/i)).toBeInTheDocument();
    expect(screen.getByText(/Payments v2, Warehouse API/)).toBeInTheDocument();
    // Second suggestion has no surprise source: exactly one badge overall.
    expect(screen.getAllByText(/surprise last time/i)).toHaveLength(1);
    expect(body).toMatchObject({ title: "Vendor work", description: "Billing", tags: ["Vendor"] });
  });

  it("does not query when there is nothing to search with", async () => {
    setAccessToken("tok");
    const { container } = wrap(<SuggestionsPanel workspaceId="ws1" title="" tags={[]} debounceMs={0} />);
    await new Promise((r) => setTimeout(r, 30));
    expect(container).toBeEmptyDOMElement();
  });
});
