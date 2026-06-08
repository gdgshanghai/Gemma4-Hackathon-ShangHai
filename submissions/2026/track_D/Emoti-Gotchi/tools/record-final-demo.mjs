import { chromium } from "file:///C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs";
import path from "node:path";
import fs from "node:fs/promises";

const outputDir = path.resolve("videos/raw");
await fs.mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: {
    dir: outputDir,
    size: { width: 1440, height: 900 },
  },
  colorScheme: "light",
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);

async function clickText(text) {
  const button = page.getByRole("button", { name: text });
  await button.scrollIntoViewIfNeeded();
  await button.click();
}

async function focusText(text, waitMs) {
  const target = page.getByText(text, { exact: false }).first();
  if (await target.count()) await target.scrollIntoViewIfNeeded();
  await pause(waitMs);
}

async function clickTab(name) {
  await page.keyboard.press("Escape");
  let clicked = await page.evaluate((label) => {
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    const target = tabs.find((item) => item.textContent?.trim() === label);
    if (!target) return false;
    target.click();
    return true;
  }, name);
  if (!clicked) {
    await page.reload({ waitUntil: "networkidle" });
    clicked = await page.evaluate((label) => {
      const tabs = [...document.querySelectorAll('[role="tab"]')];
      const target = tabs.find((item) => item.textContent?.trim() === label);
      if (!target) return false;
      target.click();
      return true;
    }, name);
  }
  if (!clicked) {
    console.error("Tab recovery failed", {
      name,
      url: page.url(),
      title: await page.title(),
      text: (await page.locator("body").innerText()).slice(0, 500),
    });
    throw new Error(`Tab not found: ${name}`);
  }
  await pause(300);
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
  if (!clicked) {
    console.warn(`Button not found, continuing recording: ${label}`);
    return false;
  }
  await pause(300);
  return true;
}

const video = page.video();
try {
  await page.goto("http://127.0.0.1:8080", { waitUntil: "networkidle" });
  await pause(7000);

  // Opening and architecture overview.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(9000);

  // Normal child-support scene.
  await clickText(/A\. Regulated sharing/);
  await pause(3000);
  await focusText("Embodied co-regulation", 9000);

  // Hidden-distress scene and realtime response.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await clickText(/B\. 'I am fine' self-correction/);
  await pause(3000);
  await focusText("Embodied co-regulation", 10000);

  // Technical comparison.
  await clickTab("Technical Proof");
  await pause(2500);
  await focusText("Text-only Rules", 14000);
  await page.evaluate(() => window.scrollBy({ top: 650, behavior: "smooth" }));
  await pause(9000);

  // Anger scene.
  await clickTab("Live Demo");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  const input = page.getByRole("textbox");
  await input.fill("Leave me alone. I am angry and I do not want to talk.");
  await page.getByRole("button", { name: "Run on-device response" }).click();
  await pause(3000);
  await focusText("Embodied co-regulation", 10000);

  // High-risk safety scene.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await clickText(/C\. Safety meltdown/);
  await pause(4000);
  await focusText("What to do now", 9000);

  // Family climate and explicit safety boundary.
  await clickTab("Family Climate");
  await pause(3000);
  await focusText("7-Day Family Climate Forecast", 14000);
  await focusText("Gemma 4 Family Climate Outlook", 12000);
  await focusText("Weather metaphor stops where life safety begins", 10000);

  // Authorized professional-support handoff preview.
  await clickButtonLabel("Prepare authorized handoff");
  await pause(7000);
  await clickButtonLabel("Authorize professional support handoff");
  await pause(12000);
  await clickButtonLabel("Close handoff preview");
  await pause(2500);

  // Climate outlook refresh; local preview remains responsive while cloud runs.
  await focusText("Gemma 4 Family Climate Outlook", 1000);
  await clickButtonLabel("Refresh climate outlook");
  await pause(12000);

  // Technical proof close.
  await clickTab("Technical Proof");
  await pause(3000);
  await focusText("Text-only Rules", 10000);
  await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }));
  await pause(8000);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(8000);
} finally {
  await context.close();
  await browser.close();
}
const rawPath = await video.path();
const finalPath = path.resolve("videos/Emoti-Gotchi_final_demo_raw.webm");
await fs.copyFile(rawPath, finalPath);
console.log(finalPath);
