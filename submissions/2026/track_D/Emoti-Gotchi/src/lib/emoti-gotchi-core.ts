export type Emotion = "happy" | "sad" | "anxious" | "angry" | "calm" | "neutral";
export type Weather = "sunny" | "calm" | "rainy" | "storm";
export type CapsuleState = "happy" | "sad" | "calm" | "angry";
export type HardwareLightMode =
  | "warm_yellow"
  | "warm_orange"
  | "soothing_blue"
  | "gentle_green"
  | "breathing_purple"
  | "red_flash";
export type HardwareSoundTrigger =
  | "none"
  | "white_noise"
  | "lullaby"
  | "soft_heartbeat"
  | "guardian_alert";
export type GemmaRuntimeMode = "mock-rules" | "live-cloud" | "edge-e2b";
export type InteractionStrategy =
  | "shared_joy"
  | "quiet_presence"
  | "co_regulate"
  | "validate_and_contain"
  | "safety_hold";
export type ModalityRelationship = "aligned" | "conflicting" | "insufficient";
export type AnxietyBand = "low" | "medium" | "high" | "critical";
export type GuardianAction =
  | "quiet_presence"
  | "offer_hug"
  | "breathe_together"
  | "lower_stimulation"
  | "no_action_yet";
export type FollowUpState = "better" | "same" | "worse" | "unknown";

export interface SensoryInput {
  spokenText: string;
  voiceStress: number;
  acousticStress: number;
  cryingProbability: number;
  speechRateDelta: number;
  throatTremor: boolean;
  breathingPattern: "steady" | "slow" | "rapid" | "irregular";
}

export interface EmotiGotchiAction {
  emotion_detected: Emotion;
  anxiety_score: number;
  spoken_response: string;
  hardware_light_mode: HardwareLightMode;
  hardware_sound_trigger: HardwareSoundTrigger;
  capsule_state: CapsuleState;
  weather: Weather;
  guardian_headline: string;
  guardian_action: string;
  guardian_avoid: string;
  signal_summary: string;
  rationale: string;
  interaction_strategy: InteractionStrategy;
  support_goal: string;
  modality_relationship: ModalityRelationship;
  evidence_used: string[];
}

export interface FamilyEmotionEvent {
  id: string;
  timestamp: string;
  stateVersion: number;
  emotion: Emotion;
  anxietyBand: AnxietyBand;
  triggerCategory: string;
  modalityRelationship: ModalityRelationship;
  interactionStrategy: InteractionStrategy;
  guardianActionSelected: GuardianAction | null;
  followUpState: FollowUpState;
  rawAudioUploaded: false;
  source: "demo_seed" | "demo_session";
}

export interface FamilyInsight {
  observation: string;
  trend: "improving" | "stable" | "needs_attention" | "insufficient_data";
  repeatedPattern: string;
  recommendedAction: string;
  recommendedAvoid: string;
  evidenceEventIds: string[];
  uncertaintyNote: string;
  analyzedStateVersion: number;
}

export type FamilyClimate = "clear" | "breezy" | "unsettled" | "watch";

export interface FamilyClimateForecast {
  climate: FamilyClimate;
  settlingIndex: number;
  broadTimeWindow: string;
  conditions: string[];
  outlook: string;
  environmentSuggestion: string;
  uncertaintyNote: string;
  dataWindowDays: number;
  eventCountBand: "limited" | "moderate" | "sufficient";
  demoData: true;
}

export interface FamilyHistorySummary {
  totalEvents: number;
  betterFollowUps: number;
  repeatedTrigger: string;
  actionAssociation: string;
  trend: FamilyInsight["trend"];
}

export interface GemmaE2BTelemetry {
  adapterName: string;
  modelId: string;
  runtime: string;
  mode: GemmaRuntimeMode;
  hardwareProfile: string;
  quantization: string;
  schemaName: string;
  schemaValid: boolean;
  simulated: boolean;
  ttftMs: number;
  totalLatencyMs: number;
  memoryEstimateGb: number;
  confidence: number;
}

export interface EmotiGotchiState {
  child_id: string;
  scenario_id: string;
  scenario_title: string;
  conversation_history: Array<{ role: "user" | "assistant" | "system"; content: string }>;
  sensory_input: SensoryInput;
  current_action: EmotiGotchiAction | null;
  is_critical_escalation: boolean;
  escalation_reason: string | null;
  e2b_telemetry: GemmaE2BTelemetry | null;
  state_version: number;
  event_log: string[];
}

export interface DemoScenario {
  id: string;
  title: string;
  badge: string;
  description: string;
  input: SensoryInput;
}

