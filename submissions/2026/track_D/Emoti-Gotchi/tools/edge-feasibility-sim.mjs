const hardwareProfiles = [
  {
    name: "Toy MCU only",
    memoryGb: 0.5,
    computeScore: 0.12,
    accelerator: "none",
  },
  {
    name: "Raspberry Pi 4 8GB",
    memoryGb: 8,
    computeScore: 0.65,
    accelerator: "CPU",
  },
  {
    name: "Raspberry Pi 5 8GB",
    memoryGb: 8,
    computeScore: 1,
    accelerator: "CPU",
  },
  {
    name: "Android phone / tablet",
    memoryGb: 8,
    computeScore: 2.2,
    accelerator: "GPU/NPU",
  },
  {
    name: "Edge SoC with NPU",
    memoryGb: 8,
    computeScore: 3,
    accelerator: "NPU",
  },
];

const modelProfiles = [
  {
    name: "Deterministic safety only",
    memoryGb: 0.05,
    baseTtftMs: 20,
    tokensPerSecondAtScore1: 0,
  },
  {
    name: "Acoustic + ASR tiny + safety",
    memoryGb: 0.35,
    baseTtftMs: 180,
    tokensPerSecondAtScore1: 0,
  },
  {
    name: "Gemma 4 E2B-style quantized",
    memoryGb: 3.2,
    baseTtftMs: 1500,
    tokensPerSecondAtScore1: 8,
  },
  {
    name: "Gemma 4 4B-style quantized",
    memoryGb: 5.8,
    baseTtftMs: 2800,
    tokensPerSecondAtScore1: 4,
  },
];

const acceptance = {
  maxFeatureMs: 200,
  maxEndToEndMs: 2500,
  maxMemoryGb: 5.5,
};

function estimate(profile, model) {
  const fitsMemory = model.memoryGb <= Math.min(profile.memoryGb * 0.72, acceptance.maxMemoryGb);
  const ttftMs = Math.round(model.baseTtftMs / Math.max(profile.computeScore, 0.1));
  const endToEndMs = model.name.includes("Gemma") ? ttftMs + 250 : ttftMs;
  const tokensPerSecond = model.tokensPerSecondAtScore1
    ? Number((model.tokensPerSecondAtScore1 * profile.computeScore).toFixed(1))
    : "n/a";
  const passLatency = model.name.includes("Gemma")
    ? endToEndMs <= acceptance.maxEndToEndMs
    : endToEndMs <= acceptance.maxFeatureMs;
  const verdict = fitsMemory && passLatency ? "PASS" : fitsMemory ? "LATENCY_RISK" : "MEMORY_RISK";

  return {
    hardware: profile.name,
    accelerator: profile.accelerator,
    model: model.name,
    memoryGb: model.memoryGb,
    ttftMs,
    endToEndMs,
    tokensPerSecond,
    verdict,
  };
}

const rows = hardwareProfiles.flatMap((profile) =>
  modelProfiles.map((model) => estimate(profile, model)),
);

console.log("Emoti-Gotchi edge feasibility simulation");
console.log("Note: this is a planning budget, not a real Gemma 4 benchmark.");
console.log("");
console.table(rows);
console.log("Recommended MVP path:");
console.log("1. Keep deterministic safety audit always-on and local.");
console.log("2. Validate acoustic feature extraction locally first.");
console.log("3. Use Raspberry Pi 4 8GB as a stress test and Raspberry Pi 5 or stronger hardware as the safer demo target.");
console.log("4. If latency misses the target, move Gemma reasoning to a paired phone or base station while keeping raw audio local.");
