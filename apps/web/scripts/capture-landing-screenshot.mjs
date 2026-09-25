// Captures the seeded demo's calibration dashboard for the landing page.
// Needs the running, seeded stack. Usage: node scripts/capture-landing-screenshot.mjs
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
// fileURLToPath handles Windows drive letters and the spaces in this repo's OneDrive path.
const OUT = fileURLToPath(new URL("../public/landing/calibration.png", import.meta.url));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, colorScheme: "light" });
await page.goto(`${BASE}/login`);
await page.getByLabel("Email").fill("ada@demo.local");
await page.getByLabel("Password").fill("demo1234");
await page.getByRole("button", { name: "Sign in" }).click();
await page.waitForURL(/\/w/);
await page.getByRole("link", { name: /Demo Team/ }).click();
await page.getByRole("link", { name: "Dashboard" }).click();
await page.getByRole("heading", { name: "Team calibration" }).waitFor();
await page.getByTestId("bin-dot").first().waitFor();
await page.waitForTimeout(500); // let chart animations settle
await page.screenshot({ path: OUT });
await browser.close();
console.log(`saved ${OUT}`);