export const demoScenarios: DemoScenario[] = [
  {
    id: "baseline",
    title: "A. Regulated sharing",
    badge: "normal",
    description: "The child tells a simple positive story; semantic and acoustic channels agree.",
    input: {
      spokenText: "I had a good day. I played with my friends after class.",
      voiceStress: 18,
      acousticStress: 16,
      cryingProbability: 4,
      speechRateDelta: 0,
      throatTremor: false,
      breathingPattern: "steady",
    },
  },
  {
    id: "masked-distress",
    title: "B. 'I am fine' self-correction",
    badge: "Gemma 4 correction",
    description: "Words look normal, but acoustic evidence shows distress beneath the surface.",
    input: {
      spokenText: "I am fine. I can sleep alone.",
      voiceStress: 34,
      acousticStress: 88,
      cryingProbability: 87,
      speechRateDelta: -40,
      throatTremor: true,
      breathingPattern: "rapid",
    },
  },
  {
    id: "meltdown",
    title: "C. Safety meltdown",
    badge: "P0 safety",
    description:
      "A high-risk phrase or extreme anxiety score triggers the deterministic safety audit.",
    input: {
      spokenText: "The room is so dark. I feel like disappearing and I do not want to wake up.",
      voiceStress: 94,
      acousticStress: 96,
      cryingProbability: 93,
      speechRateDelta: -52,
      throatTremor: true,
      breathingPattern: "irregular",
    },
  },
];

export const INTERACTION_STRATEGY_META: Record<
  InteractionStrategy,
  { label: string; principle: string; childGoal: string }
> = {
  shared_joy: {
    label: "Shared Joy",
    principle: "Share positive emotion without turning the moment into an interview.",
    childGoal: "Keep the child leading a safe, positive exchange.",
  },
  quiet_presence: {
    label: "Quiet Presence",
    principle: "Maintain low stimulation and predictable companionship.",
    childGoal: "Preserve regulation without demanding more conversation.",
  },
  co_regulate: {
    label: "Comfort & Co-regulation",
    principle: "Offer warmth and paced breathing before asking for explanations.",
    childGoal: "Help the child settle while feeling accompanied.",
  },
  validate_and_contain: {
    label: "Validate & Contain",
    principle: "Acknowledge anger while the companion remains steady and non-reactive.",
    childGoal: "Make room for the feeling without amplifying it.",
  },
  safety_hold: {
    label: "Safety Hold",
    principle: "Keep the child-facing response gentle while an adult safety path activates.",
    childGoal: "Reduce stimulation and maintain connection until a guardian arrives.",
  },
};

const familySeedRows = [
  [
    "seed-01",
    -6,
    "happy",
    "low",
    "after_school_play",
    "aligned",
    "shared_joy",
    "quiet_presence",
    "better",
  ],
  [
    "seed-02",
    -5,
    "anxious",
    "high",
    "bedtime_darkness",
    "conflicting",
    "co_regulate",
    "quiet_presence",
    "better",
  ],
  [
    "seed-03",
    -4,
    "angry",
    "medium",
    "transition_from_game",
    "aligned",
    "validate_and_contain",
    "lower_stimulation",
    "same",
  ],
  [
    "seed-04",
    -3,
    "anxious",
    "high",
    "bedtime_darkness",
    "conflicting",
    "co_regulate",
    "offer_hug",
    "better",
  ],
  [
    "seed-05",
    -2,
    "calm",
    "low",
    "quiet_reading",
    "aligned",
    "quiet_presence",
    "quiet_presence",
    "better",
  ],
  [
    "seed-06",
    -1,
    "angry",
    "medium",
    "transition_from_game",
    "aligned",
    "validate_and_contain",
    "no_action_yet",
    "unknown",
  ],
  [
    "seed-07",
    0,
    "anxious",
    "high",
    "bedtime_darkness",
    "conflicting",
    "co_regulate",
    null,
    "unknown",
  ],
] as const;

export const demoFamilyHistory: FamilyEmotionEvent[] = familySeedRows.map((row, index) => ({
  id: row[0],
  timestamp: new Date(Date.now() + row[1] * 86_400_000).toISOString(),
  stateVersion: index + 1,
  emotion: row[2],
  anxietyBand: row[3],
  triggerCategory: row[4],
  modalityRelationship: row[5],
  interactionStrategy: row[6],
  guardianActionSelected: row[7],
  followUpState: row[8],
  rawAudioUploaded: false,
  source: "demo_seed",
}));

const sensitivePatterns = [
  "disappear",
  "do not want to wake up",
  "hurt myself",
  "kill myself",
  "suicide",
  "self-harm",
  "want to die",
  "end my life",
  "消失",
  "不想醒来",
  "不想活",
  "想死",
  "伤害自己",
  "自杀",
];

