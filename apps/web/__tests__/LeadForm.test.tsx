import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { LeadForm, readSource } from "@/components/landing/LeadForm";
import { API_URL } from "@/lib/env";

const nav = vi.hoisted(() => ({ params: new URLSearchParams() }));
vi.mock("next/navigation", () => ({ useSearchParams: () => nav.params }));

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  nav.params = new URLSearchParams();
});
afterAll(() => server.close());

function wrap() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LeadForm />
    </QueryClientProvider>,
  );
}

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Name"), "Ada Lovelace");
  await user.type(screen.getByLabelText("Work email"), "Ada@Analytical.co");
  await user.type(screen.getByLabelText("Company"), "Analytical Ltd");
  await user.type(screen.getByLabelText("Role"), "Delivery lead");
  await user.selectOptions(screen.getByLabelText("Team size"), "11-50");
}

describe("readSource", () => {
  it("prefers ref, falls back to utm_source, truncates to 100", () => {
    expect(readSource(new URLSearchParams("ref=linkedin&utm_source=x"))).toBe("linkedin");
    expect(readSource(new URLSearchParams("utm_source=newsletter"))).toBe("newsletter");
    expect(readSource(new URLSearchParams(""))).toBeNull();
    expect(readSource(new URLSearchParams(`ref=${"a".repeat(150)}`))).toHaveLength(100);
  });
});

describe("LeadForm", () => {
  it("shows validation messages and sends nothing when empty", async () => {
    const user = userEvent.setup();
    wrap();
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Tell us your name")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid work email")).toBeInTheDocument();
    expect(screen.getByText("Pick a team size")).toBeInTheDocument();
  });

  it("submits the expected body and shows the thank-you message", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${API_URL}/v1/leads`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ status: "received" }, { status: 202 });
      }),
    );
    nav.params = new URLSearchParams("ref=linkedin");
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Thanks, we'll reach out");
    expect(body).toEqual({
      name: "Ada Lovelace",
      email: "ada@analytical.co",
      company: "Analytical Ltd",
      role: "Delivery lead",
      team_size: "11-50",
      story: null,
      source: "linkedin",
      website: "",
    });
  });

  it("sends a single request on double click", async () => {
    let calls = 0;
    server.use(
      http.post(`${API_URL}/v1/leads`, async () => {
        calls += 1;
        await new Promise((r) => setTimeout(r, 50));
        return HttpResponse.json({ status: "received" }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.dblClick(screen.getByRole("button", { name: "Apply" }));
    await screen.findByRole("status");
    expect(calls).toBe(1);
  });

  it("keeps what the visitor typed when the network fails", async () => {
    server.use(http.post(`${API_URL}/v1/leads`, () => HttpResponse.error()));
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByLabelText("Name")).toHaveValue("Ada Lovelace");
    expect(screen.getByRole("button", { name: "Apply" })).toBeEnabled();
  });

  it("shows the rate-limit message on 429", async () => {
    server.use(
      http.post(`${API_URL}/v1/leads`, () =>
        HttpResponse.json({ error: { code: "rate_limited", message: "slow", details: {} } }, { status: 429 }),
      ),
    );
    const user = userEvent.setup();
    wrap();
    await fillValid(user);
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many attempts");
  });

  it("accepts a 2000-character story and rejects 2001", async () => {
    const user = userEvent.setup();
    server.use(http.post(`${API_URL}/v1/leads`, () => HttpResponse.json({ status: "received" }, { status: 202 })));
    wrap();
    await fillValid(user);
    const story = screen.getByLabelText(/What went wrong/);
    await user.click(story);
    await user.paste("é".repeat(2001));
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Keep it under 2000 characters")).toBeInTheDocument();
    await user.type(story, "{Backspace}");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });

  it("hides the honeypot from people and assistive tech", () => {
    wrap();
    expect(screen.queryByRole("textbox", { name: /website/i })).toBeNull();
  });
});
