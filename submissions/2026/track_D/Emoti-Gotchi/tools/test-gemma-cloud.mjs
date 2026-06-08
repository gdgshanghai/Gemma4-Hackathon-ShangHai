import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

function loadLocalEnv() {
  const envPath = resolve(".env.local");
  if (!existsSync(envPath)) return;

  const lines = readFileSync(envPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const equalIndex = trimmed.indexOf("=");
    if (equalIndex === -1) continue;
    const key = trimmed.slice(0, equalIndex).trim();
    const value = trimmed.slice(equalIndex + 1).trim().replace(/^["']|["']$/g, "");
    if (!process.env[key]) process.env[key] = value;
  }
}

loadLocalEnv();

const apiKey = process.env.GEMINI_API_KEY;
const model = process.env.GEMINI_MODEL || "gemma-4-26b-a4b-it";
const proxy = process.env.ALL_PROXY || process.env.HTTPS_PROXY || process.env.HTTP_PROXY;

if (!apiKey) {
  console.error("Missing GEMINI_API_KEY. Create .env.local first.");
  process.exit(1);
}

const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
const startedAt = Date.now();
const requestBody = {
  contents: [
    {
      role: "user",
      parts: [
        {
          text: "Return one short sentence confirming the Emoti-Gotchi Gemma cloud adapter is reachable.",
        },
      ],
    },
  ],
  generationConfig: {
    temperature: 0.1,
    maxOutputTokens: 80,
  },
};

if (proxy?.startsWith("socks5://")) {
  const proxyAddress = proxy.replace("socks5://", "");
  const curl = spawnSync(
    "curl.exe",
    [
      "--silent",
      "--show-error",
      "--socks5-hostname",
      proxyAddress,
      "--connect-timeout",
      "30",
      "-H",
      "content-type: application/json",
      "-H",
      `x-goog-api-key: ${apiKey}`,
      "-d",
      JSON.stringify(requestBody),
      endpoint,
    ],
    { encoding: "utf8" },
  );

  if (curl.status !== 0) {
    console.error(`Gemma cloud test failed through SOCKS5 proxy ${proxyAddress}.`);
    console.error(curl.stderr || curl.stdout || "curl failed without output");
    process.exit(1);
  }

  const elapsed = Date.now() - startedAt;
  const payload = JSON.parse(curl.stdout);
  const text = payload?.candidates?.[0]?.content?.parts?.[0]?.text ?? "(no text returned)";
  if (payload?.error) {
    console.error(`Gemma cloud test failed for model ${model}.`);
    console.error(JSON.stringify(payload.error, null, 2));
    process.exit(1);
  }

  console.log(`Gemma cloud adapter reachable.`);
  console.log(`Model: ${model}`);
  console.log(`Proxy: ${proxyAddress}`);
  console.log(`Latency: ${elapsed} ms`);
  console.log(`Response: ${text}`);
  process.exit(0);
}

let response;
try {
  response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": apiKey },
    body: JSON.stringify(requestBody),
  });
} catch (error) {
  console.error(`Gemma cloud test could not connect to Google API for model ${model}.`);
  console.error("Your API key was hidden. Check network/proxy access to generativelanguage.googleapis.com.");
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}

const elapsed = Date.now() - startedAt;

if (!response.ok) {
  const body = await response.text();
  console.error(`Gemma cloud test failed for model ${model}: ${response.status}`);
  console.error(body.slice(0, 700));
  process.exit(1);
}

const payload = await response.json();
const text = payload?.candidates?.[0]?.content?.parts?.[0]?.text ?? "(no text returned)";

console.log(`Gemma cloud adapter reachable.`);
console.log(`Model: ${model}`);
console.log(`Latency: ${elapsed} ms`);
console.log(`Response: ${text}`);
