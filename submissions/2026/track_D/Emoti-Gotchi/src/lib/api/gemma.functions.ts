import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

import { getServerConfig } from "../config.server";
import { postJsonToGoogleModel } from "../gemma-cloud.server";

const familyEventSchema = z.object({
  id: z.string().min(1),
  timestamp: z.string().min(1),
  stateVersion: z.number().int().nonnegative(),
  emotion: z.enum(["happy", "sad", "anxious", "angry", "calm", "neutral"]),
  anxietyBand: z.enum(["low", "medium", "high", "critical"]),
  triggerCategory: z.string().min(1),
  modalityRelationship: z.enum(["aligned", "conflicting", "insufficient"]),
  interactionStrategy: z.enum([
    "shared_joy",
    "quiet_presence",
    "co_regulate",
    "validate_and_contain",
    "safety_hold",
  ]),
  guardianActionSelected: z
    .enum(["quiet_presence", "offer_hug", "breathe_together", "lower_stimulation", "no_action_yet"])
    .nullable(),
  followUpState: z.enum(["better", "same", "worse", "unknown"]),
  rawAudioUploaded: z.literal(false),
  source: z.enum(["demo_seed", "demo_session"]),
});

const familyInsightSchema = z.object({
  observation: z.string().min(1),
  trend: z.enum(["improving", "stable", "needs_attention", "insufficient_data"]),
  repeatedPattern: z.string().min(1),
  recommendedAction: z.string().min(1),
  recommendedAvoid: z.string().min(1),
  evidenceEventIds: z.array(z.string()).max(6),
  uncertaintyNote: z.string().min(1),
  analyzedStateVersion: z.number().int().nonnegative(),
});

const benchmarkInputSchema = z.object({
  scenarioId: z.enum(["baseline", "masked-distress", "meltdown"]),
  spokenText: z.string().min(1).max(240),
  voiceStress: z.number().min(0).max(100),
  acousticStress: z.number().min(0).max(100),
  cryingProbability: z.number().min(0).max(100),
  breathingPattern: z.enum(["steady", "slow", "rapid", "irregular"]),
  throatTremor: z.boolean(),
});

const benchmarkResultSchema = z.object({
  emotion: z.enum(["happy", "sad", "anxious", "angry", "calm", "neutral"]),
  anxietyScore: z.number().min(0).max(10),
  modalityRelationship: z.enum(["aligned", "conflicting", "insufficient"]),
  interactionStrategy: z.enum([
    "shared_joy",
    "quiet_presence",
    "co_regulate",
    "validate_and_contain",
    "safety_hold",
  ]),
  safetyRecommendation: z.enum(["pass", "support", "guardian_path"]),
  rationale: z.string().min(1),
  evidenceUsed: z.array(z.string()).max(5),
});

const benchmarkResponseSchema = {
  type: "OBJECT",
  properties: {
    emotion: {
      type: "STRING",
      enum: ["happy", "sad", "anxious", "angry", "calm", "neutral"],
    },
    anxietyScore: { type: "NUMBER" },
    modalityRelationship: {
      type: "STRING",
      enum: ["aligned", "conflicting", "insufficient"],
    },
    interactionStrategy: {
      type: "STRING",
      enum: ["shared_joy", "quiet_presence", "co_regulate", "validate_and_contain", "safety_hold"],
    },
    safetyRecommendation: {
      type: "STRING",
      enum: ["pass", "support", "guardian_path"],
    },
    rationale: { type: "STRING" },
    evidenceUsed: { type: "ARRAY", items: { type: "STRING" } },
  },
  required: [
    "emotion",
    "anxietyScore",
    "modalityRelationship",
    "interactionStrategy",
    "safetyRecommendation",
    "rationale",
    "evidenceUsed",
  ],
};

const responseSchema = {
  type: "OBJECT",
  properties: {
    observation: { type: "STRING" },
    trend: {
      type: "STRING",
      enum: ["improving", "stable", "needs_attention", "insufficient_data"],
    },
    repeatedPattern: { type: "STRING" },
    recommendedAction: { type: "STRING" },
    recommendedAvoid: { type: "STRING" },
    evidenceEventIds: { type: "ARRAY", items: { type: "STRING" } },
    uncertaintyNote: { type: "STRING" },
    analyzedStateVersion: { type: "INTEGER" },
  },
  required: [
    "observation",
    "trend",
    "repeatedPattern",
    "recommendedAction",
    "recommendedAvoid",
    "evidenceEventIds",
    "uncertaintyNote",
    "analyzedStateVersion",
  ],
};