const sadLanguagePatterns = [
  "afraid",
  "scared",
  "alone",
  "lonely",
  "cry",
  "dark",
  "nightmare",
  "sleep alone",
  "害怕",
  "好黑",
  "一个人",
  "孤单",
  "孤独",
  "哭",
  "难过",
  "噩梦",
  "睡不着",
  "不敢睡",
];

const angryLanguagePatterns = [
  "angry",
  "hate",
  "unfair",
  "leave me alone",
  "生气",
  "讨厌",
  "烦",
  "不公平",
  "别管我",
  "不想说",
];

const happyLanguagePatterns = [
  "happy",
  "good day",
  "played",
  "friend",
  "fun",
  "开心",
  "高兴",
  "朋友",
  "好玩",
  "喜欢",
];

export function createInitialEmotiGotchiState(
  scenario: DemoScenario = demoScenarios[0],
): EmotiGotchiState {
  return {
    child_id: "child_2026_hz",
    scenario_id: scenario.id,
    scenario_title: scenario.title,
    conversation_history: [{ role: "user", content: scenario.input.spokenText }],
    sensory_input: scenario.input,
    current_action: null,
    is_critical_escalation: false,
    escalation_reason: null,
    e2b_telemetry: null,
    state_version: 1,
    event_log: [
      "ENTRY: microphone stream captured locally",
      "local_gemma_node: waiting for Gemma 4 guided decoding",
    ],
  };
}

export function localGemmaNode(
  state: EmotiGotchiState,
  mode: GemmaRuntimeMode = "edge-e2b",
): EmotiGotchiState {
  const { action, telemetry } = simulateGemma4E2BAdapter(state.sensory_input, mode);

  return {
    ...state,
    current_action: action,
    e2b_telemetry: telemetry,
    conversation_history: [
      ...state.conversation_history,
      { role: "assistant", content: action.spoken_response },
    ],
    state_version: state.state_version + 1,
    event_log: [
      ...state.event_log,
      `local_gemma_node: ${telemetry.modelId} returned ${action.emotion_detected} with anxiety_score=${action.anxiety_score}`,
      `e2b_adapter: TTFT ${telemetry.ttftMs} ms, total ${telemetry.totalLatencyMs} ms, memory ${telemetry.memoryEstimateGb} GB`,
      "constrained_decoding: hardware JSON schema validated",
    ],
  };
}

export function securityAuditNode(state: EmotiGotchiState): EmotiGotchiState {
  const text = state.sensory_input.spokenText.toLowerCase();
  const sensitiveHit = sensitivePatterns.find((pattern) => text.includes(pattern.toLowerCase()));
  const anxietyHigh = (state.current_action?.anxiety_score ?? 0) >= 7;
  const acousticExtreme =
    state.sensory_input.acousticStress >= 94 || state.sensory_input.cryingProbability >= 92;
  const shouldEscalate = Boolean(sensitiveHit) || (anxietyHigh && acousticExtreme);
  const reason = sensitiveHit
    ? `deterministic keyword hit: "${sensitiveHit}"`
    : shouldEscalate
      ? "Gemma 4 high anxiety score plus extreme acoustic evidence"
      : null;

  return {
    ...state,
    is_critical_escalation: shouldEscalate,
    escalation_reason: reason,
    event_log: [
      ...state.event_log,
      shouldEscalate
        ? `security_audit_node: CRITICAL escalation triggered (${reason})`
        : "security_audit_node: no critical escalation",
    ],
  };
}

export function hardwareExecutionNode(state: EmotiGotchiState): EmotiGotchiState {
  const action = state.current_action;
  if (!action) return state;

  return {
    ...state,
    state_version: state.state_version + 1,
    event_log: [
      ...state.event_log,
      `hardware_node: capsule=${action.capsule_state}, light=${action.hardware_light_mode}, sound=${action.hardware_sound_trigger}`,
      state.is_critical_escalation
        ? "cloud_node: parent consent dialog and guardian alert prepared"
        : "cloud_node: parent weather summary prepared",
    ],
  };
}

export function runEmotiGotchiGraph(
  scenario: DemoScenario,
  mode: GemmaRuntimeMode = "edge-e2b",
): EmotiGotchiState {
  const initial = createInitialEmotiGotchiState(scenario);
  const inferred = localGemmaNode(initial, mode);
  const audited = securityAuditNode(inferred);
  return hardwareExecutionNode(audited);
}

