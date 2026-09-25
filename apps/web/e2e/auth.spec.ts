import { expect, test } from "@playwright/test";

import { registerViaUi, uniqueEmail } from "./helpers";

test("register, survive a reload, sign out, and get redirected when signed out", async ({ page }) => {
  await registerViaUi(page, "E2E Ada", uniqueEmail("ada"));
  await expect(page.getByRole("heading", { name: "Workspaces" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Workspaces" })).toBeVisible();

  await page.getByRole("button", { name: "Account menu" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);

  await page.goto("/w");
  await expect(page).toHaveURL(/\/login\?next=/);
});

test("rejects a wrong password with a readable error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("ada@demo.local");
  await page.getByLabel("Password").fill("definitely-wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /incorrect/i })).toBeVisible();
});
