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
const video = page.video();
await page.goto("http://127.0.0.1:8080/mascot-ad.html", { waitUntil: "networkidle" });
await page.waitForTimeout(36500);
await context.close();
await browser.close();

const rawPath = await video.path();
const finalPath = path.resolve("videos/03_Emoti-Gotchi_product_film.webm");
await fs.copyFile(rawPath, finalPath);
console.log(finalPath);
