import { chromium } from "file:///C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs";
import path from "node:path";
import fs from "node:fs/promises";

const outputDir = path.resolve("videos/raw");
await fs.mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: outputDir, size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);
const video = page.video();

async function focus(text, waitMs) {
  const target = page.getByText(text, { exact: false }).first();
  await target.scrollIntoViewIfNeeded();
  await pause(waitMs);
}

async function clickButtonLabel(label) {
  const clicked = await page.evaluate((text) => {
    const target = [...document.querySelectorAll("button")].find(
      (item) => item.textContent?.trim() === text,
    );
    if (!target) return false;
    target.click();
    return true;
  }, label);
  if (!clicked) throw new Error(`Button not found: ${label}`);
  await pause(300);
}

try {
  await page.goto("http://127.0.0.1:8080", { waitUntil: "networkidle" });
  await pause(5000);
  await page.getByRole("tab", { name: "Family Climate" }).click();
  await pause(2500);
  await focus("7-Day Family Climate Forecast", 16000);
  await focus("Gemma 4 Family Climate Outlook", 15000);
  await clickButtonLabel("Refresh climate outlook");
  await pause(12000);
  await focus("Weather metaphor stops where life safety begins", 12000);
  await clickButtonLabel("Prepare authorized handoff");
  await pause(8000);
  await clickButtonLabel("Authorize professional support handoff");
  await pause(14000);
  await clickButtonLabel("Close handoff preview");
  await pause(3000);
  await page.getByRole("tab", { name: "Technical Proof" }).click();
  await pause(2500);
  await focus("Text-only Rules", 12000);
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
  await pause(10000);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(10000);
} finally {
  await context.close();
  await browser.close();
}

const rawPath = await video.path();
const finalPath = path.resolve("videos/Emoti-Gotchi_family_climate_raw.webm");
await fs.copyFile(rawPath, finalPath);
console.log(finalPath);