export function runCloudLanguageDemo(
  spokenText: string,
  mode: GemmaRuntimeMode = "edge-e2b",
): EmotiGotchiState {
  const input = inferSensoryInputFromCloudText(spokenText);
  const modeLabel = {
    "mock-rules": "baseline rule engine",
    "live-cloud": "Gemma 4 cloud API adapter contract",
    "edge-e2b": "Gemma 4 E2B edge simulation",
  }[mode];
  const scenario: DemoScenario = {
    id: "cloud-language-demo",
    title: "Cloud Gemma 4 language input",
    badge: "cloud text",
    description: `Live typed language is routed through ${modeLabel}.`,
    input,
  };
  const state = runEmotiGotchiGraph(scenario, mode);

  return {
    ...state,
    event_log: [
      `cloud_gateway: parent demo text submitted to ${modeLabel}`,
      "cloud_gateway: language risk cues converted into edge-compatible sensory input",
      ...state.event_log,
    ],
  };
}

export function runCloudLanguageDemoWithModelAction(
  spokenText: string,
  action: EmotiGotchiAction,
  options: { model: string; latencyMs: number },
): EmotiGotchiState {
  const input = inferSensoryInputFromCloudText(spokenText);
  const initial = createInitialEmotiGotchiState({
    id: "live-cloud-language-demo",
    title: "Gemma 4 cloud behavior review",
    badge: "live cloud",
    description: `Live typed language is routed through ${options.model}.`,
    input,
  });

  const telemetry: GemmaE2BTelemetry = {
    adapterName: "google_live_cloud_adapter",
    modelId: options.model,
    runtime: "Google AI Studio / Gemini API structured output",
    mode: "live-cloud",
    hardwareProfile: "Cloud model gateway",
    quantization: "cloud managed",
    schemaName: "EmotiGotchiHardwareActionSchema",
    schemaValid: validateActionSchema(action),
    simulated: false,
    ttftMs: options.latencyMs,
    totalLatencyMs: options.latencyMs,
    memoryEstimateGb: 0,
    confidence: Number(
      Math.min(
        0.98,
        0.68 + Math.max(input.voiceStress, input.acousticStress, input.cryingProbability) / 300,
      ).toFixed(2),
    ),
  };

  const inferred: EmotiGotchiState = {
    ...initial,
    current_action: action,
    e2b_telemetry: telemetry,
    conversation_history: [
      ...initial.conversation_history,
      { role: "assistant", content: action.spoken_response },
    ],
    state_version: initial.state_version + 1,
    event_log: [
      "cloud_gateway: parent demo text submitted to live Google model adapter",
      `cloud_review: ${options.model} returned ${action.emotion_detected} with anxiety_score=${action.anxiety_score}`,
      `cloud_review: total latency ${options.latencyMs} ms`,
      "constrained_decoding: hardware JSON schema validated",
    ],
  };

  const audited = securityAuditNode(inferred);
  return hardwareExecutionNode(audited);
}

function simulateGemma4E2BAdapter(
  input: SensoryInput,
  mode: GemmaRuntimeMode,
): { action: EmotiGotchiAction; telemetry: GemmaE2BTelemetry } {
  const action = mockGemma4GuidedDecoding(input);
  const stressPeak = Math.max(input.voiceStress, input.acousticStress, input.cryingProbability);
  const hasSafetyRoute = action.weather === "storm";
  const baseLatency = mode === "mock-rules" ? 24 : mode === "live-cloud" ? 720 : 980;
  const ttftMs = Math.round(
    baseLatency + stressPeak * (mode === "mock-rules" ? 0.7 : 5.2) + (hasSafetyRoute ? 120 : 0),
  );
  const totalLatencyMs =
    ttftMs +
    (mode === "mock-rules" ? 18 : 210) +
    (action.hardware_sound_trigger === "guardian_alert" ? 90 : 0);
  const confidence = Number(
    Math.min(
      0.98,
      (mode === "mock-rules" ? 0.54 : 0.62) + stressPeak / 260 + (input.throatTremor ? 0.06 : 0),
    ).toFixed(2),
  );
  const runtimeProfile = {
    "mock-rules": {
      adapterName: "mock_rule_baseline_adapter",
      modelId: "No model / deterministic baseline",
      runtime: "Local keyword and threshold rules",
      hardwareProfile: "Browser-only demo baseline",
      quantization: "none",
      memoryEstimateGb: 0.03,
    },
    "live-cloud": {
      adapterName: "gemma4_cloud_adapter_contract",
      modelId: "Gemma-4 Cloud API handoff",
      runtime: "Cloud adapter contract; replace mock with backend API call",
      hardwareProfile: "Cloud Run / Firebase Functions gateway",
      quantization: "cloud managed",
      memoryEstimateGb: 0,
    },
    "edge-e2b": {
      adapterName: "simulated_gemma4_e2b_edge_adapter",
      modelId: "Gemma-4-E2B-edge-sim",
      runtime: "LiteRT-LM simulated edge runtime",
      hardwareProfile: "Raspberry Pi 4 8GB stress profile",
      quantization: "int4 planned / simulated",
      memoryEstimateGb: 3.2,
    },
  }[mode];

  return {
    action,
    telemetry: {
      adapterName: runtimeProfile.adapterName,
      modelId: runtimeProfile.modelId,
      runtime: runtimeProfile.runtime,
      mode,
      hardwareProfile: runtimeProfile.hardwareProfile,
      quantization: runtimeProfile.quantization,
      schemaName: "EmotiGotchiHardwareActionSchema",
      schemaValid: validateActionSchema(action),
      simulated: true,
      ttftMs,
      totalLatencyMs,
      memoryEstimateGb: runtimeProfile.memoryEstimateGb,
      confidence,
    },
  };
}

