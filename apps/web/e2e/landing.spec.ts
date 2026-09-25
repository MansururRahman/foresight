import { expect, test } from "@playwright/test";

import { loginViaUi } from "./helpers";

test("anonymous visitors see the landing page and can apply", async ({ page }) => {
  await page.goto("/?ref=e2e");
  await expect(page.getByRole("heading", { level: 1, name: /Your team saw it coming/ })).toBeVisible();

  await page.getByRole("link", { name: "Apply as design partner" }).first().click();
  await page.getByLabel("Name", { exact: true }).fill("E2E Lead");
  await page.getByLabel("Work email").fill(`lead-${Date.now()}@foresight-e2e.dev`);
  await page.getByLabel("Company").fill("E2E Consulting");
  await page.getByLabel("Role", { exact: true }).fill("Delivery lead");
  await page.getByLabel("Team size").selectOption("11-50");
  await page.getByRole("button", { name: "Apply", exact: true }).click();

  await expect(page.getByRole("status")).toContainText("Thanks, we'll reach out");
});

test("signed-in users opening / land in the app", async ({ page }) => {
  await loginViaUi(page, "ada@demo.local");
  await page.goto("/");
  await expect(page).toHaveURL(/\/w$/);
});