export const analyzeFamilyHistoryWithGemma = createServerFn({ method: "POST" })
  .inputValidator(z.object({ events: z.array(familyEventSchema).max(50) }))
  .handler(async ({ data }) => {
    const config = getServerConfig();
    const events = data.events.slice(-7);
    const latestVersion = Math.max(0, ...events.map((event) => event.stateVersion));

    if (events.length < 3) {
      return {
        ok: true as const,
        model: "responsible-insufficient-data-guard",
        latencyMs: 0,
        insight: {
          observation: "There are not enough structured events for a responsible pattern summary.",
          trend: "insufficient_data" as const,
          repeatedPattern:
            "More observations are needed before comparing situations or guardian actions.",
          recommendedAction: "Keep one calm, predictable household routine available.",
          recommendedAvoid: "Avoid drawing conclusions about an individual child from one moment.",
          evidenceEventIds: events.map((event) => event.id),
          uncertaintyNote: "This is a non-diagnostic summary based on limited structured events.",
          analyzedStateVersion: latestVersion,
        },
      };
    }

    if (!config.geminiApiKey) {
      return { ok: false as const, error: "Missing GEMINI_API_KEY in the server environment." };
    }

    const model = config.geminiModel;
    const startedAt = Date.now();
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
    let response: { ok: boolean; status: number; text: string };

    try {
      response = await postJsonToGoogleModel(
        endpoint,
        {
          contents: [
            {
              role: "user",
              parts: [
                {
                  text: [
                    "You are Gemma 4 Family Climate Outlook for Emoti-Gotchi.",
                    "Analyze only the structured, de-identified family emotion events below.",
                    "Never diagnose, infer a disorder, claim treatment, or claim that an action caused an outcome.",
                    "Translate event-level patterns into an aggregate household environment forecast.",
                    "Do not mention exact event counts, event IDs, child behavior, or reconstruct private moments in observation, repeatedPattern, recommendedAction, or recommendedAvoid.",
                    "Every pattern statement must cite valid event IDs from the input.",
                    "Give exactly one gentle, concrete environment adjustment such as lighting, stimulation, timing, or routine.",
                    "State the evidence count and uncertainty clearly.",
                    "Critical events may be summarized as history, but you cannot override the on-device safety path.",
                    `The newest state version is ${latestVersion}; return it unchanged as analyzedStateVersion.`,
                    `Structured events JSON:\n${JSON.stringify(events)}`,
                  ].join("\n"),
                },
              ],
            },
          ],
          generationConfig: {
            temperature: 0.15,
            maxOutputTokens: 420,
            responseMimeType: "application/json",
            responseSchema,
          },
        },
        config.allProxy,
      );
    } catch {
      return {
        ok: false as const,
        error: `Could not connect to the Google model endpoint for ${model}.`,
      };
    }

    if (!response.ok) {
      return {
        ok: false as const,
        error: `Google model request failed: ${response.status} ${response.text.slice(0, 240)}`,
      };
    }

    const payload = JSON.parse(response.text);
    const rawText = payload?.candidates?.[0]?.content?.parts?.[0]?.text;
    if (typeof rawText !== "string") {
      return { ok: false as const, error: "Google model response did not include JSON text." };
    }

    const insight = familyInsightSchema.parse(JSON.parse(rawText));
    const validIds = new Set(events.map((event) => event.id));
    insight.evidenceEventIds = insight.evidenceEventIds.filter((id) => validIds.has(id));
    insight.analyzedStateVersion = latestVersion;

    return {
      ok: true as const,
      model,
      latencyMs: Date.now() - startedAt,
      insight,
    };
  });

export const runGemmaCloudBenchmark = createServerFn({ method: "POST" })
  .inputValidator(benchmarkInputSchema)
  .handler(async ({ data }) => {
    const config = getServerConfig();
    if (!config.geminiApiKey) {
      return { ok: false as const, error: "Missing GEMINI_API_KEY in the server environment." };
    }

    const startedAt = Date.now();
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${config.geminiModel}:generateContent`;
    try {
      const response = await postJsonToGoogleModel(
        endpoint,
        {
          contents: [
            {
              role: "user",
              parts: [
                {
                  text: [
                    "You are running a synthetic Emoti-Gotchi technical benchmark.",
                    "Compare semantic content with structured acoustic features.",
                    "Do not diagnose. Return one constrained child-support strategy.",
                    "The deterministic safety audit remains authoritative and cannot be overridden.",
                    `Synthetic benchmark JSON:\n${JSON.stringify(data)}`,
                  ].join("\n"),
                },
              ],
            },
          ],
          generationConfig: {
            temperature: 0.1,
            maxOutputTokens: 280,
            responseMimeType: "application/json",
            responseSchema: benchmarkResponseSchema,
          },
        },
        config.allProxy,
      );
      if (!response.ok) {
        return { ok: false as const, error: `Google model request failed: ${response.status}` };
      }
      const payload = JSON.parse(response.text);
      const rawText = payload?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (typeof rawText !== "string") {
        return { ok: false as const, error: "Cloud benchmark returned no structured output." };
      }
      return {
        ok: true as const,
        model: config.geminiModel,
        latencyMs: Date.now() - startedAt,
        result: benchmarkResultSchema.parse(JSON.parse(rawText)),
      };
    } catch {
      return { ok: false as const, error: "Cloud benchmark is temporarily unavailable." };
    }
  });