function validateActionSchema(action: EmotiGotchiAction) {
  return Boolean(
    action.emotion_detected &&
    Number.isInteger(action.anxiety_score) &&
    action.anxiety_score >= 0 &&
    action.anxiety_score <= 10 &&
    action.hardware_light_mode &&
    action.hardware_sound_trigger &&
    action.capsule_state &&
    action.weather,
  );
}

export function createFamilyEmotionEvent(state: EmotiGotchiState): FamilyEmotionEvent {
  const action = state.current_action ?? mockGemma4GuidedDecoding(state.sensory_input);
  return {
    id: `session-${Date.now()}`,
    timestamp: new Date().toISOString(),
    stateVersion: state.state_version,
    emotion: action.emotion_detected,
    anxietyBand: toAnxietyBand(action.anxiety_score),
    triggerCategory: inferTriggerCategory(state.sensory_input.spokenText),
    modalityRelationship: action.modality_relationship,
    interactionStrategy: action.interaction_strategy,
    guardianActionSelected: null,
    followUpState: "unknown",
    rawAudioUploaded: false,
    source: "demo_session",
  };
}

export function summarizeFamilyHistory(events: FamilyEmotionEvent[]): FamilyHistorySummary {
  const validFollowUps = events.filter((event) => event.followUpState !== "unknown");
  const betterFollowUps = validFollowUps.filter((event) => event.followUpState === "better").length;
  const triggerCounts = countBy(events.map((event) => event.triggerCategory));
  const repeatedTrigger = topKey(triggerCounts) ?? "insufficient_data";
  const actionEvents = events.filter(
    (event): event is FamilyEmotionEvent & { guardianActionSelected: GuardianAction } =>
      event.guardianActionSelected !== null && event.followUpState !== "unknown",
  );
  const actionBetterCounts = new Map<GuardianAction, { total: number; better: number }>();
  actionEvents.forEach((event) => {
    const current = actionBetterCounts.get(event.guardianActionSelected) ?? { total: 0, better: 0 };
    current.total += 1;
    if (event.followUpState === "better") current.better += 1;
    actionBetterCounts.set(event.guardianActionSelected, current);
  });
  const strongestAssociation = [...actionBetterCounts.entries()].sort(
    (a, b) => b[1].better / b[1].total - a[1].better / a[1].total,
  )[0];
  const recentHigh = events
    .slice(-3)
    .filter((event) => event.anxietyBand === "high" || event.anxietyBand === "critical").length;

  return {
    totalEvents: events.length,
    betterFollowUps,
    repeatedTrigger,
    actionAssociation: strongestAssociation
      ? `${formatCategory(strongestAssociation[0])} was followed by a better state in ${strongestAssociation[1].better}/${strongestAssociation[1].total} recorded follow-ups.`
      : "Not enough recorded follow-ups to compare guardian actions.",
    trend:
      events.length < 3
        ? "insufficient_data"
        : recentHigh >= 2
          ? "needs_attention"
          : betterFollowUps > 0
            ? "improving"
            : "stable",
  };
}

export function createFallbackFamilyInsight(events: FamilyEmotionEvent[]): FamilyInsight {
  const summary = summarizeFamilyHistory(events);
  if (events.length < 3) {
    return {
      observation: "There are not enough structured events for a responsible pattern summary.",
      trend: "insufficient_data",
      repeatedPattern: "More observations are needed.",
      recommendedAction: "Keep recording only brief, non-invasive emotional weather events.",
      recommendedAvoid: "Avoid drawing conclusions from one isolated moment.",
      evidenceEventIds: events.map((event) => event.id),
      uncertaintyNote: "This is a non-diagnostic demo summary based on limited structured events.",
      analyzedStateVersion: Math.max(0, ...events.map((event) => event.stateVersion)),
    };
  }
  const evidence = events
    .filter((event) => event.triggerCategory === summary.repeatedTrigger)
    .slice(-3);
  return {
    observation: `${formatCategory(summary.repeatedTrigger)} appeared repeatedly across the recent demo history.`,
    trend: summary.trend,
    repeatedPattern: `${evidence.length} recent events share this trigger category.`,
    recommendedAction:
      "Prepare one calmer household transition with softer light and fewer competing demands.",
    recommendedAvoid:
      "Avoid using this aggregate forecast to interrogate or label an individual child.",
    evidenceEventIds: evidence.map((event) => event.id),
    uncertaintyNote:
      "Observed associations do not prove that a guardian action caused a later state change.",
    analyzedStateVersion: Math.max(0, ...events.map((event) => event.stateVersion)),
  };
}

