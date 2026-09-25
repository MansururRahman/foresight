import { expect, test } from "@playwright/test";

import { registerViaUi, uniqueEmail } from "./helpers";

test("workspace -> project -> pre-mortem: collect, merge, vote, seal", async ({ page }) => {
  page.on("dialog", (d) => d.accept());
  await registerViaUi(page, "E2E Facilitator", uniqueEmail("fac"));

  // Workspace
  await page.getByRole("button", { name: "New workspace" }).click();
  await page.getByLabel("Name").fill("E2E Team");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(page).toHaveURL(/\/w\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "E2E Team" })).toBeVisible();

  // Project
  await page.getByRole("link", { name: "New project" }).click();
  await page.getByLabel("Title").fill("Vendor API integration");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("heading", { name: "Vendor API integration" })).toBeVisible();

  // Session: collect
  await page.getByRole("button", { name: "Start pre-mortem session" }).click();
  await page.getByRole("link", { name: "Open session" }).click();
  await expect(page.getByRole("heading", { name: "Pre-mortem session" })).toBeVisible();
  const newRisk = page.getByLabel("New risk");
  await newRisk.fill("Vendor API not ready by integration start");
  await page.getByRole("button", { name: "Add risk" }).click();
  await expect(page.getByText("Vendor API not ready by integration start")).toBeVisible();
  await newRisk.fill("Finance unavailable for UAT");
  await page.getByRole("button", { name: "Add risk" }).click();
  await expect(page.getByText("Finance unavailable for UAT")).toBeVisible();

  // Merge
  await page.getByRole("button", { name: /Advance to merge/ }).click();
  await expect(page.getByText("Merge and tag", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Advance to vote/ }).click();

  // Vote (autosave), then seal
  await expect(page.getByText("Rate each risk", { exact: true })).toBeVisible();
  await page.getByLabel("Probability for Vendor API not ready by integration start").fill("60");
  await page.getByLabel("Probability for Finance unavailable for UAT").fill("25");
  await expect(page.getByText("Saved 2 of 2")).toBeVisible();
  await page.getByRole("button", { name: "Seal session" }).click();
  await expect(page.getByText("Sealed results", { exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "60%" }).first()).toBeVisible();
});
