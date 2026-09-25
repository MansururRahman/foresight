import { expect, test } from "@playwright/test";

import { loginViaUi } from "./helpers";

// Requires the demo seed: docker compose run --rm api python -m app.seed
test("the seeded demo workspace shows a populated calibration dashboard", async ({ page }) => {
  await loginViaUi(page, "ada@demo.local");
  await page.getByRole("link", { name: /Demo Team/ }).click();
  await expect(page.getByRole("heading", { name: "Demo Team" })).toBeVisible();

  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("heading", { name: "Team calibration" })).toBeVisible();
  await expect(page.getByText(/96 graded predictions/)).toBeVisible();

  const brierTile = page.locator("div", { hasText: /^Brier score/ }).first();
  await expect(brierTile).not.toContainText("—");
  await expect(page.getByTestId("bin-dot")).toHaveCount(10);
  await expect(page.getByText(/Visible to admins only/)).toBeVisible(); // Ada is the owner

  await page.getByRole("link", { name: "Me", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My calibration" })).toBeVisible();
  await expect(page.getByText(/32 graded predictions/)).toBeVisible();
});