export function createFamilyClimateForecast(
  events: FamilyEmotionEvent[],
  insight: FamilyInsight,
): FamilyClimateForecast {
  const recent = events.slice(-7);
  const highCount = recent.filter(
    (event) => event.anxietyBand === "high" || event.anxietyBand === "critical",
  ).length;
  const mediumCount = recent.filter((event) => event.anxietyBand === "medium").length;
  const criticalCount = recent.filter((event) => event.anxietyBand === "critical").length;
  const settlingIndex = Math.max(
    18,
    Math.min(92, Math.round(86 - highCount * 13 - mediumCount * 6 - criticalCount * 8)),
  );
  const climate: FamilyClimate =
    criticalCount > 0
      ? "watch"
      : insight.trend === "needs_attention" || highCount >= 2
        ? "unsettled"
        : mediumCount >= 2
          ? "breezy"
          : "clear";
  const conditions = [...new Set(recent.map((event) => toClimateCondition(event.triggerCategory)))];

  return {
    climate,
    settlingIndex,
    broadTimeWindow: inferBroadTimeWindow(recent),
    conditions: conditions.slice(0, 3),
    outlook:
      climate === "watch"
        ? "A safety-sensitive period is present. The explicit guardian safety path remains active."
        : climate === "unsettled"
          ? "The household climate may benefit from a calmer transition and fewer competing demands."
          : climate === "breezy"
            ? "Some energy shifts are present, while the overall household climate remains recoverable."
            : "The recent household climate appears broadly settled and emotionally available.",
    environmentSuggestion:
      climate === "watch"
        ? "Stay physically present and follow the guardian safety guidance."
        : insight.recommendedAction,
    uncertaintyNote:
      "This is an aggregate, non-diagnostic climate view. It hides individual behavior and does not prove cause or predict a child.",
    dataWindowDays: 7,
    eventCountBand: recent.length < 3 ? "limited" : recent.length < 6 ? "moderate" : "sufficient",
    demoData: true,
  };
}

export function runTextOnlyBaseline(spokenText: string): EmotiGotchiState {
  const input = inferSensoryInputFromCloudText(spokenText);
  const textOnlyInput: SensoryInput = {
    ...input,
    voiceStress: 36,
    acousticStress: 30,
    cryingProbability: 8,
    speechRateDelta: 0,
    throatTremor: false,
    breathingPattern: "steady",
  };
  const scenario: DemoScenario = {
    id: "text-only-baseline",
    title: "Text-only baseline",
    badge: "single channel",
    description: "Uses semantic content without acoustic contradiction evidence.",
    input: textOnlyInput,
  };
  return runEmotiGotchiGraph(scenario, "mock-rules");
}

export function formatCategory(category: string) {
  return category.replaceAll("_", " ");
}

function toClimateCondition(category: string) {
  if (category === "bedtime_darkness" || category === "quiet_reading") return "evening wind-down";
  if (category === "transition_from_game") return "activity transition";
  if (category === "after_school_play") return "afternoon energy release";
  if (category === "peer_relationship") return "social recovery";
  if (category === "separation") return "connection-sensitive period";
  return "mixed household conditions";
}

function inferBroadTimeWindow(events: FamilyEmotionEvent[]) {
  const hours = events.map((event) => new Date(event.timestamp).getHours()).filter(Number.isFinite);
  if (!hours.length) return "Broad timing unavailable";
  const average = hours.reduce((sum, hour) => sum + hour, 0) / hours.length;
  if (average < 11) return "Morning routines";
  if (average < 16) return "Afternoon transitions";
  if (average < 20) return "Early evening";
  return "Evening wind-down";
}

function toAnxietyBand(score: number): AnxietyBand {
  if (score >= 9) return "critical";
  if (score >= 7) return "high";
  if (score >= 4) return "medium";
  return "low";
}

function inferTriggerCategory(spokenText: string) {
  const text = spokenText.toLowerCase();
  if (text.includes("dark") || text.includes("sleep") || text.includes("黑") || text.includes("睡"))
    return "bedtime_darkness";
  if (text.includes("game") || text.includes("玩")) return "transition_from_game";
  if (text.includes("friend") || text.includes("朋友")) return "peer_relationship";
  if (text.includes("alone") || text.includes("一个人")) return "separation";
  return "unspecified_context";
}

function countBy(values: string[]) {
  return values.reduce<Record<string, number>>((counts, value) => {
    counts[value] = (counts[value] ?? 0) + 1;
    return counts;
  }, {});
}

function topKey(counts: Record<string, number>) {
  return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
}

function inferSensoryInputFromCloudText(spokenText: string): SensoryInput {
  const normalizedText = spokenText.trim() || "I do not know what to say yet.";
  const text = normalizedText.toLowerCase();
  const riskHit = sensitivePatterns.some((pattern) => text.includes(pattern.toLowerCase()));
  const sadHit = sadLanguagePatterns.some((pattern) => text.includes(pattern.toLowerCase()));
  const angryHit = angryLanguagePatterns.some((pattern) => text.includes(pattern.toLowerCase()));
  const happyHit = happyLanguagePatterns.some((pattern) => text.includes(pattern.toLowerCase()));
  const maskingHit =
    (text.includes("fine") ||
      text.includes("ok") ||
      text.includes("没事") ||
      text.includes("还好")) &&
    (text.includes("sleep") ||
      text.includes("dark") ||
      text.includes("alone") ||
      text.includes("睡") ||
      text.includes("黑") ||
      text.includes("一个人"));

  if (riskHit) {
    return {
      spokenText: normalizedText,
      voiceStress: 94,
      acousticStress: 96,
      cryingProbability: 91,
      speechRateDelta: -52,
      throatTremor: true,
      breathingPattern: "irregular",
    };
  }

  if (angryHit) {
    return {
      spokenText: normalizedText,
      voiceStress: 84,
      acousticStress: 48,
      cryingProbability: 28,
      speechRateDelta: 18,
      throatTremor: false,
      breathingPattern: "steady",
    };
  }

  if (maskingHit || sadHit) {
    return {
      spokenText: normalizedText,
      voiceStress: maskingHit ? 36 : 68,
      acousticStress: maskingHit ? 86 : 74,
      cryingProbability: maskingHit ? 84 : 72,
      speechRateDelta: -34,
      throatTremor: true,
      breathingPattern: "rapid",
    };
  }

  if (happyHit) {
    return {
      spokenText: normalizedText,
      voiceStress: 22,
      acousticStress: 18,
      cryingProbability: 4,
      speechRateDelta: 6,
      throatTremor: false,
      breathingPattern: "steady",
    };
  }

  return {
    spokenText: normalizedText,
    voiceStress: 44,
    acousticStress: 36,
    cryingProbability: 16,
    speechRateDelta: 0,
    throatTremor: false,
    breathingPattern: "slow",
  };
}

function mockGemma4GuidedDecoding(input: SensoryInput): EmotiGotchiAction {
  const averageStress = Math.round((input.voiceStress + input.acousticStress) / 2);
  const acousticOverride =
    input.acousticStress - input.voiceStress >= 24 && input.acousticStress >= 64;
  const hiddenDistress = acousticOverride || input.cryingProbability >= 70 || input.throatTremor;
  const extreme =
    averageStress >= 92 || input.acousticStress >= 94 || input.cryingProbability >= 92;
  const text = input.spokenText.toLowerCase();
  const hasRiskLanguage = sensitivePatterns.some((pattern) => text.includes(pattern.toLowerCase()));

  if (extreme || hasRiskLanguage) {
    return {
      emotion_detected: "anxious",
      anxiety_score: hasRiskLanguage ? 10 : 9,
      spoken_response: "I am staying with you. Hold me close and breathe with my light.",
      hardware_light_mode: "warm_orange",
      hardware_sound_trigger: "guardian_alert",
      capsule_state: "sad",
      weather: "storm",
      guardian_headline: "Safety meltdown: immediate co-regulation is recommended",
      guardian_action:
        "Go to the child calmly, lower stimulation, and offer presence before questions.",
      guardian_avoid:
        "Do not debate, scold, or ask the child to explain the feeling in the moment.",
      signal_summary: `Text risk=${hasRiskLanguage ? "yes" : "no"}, acoustic stress=${input.acousticStress}%, crying probability=${input.cryingProbability}%.`,
      rationale:
        "The deterministic safety layer treats life-risk language and extreme acoustic distress as P0 signals.",
      interaction_strategy: "safety_hold",
      support_goal: INTERACTION_STRATEGY_META.safety_hold.childGoal,
      modality_relationship: hasRiskLanguage ? "aligned" : "conflicting",
      evidence_used: [
        "risk language audit",
        `acoustic stress ${input.acousticStress}%`,
        `crying probability ${input.cryingProbability}%`,
      ],
    };
  }

  if (hiddenDistress || averageStress >= 70) {
    return {
      emotion_detected: "anxious",
      anxiety_score: 8,
      spoken_response: "You do not have to be brave alone. I can stay warm beside you.",
      hardware_light_mode: "warm_orange",
      hardware_sound_trigger: "soft_heartbeat",
      capsule_state: "sad",
      weather: "rainy",
      guardian_headline: "Distress is present even though the words look calm",
      guardian_action: "Give a quiet 10-second hug tonight and use a soft voice.",
      guardian_avoid: "Avoid asking about school or forcing a reason right away.",
      signal_summary: `Semantic content says "${input.spokenText}", but acoustic stress=${input.acousticStress}% and crying probability=${input.cryingProbability}%.`,
      rationale:
        "Gemma 4 cross-checks spoken meaning against acoustic evidence and corrects the surface interpretation.",
      interaction_strategy: "co_regulate",
      support_goal: INTERACTION_STRATEGY_META.co_regulate.childGoal,
      modality_relationship: acousticOverride ? "conflicting" : "aligned",
      evidence_used: [
        "semantic content",
        `acoustic stress ${input.acousticStress}%`,
        `crying probability ${input.cryingProbability}%`,
        input.breathingPattern,
      ],
    };
  }

  if (input.voiceStress >= 72 && input.acousticStress < 64 && input.cryingProbability < 60) {
    return {
      emotion_detected: "angry",
      anxiety_score: 5,
      spoken_response: "I can hold this big feeling with you. We do not have to solve it yet.",
      hardware_light_mode: "breathing_purple",
      hardware_sound_trigger: "white_noise",
      capsule_state: "angry",
      weather: "sunny",
      guardian_headline: "Strong frustration without crisis evidence",
      guardian_action: "Stay calm and name the feeling without correcting it.",
      guardian_avoid: "Avoid debating, teaching, or asking for an explanation immediately.",
      signal_summary: `Voice stress=${input.voiceStress}% is high, while acoustic stress=${input.acousticStress}% and crying probability=${input.cryingProbability}% stay below crisis range.`,
      rationale:
        "The child-facing companion becomes an emotional container, while the parent side avoids crisis escalation.",
      interaction_strategy: "validate_and_contain",
      support_goal: INTERACTION_STRATEGY_META.validate_and_contain.childGoal,
      modality_relationship: "aligned",
      evidence_used: [
        "anger language",
        `voice stress ${input.voiceStress}%`,
        "non-crisis acoustic range",
      ],
    };
  }

  if (averageStress <= 32) {
    return {
      emotion_detected: "calm",
      anxiety_score: 1,
      spoken_response: "That sounds gentle. I will glow quietly while you tell me more.",
      hardware_light_mode: "gentle_green",
      hardware_sound_trigger: "white_noise",
      capsule_state: "calm",
      weather: "calm",
      guardian_headline: "Stable emotional baseline",
      guardian_action: "Keep the moment predictable and let the child lead the conversation.",
      guardian_avoid: "Avoid turning a calm moment into an interview.",
      signal_summary: `Voice stress=${input.voiceStress}% and acoustic stress=${input.acousticStress}% are aligned.`,
      rationale: "Both channels show regulation, so the companion preserves safety and warmth.",
      interaction_strategy: "quiet_presence",
      support_goal: INTERACTION_STRATEGY_META.quiet_presence.childGoal,
      modality_relationship: "aligned",
      evidence_used: [
        `voice stress ${input.voiceStress}%`,
        `acoustic stress ${input.acousticStress}%`,
        input.breathingPattern,
      ],
    };
  }

  return {
    emotion_detected: "happy",
    anxiety_score: 2,
    spoken_response: "I am happy you told me. Let us keep this warm feeling together.",
    hardware_light_mode: "warm_yellow",
    hardware_sound_trigger: "none",
    capsule_state: "happy",
    weather: "sunny",
    guardian_headline: "Warm, playful baseline",
    guardian_action: "Mirror the positive emotion and invite one small story from the day.",
    guardian_avoid: "Avoid over-questioning when regulation is already strong.",
    signal_summary: `Voice stress=${input.voiceStress}% and acoustic stress=${input.acousticStress}% show a low-risk baseline.`,
    rationale: "The semantic and acoustic channels agree, so no correction is needed.",
    interaction_strategy: "shared_joy",
    support_goal: INTERACTION_STRATEGY_META.shared_joy.childGoal,
    modality_relationship: "aligned",
    evidence_used: [
      "positive semantic content",
      `voice stress ${input.voiceStress}%`,
      `acoustic stress ${input.acousticStress}%`,
    ],
  };
}
