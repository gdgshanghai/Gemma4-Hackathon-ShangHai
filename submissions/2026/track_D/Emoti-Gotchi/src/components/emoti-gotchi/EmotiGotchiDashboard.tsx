import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Cloud,
  CloudLightning,
  CloudRain,
  CloudSun,
  Database,
  Gauge,
  HeartHandshake,
  History,
  Lock,
  Mic,
  Phone,
  Play,
  RefreshCw,
  Send,
  Shield,
  Sparkles,
  Sun,
  TrendingUp,
  Volume2,
  Waves,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { analyzeFamilyHistoryWithGemma, runGemmaCloudBenchmark } from "@/lib/api/gemma.functions";
import {
  INTERACTION_STRATEGY_META,
  type CapsuleState,
  type DemoScenario,
  type EmotiGotchiState,
  type FamilyClimate,
  type FamilyEmotionEvent,
  type FamilyInsight,
  type FollowUpState,
  type GuardianAction,
  type Weather,
  createFamilyClimateForecast,
  createFallbackFamilyInsight,
  createFamilyEmotionEvent,
  demoFamilyHistory,
  demoScenarios,
  formatCategory,
  runCloudLanguageDemo,
  runEmotiGotchiGraph,
  runTextOnlyBaseline,
  summarizeFamilyHistory,
} from "@/lib/emoti-gotchi-core";
import { cn } from "@/lib/utils";
import angryImage from "@/assets/emoti-gotchi-angry.webp";
import calmImage from "@/assets/emoti-gotchi-calm.webp";
import happyImage from "@/assets/emoti-gotchi-happy.webp";
import sadImage from "@/assets/emoti-gotchi-sad.webp";

const HISTORY_KEY = "emoti-gotchi-family-history-v1";

type CloudBenchmark =
  | {
      ok: true;
      model: string;
      latencyMs: number;
      result: {
        emotion: string;
        anxietyScore: number;
        modalityRelationship: string;
        interactionStrategy: string;
        safetyRecommendation: string;
        rationale: string;
        evidenceUsed: string[];
      };
    }
  | { ok: false; error: string };

const WEATHER_META: Record<Weather, { label: string; sub: string; icon: typeof Sun; bg: string }> =
  {
    sunny: {
      label: "Sunny",
      sub: "Open and emotionally available",
      icon: Sun,
      bg: "from-secondary to-muted",
    },
    calm: {
      label: "Breezy",
      sub: "Settled and self-regulating",
      icon: CloudSun,
      bg: "from-muted to-accent/10",
    },
    rainy: {
      label: "Rainy",
      sub: "Distress beneath the spoken surface",
      icon: CloudRain,
      bg: "from-accent/10 to-secondary",
    },
    storm: {
      label: "Storm Alert",
      sub: "Guardian support is needed now",
      icon: CloudLightning,
      bg: "from-destructive/10 to-secondary",
    },
  };

const CAPSULE_META: Record<CapsuleState, { image: string; mood: string; halo: string }> = {
  happy: {
    image: happyImage,
    mood: "Shared joy / Child-led",
    halo: "radial-gradient(circle, rgba(255,215,120,.38), transparent 70%)",
  },
  calm: {
    image: calmImage,
    mood: "Quiet presence / Low stimulation",
    halo: "radial-gradient(circle, rgba(167,232,180,.36), transparent 70%)",
  },
  sad: {
    image: sadImage,
    mood: "Comfort / Co-regulation",
    halo: "radial-gradient(circle, rgba(255,175,93,.36), transparent 72%)",
  },
  angry: {
    image: angryImage,
    mood: "Validate / Contain without amplifying",
    halo: "radial-gradient(circle, rgba(165,140,220,.36), transparent 72%)",
  },
};

const GUARDIAN_ACTIONS: Array<{ value: GuardianAction; label: string }> = [
  { value: "quiet_presence", label: "Quiet presence" },
  { value: "offer_hug", label: "Offer a hug" },
  { value: "breathe_together", label: "Breathe together" },
  { value: "lower_stimulation", label: "Lower stimulation" },
  { value: "no_action_yet", label: "No action yet" },
];

const FOLLOW_UPS: Array<{ value: FollowUpState; label: string }> = [
  { value: "better", label: "Better" },
  { value: "same", label: "Same" },
  { value: "worse", label: "Worse" },
  { value: "unknown", label: "Unknown" },
];

export default function EmotiGotchiDashboard() {
  const [activeScenarioId, setActiveScenarioId] = useState(demoScenarios[0].id);
  const [state, setState] = useState<EmotiGotchiState>(() =>
    runEmotiGotchiGraph(demoScenarios[0], "edge-e2b"),
  );
  const [text, setText] = useState(
    "I am fine, but the room is too dark and I am scared to sleep alone.",
  );
  const [consentOpen, setConsentOpen] = useState(false);
  const [history, setHistory] = useState<FamilyEmotionEvent[]>(demoFamilyHistory);
  const [historyReady, setHistoryReady] = useState(false);
  const [insight, setInsight] = useState<FamilyInsight>(() =>
    createFallbackFamilyInsight(demoFamilyHistory),
  );
  const [insightBusy, setInsightBusy] = useState(false);
  const [insightStatus, setInsightStatus] = useState(
    "Demo seed data is ready for a privacy-safe family climate outlook.",
  );
  const [cloudBenchmark, setCloudBenchmark] = useState<CloudBenchmark | null>(null);
  const [cloudBenchmarkBusy, setCloudBenchmarkBusy] = useState(false);
  const [cloudBenchmarkSignature, setCloudBenchmarkSignature] = useState("");

  useEffect(() => {
    const stored = window.localStorage.getItem(HISTORY_KEY);
    if (stored) {
      try {
        setHistory(JSON.parse(stored) as FamilyEmotionEvent[]);
      } catch {
        setHistory(demoFamilyHistory);
      }
    }
    setHistoryReady(true);
  }, []);

  useEffect(() => {
    if (historyReady) window.localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  }, [history, historyReady]);

  const action = state.current_action;
  const capsuleState = action?.capsule_state ?? "happy";
  const weather = action?.weather ?? "sunny";
  const climate = useMemo(() => createFamilyClimateForecast(history, insight), [history, insight]);
  const textOnlyState = useMemo(
    () => runTextOnlyBaseline(state.sensory_input.spokenText),
    [state.sensory_input.spokenText],
  );
  const currentSignature = JSON.stringify(state.sensory_input);

  const runScenario = (scenario: DemoScenario) => {
    const nextState = runEmotiGotchiGraph(scenario, "edge-e2b");
    setActiveScenarioId(scenario.id);
    setState(nextState);
    setConsentOpen(nextState.is_critical_escalation);
  };

  const runTypedInput = () => {
    const nextState = runCloudLanguageDemo(text, "edge-e2b");
    setActiveScenarioId("typed-edge-input");
    setState(nextState);
    setConsentOpen(nextState.is_critical_escalation);
  };

  const updateSignal = (
    key: "voiceStress" | "acousticStress" | "cryingProbability",
    value: number,
  ) => {
    const nextInput = { ...state.sensory_input, [key]: value };
    const maxStress = Math.max(
      nextInput.voiceStress,
      nextInput.acousticStress,
      nextInput.cryingProbability,
    );
    const custom: DemoScenario = {
      id: "manual-multichannel",
      title: "Manual multichannel check",
      badge: "interactive",
      description: "Structured signals are evaluated locally without uploading raw audio.",
      input: {
        ...nextInput,
        throatTremor: nextInput.acousticStress >= 72 || nextInput.cryingProbability >= 70,
        breathingPattern:
          maxStress >= 94
            ? "irregular"
            : maxStress >= 72
              ? "rapid"
              : maxStress <= 32
                ? "steady"
                : "slow",
        speechRateDelta: maxStress >= 72 ? -Math.round((maxStress - 60) * 0.9) : 0,
      },
    };
    const nextState = runEmotiGotchiGraph(custom, "edge-e2b");
    setActiveScenarioId(custom.id);
    setState(nextState);
    setConsentOpen(nextState.is_critical_escalation);
  };

  const saveCurrentEvent = () => {
    const event = createFamilyEmotionEvent(state);
    setHistory((current) => [...current, event].slice(-30));
    setInsightStatus("A de-identified demo event was added. Raw audio uploaded: No.");
  };

  const resetHistory = () => {
    setHistory(demoFamilyHistory);
    setInsight(createFallbackFamilyInsight(demoFamilyHistory));
    setInsightStatus("Demo seed data restored. No real child data is used.");
  };

  const runFamilyInsight = async () => {
    const preview = createFallbackFamilyInsight(history);
    setInsight(preview);
    setInsightBusy(true);
    setInsightStatus(
      "Instant on-device preview shown. Cloud Gemma is refining it in the background.",
    );
    try {
      const result = await Promise.race([
        analyzeFamilyHistoryWithGemma({ data: { events: history.slice(-7) } }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("family-insight-timeout")), 8000),
        ),
      ]);
      if (!result.ok) {
        setInsightStatus(
          "On-device preview is ready. Cloud refinement is temporarily unavailable.",
        );
        return;
      }
      const newestVersion = Math.max(0, ...history.map((event) => event.stateVersion));
      if (result.insight.analyzedStateVersion < newestVersion) {
        setInsightStatus(
          "An outdated cloud result was discarded because newer family events exist.",
        );
        return;
      }
      setInsight(result.insight);
      setInsightStatus(
        `Gemma 4 climate refinement completed in ${result.latencyMs} ms using structured summaries only.`,
      );
    } catch {
      setInsightStatus(
        "On-device preview is ready. Cloud refinement exceeded 8 seconds and was skipped.",
      );
    } finally {
      setInsightBusy(false);
    }
  };

  const runCloudBenchmark = async () => {
    if (cloudBenchmark && cloudBenchmarkSignature === currentSignature) return;
    const scenarioId = state.scenario_id;
    if (
      scenarioId !== "baseline" &&
      scenarioId !== "masked-distress" &&
      scenarioId !== "meltdown"
    ) {
      setCloudBenchmark({
        ok: false,
        error: "Select a fixed synthetic scenario before running the public cloud benchmark.",
      });
      setCloudBenchmarkSignature(currentSignature);
      return;
    }
    setCloudBenchmarkBusy(true);
    try {
      const result = await Promise.race([
        runGemmaCloudBenchmark({
          data: {
            scenarioId,
            spokenText: state.sensory_input.spokenText,
            voiceStress: state.sensory_input.voiceStress,
            acousticStress: state.sensory_input.acousticStress,
            cryingProbability: state.sensory_input.cryingProbability,
            breathingPattern: state.sensory_input.breathingPattern,
            throatTremor: state.sensory_input.throatTremor,
          },
        }),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("cloud-benchmark-timeout")), 8000),
        ),
      ]);
      setCloudBenchmark(result);
      setCloudBenchmarkSignature(currentSignature);
    } catch {
      setCloudBenchmark({ ok: false, error: "Cloud benchmark exceeded 8 seconds." });
      setCloudBenchmarkSignature(currentSignature);
    } finally {
      setCloudBenchmarkBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-[1500px] px-4 py-5 sm:px-6">
        <Header
          onReset={() => runScenario(demoScenarios[0])}
          onOpenConsent={() => setConsentOpen(true)}
          critical={state.is_critical_escalation}
        />

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <Metric icon={Mic} label="Realtime child support" value="On-device / no cloud wait" />
          <Metric icon={Cloud} label="Long-term family climate" value="Cloud Gemma 4" />
          <Metric icon={Shield} label="Raw audio uploaded" value="No" />
          <Metric icon={HeartHandshake} label="Product boundary" value="Non-diagnostic support" />
        </div>

        <Tabs defaultValue="live" className="mt-5">
          <TabsList className="grid h-auto w-full grid-cols-3 rounded-xl border border-border bg-card p-1">
            <TabsTrigger value="live" className="rounded-lg py-2">
              Live Demo
            </TabsTrigger>
            <TabsTrigger value="proof" className="rounded-lg py-2">
              Technical Proof
            </TabsTrigger>
            <TabsTrigger value="family" className="rounded-lg py-2">
              Family Climate
            </TabsTrigger>
          </TabsList>

          <TabsContent value="live" className="mt-5 space-y-5">
            <SafetyStatusBar state={state} />
            <div className="grid gap-5 xl:grid-cols-12">
              <div className="space-y-5 xl:col-span-4">
                <InputPanel text={text} onTextChange={setText} onRun={runTypedInput} />
                <ScenarioPanel activeScenarioId={activeScenarioId} onRun={runScenario} />
                <EdgePanel state={state} onSignalChange={updateSignal} />
              </div>
              <div className="xl:col-span-4">
                <CapsulePanel state={state} capsuleState={capsuleState} />
              </div>
              <div className="xl:col-span-4">
                <ParentNowPanel
                  state={state}
                  weather={weather}
                  onOpenConsent={() => setConsentOpen(true)}
                  onSave={saveCurrentEvent}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="proof" className="mt-5 space-y-5">
            <TechnicalValidationLab
              baseline={textOnlyState}
              multichannel={state}
              cloud={cloudBenchmark}
              cloudBusy={cloudBenchmarkBusy}
              cloudStale={Boolean(cloudBenchmark) && cloudBenchmarkSignature !== currentSignature}
              onRunCloud={runCloudBenchmark}
            />
            <SafetyCoverageMatrix />
            <ActionProtocolProof state={state} />
            <TracePanel state={state} />
          </TabsContent>

          <TabsContent value="family" className="mt-5 space-y-5">
            <FamilyClimatePanel
              events={history}
              climate={climate}
              onReset={resetHistory}
            />
            <ClimateInsightPanel
              climate={climate}
              insight={insight}
              busy={insightBusy}
              status={insightStatus}
              onRun={runFamilyInsight}
            />
            <FamilySafetyPanel state={state} onOpenConsent={() => setConsentOpen(true)} />
          </TabsContent>
        </Tabs>
      </div>
      <ConsentDialog open={consentOpen} onOpenChange={setConsentOpen} state={state} />
    </div>
  );
}

function Header({
  onReset,
  onOpenConsent,
  critical,
}: {
  onReset: () => void;
  onOpenConsent: () => void;
  critical: boolean;
}) {
  return (
    <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div className="flex items-center gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-xl border border-border bg-card shadow-sm">
          <HeartHandshake className="h-6 w-6 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Emoti-Gotchi</h1>
          <p className="text-xs text-muted-foreground">
            Privacy-first on-device support + Gemma 4 family climate
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={onOpenConsent}
          className="rounded-full bg-destructive text-destructive-foreground"
        >
          <Phone className="h-4 w-4" /> {critical ? "Safety path active" : "Consent flow"}
        </Button>
        <Button onClick={onReset} variant="outline" className="rounded-full bg-card">
          <RefreshCw className="h-4 w-4" /> Reset scene
        </Button>
      </div>
    </header>
  );
}

function Metric({ icon: Icon, label, value }: { icon: typeof Sun; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card/90 p-3 shadow-sm">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-secondary">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </p>
        <p className="truncate text-sm font-semibold">{value}</p>
      </div>
    </div>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-xl border border-border bg-card/90 p-5 shadow-sm", className)}>
      {children}
    </section>
  );
}

function SectionHeader({
  eyebrow,
  title,
  sub,
  icon: Icon,
}: {
  eyebrow: string;
  title: string;
  sub: string;
  icon: typeof Sun;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {eyebrow}
        </p>
        <h2 className="mt-1 text-base font-semibold">{title}</h2>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{sub}</p>
      </div>
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-border bg-secondary">
        <Icon className="h-4 w-4" />
      </div>
    </div>
  );
}

function SafetyStatusBar({ state }: { state: EmotiGotchiState }) {
  const action = state.current_action;
  const conflicting = action?.modality_relationship === "conflicting";
  const label = state.is_critical_escalation
    ? "Guardian safety path active"
    : conflicting
      ? "Support recommended"
      : "Safety audit passed";
  const detail = state.is_critical_escalation
    ? (state.escalation_reason ?? "Deterministic safety threshold reached.")
    : conflicting
      ? "Gemma E2B noticed that language and acoustic signals disagree."
      : "No deterministic risk threshold was reached.";
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border p-4 sm:flex-row sm:items-center sm:justify-between",
        state.is_critical_escalation
          ? "border-destructive/40 bg-destructive/10"
          : conflicting
            ? "border-accent/50 bg-accent/10"
            : "border-success/40 bg-success/10",
      )}
    >
      <div className="flex items-start gap-3">
        {state.is_critical_escalation ? (
          <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" />
        ) : (
          <Shield className="mt-0.5 h-5 w-5 text-success-foreground" />
        )}
        <div>
          <p className="font-semibold">{label}</p>
          <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
        </div>
      </div>
      <Badge variant="outline" className="w-fit bg-card">
        Deterministic audit always on
      </Badge>
    </div>
  );
}

function EdgePanel({
  state,
  onSignalChange,
}: {
  state: EmotiGotchiState;
  onSignalChange: (
    key: "voiceStress" | "acousticStress" | "cryingProbability",
    value: number,
  ) => void;
}) {
  return (
    <Card className="h-full">
      <SectionHeader
        eyebrow="Child room / local edge"
        title="Realtime multichannel support"
        sub="Structured acoustic features stay local and drive the immediate response."
        icon={Mic}
      />
      <div className="rounded-xl border border-border bg-secondary/45 p-4">
        <div className="flex items-center justify-between gap-2">
          <Badge variant="outline" className="bg-card">
            ON-DEVICE
          </Badge>
          <span className="text-[11px] text-success-foreground">Raw audio uploaded: No</span>
        </div>
        <p className="mt-3 text-sm leading-relaxed">“{state.sensory_input.spokenText}”</p>
      </div>
      <div className="mt-4 space-y-4">
        <SignalBar
          icon={Volume2}
          label="Semantic / voice stress"
          value={state.sensory_input.voiceStress}
          onChange={(value) => onSignalChange("voiceStress", value)}
        />
        <SignalBar
          icon={Waves}
          label="Acoustic arousal"
          value={state.sensory_input.acousticStress}
          onChange={(value) => onSignalChange("acousticStress", value)}
        />
        <SignalBar
          icon={CloudRain}
          label="Crying likelihood"
          value={state.sensory_input.cryingProbability}
          onChange={(value) => onSignalChange("cryingProbability", value)}
        />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <InfoBox label="Breathing" value={state.sensory_input.breathingPattern} />
        <InfoBox
          label="Throat tremor"
          value={state.sensory_input.throatTremor ? "detected" : "clear"}
        />
      </div>
    </Card>
  );
}

function SignalBar({
  icon: Icon,
  label,
  value,
  onChange,
}: {
  icon: typeof Sun;
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="flex items-center gap-2 font-medium">
          <Icon className="h-3.5 w-3.5" />
          {label}
        </span>
        <span
          className={
            value > 70 ? "font-semibold text-destructive" : "font-semibold text-success-foreground"
          }
        >
          {value}%
        </span>
      </div>
      <Slider
        value={[value]}
        min={0}
        max={100}
        step={1}
        onValueChange={(values) => onChange(values[0] ?? 0)}
      />
    </div>
  );
}

function CapsulePanel({
  state,
  capsuleState,
}: {
  state: EmotiGotchiState;
  capsuleState: CapsuleState;
}) {
  const meta = CAPSULE_META[capsuleState];
  const strategy = state.current_action?.interaction_strategy ?? "quiet_presence";
  const strategyMeta = INTERACTION_STRATEGY_META[strategy];
  return (
    <Card className="h-full">
      <SectionHeader
        eyebrow="Child-facing support"
        title="Embodied co-regulation"
        sub="The companion validates feelings without copying or amplifying negative emotion."
        icon={HeartHandshake}
      />
      <div className="relative mx-auto flex min-h-[285px] max-w-[300px] items-center justify-center">
        <div className="absolute inset-2 rounded-full blur-3xl" style={{ background: meta.halo }} />
        <img
          src={meta.image}
          alt={`Emoti-Gotchi ${capsuleState} support state`}
          className="relative h-[260px] w-[260px] rounded-full object-cover"
        />
      </div>
      <div className="rounded-xl border border-border bg-secondary/45 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-semibold">{strategyMeta.label}</p>
          <Badge variant="outline" className="bg-card">
            {capsuleState}
          </Badge>
        </div>
        <p className="mt-2 text-sm text-foreground/80">{meta.mood}</p>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {strategyMeta.principle}
        </p>
        <p className="mt-3 text-sm font-medium">“{state.current_action?.spoken_response}”</p>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <InfoBox label="Support goal" value={state.current_action?.support_goal ?? "-"} />
        <InfoBox
          label="Signal relationship"
          value={state.current_action?.modality_relationship ?? "-"}
        />
      </div>
    </Card>
  );
}

function ParentNowPanel({
  state,
  weather,
  onOpenConsent,
  onSave,
}: {
  state: EmotiGotchiState;
  weather: Weather;
  onOpenConsent: () => void;
  onSave: () => void;
}) {
  const meta = WEATHER_META[weather];
  const Icon = meta.icon;
  const action = state.current_action;
  return (
    <Card className="h-full">
      <SectionHeader
        eyebrow="Parent phone / immediate guidance"
        title="What to do now"
        sub="A calm summary and one low-pressure action, not raw conversations."
        icon={Cloud}
      />
      <div className={cn("rounded-xl border border-border bg-gradient-to-br p-4", meta.bg)}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em]">
              Emotional weather
            </p>
            <p className="mt-1 text-2xl font-semibold">{meta.label}</p>
            <p className="text-xs text-muted-foreground">{meta.sub}</p>
          </div>
          <Icon className="h-10 w-10" />
        </div>
      </div>
      <div className="mt-4 space-y-3">
        <CoachRow tone="do" label="Do now" text={action?.guardian_action ?? "-"} />
        <CoachRow tone="avoid" label="Avoid" text={action?.guardian_avoid ?? "-"} />
        <CoachRow tone="why" label="Why it matters" text={action?.signal_summary ?? "-"} />
      </div>
      <div className="mt-4 grid gap-2">
        <Button onClick={onSave} variant="outline" className="w-full rounded-lg bg-card">
          <History className="h-4 w-4" /> Add de-identified demo event
        </Button>
        {state.is_critical_escalation ? (
          <Button
            onClick={onOpenConsent}
            className="w-full rounded-lg bg-destructive text-destructive-foreground"
          >
            <AlertTriangle className="h-4 w-4" /> Open guardian safety path
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function CoachRow({
  tone,
  label,
  text,
}: {
  tone: "do" | "avoid" | "why";
  label: string;
  text: string;
}) {
  const colors = { do: "bg-success", avoid: "bg-destructive", why: "bg-accent" };
  return (
    <div className="flex gap-3">
      <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", colors[tone])} />
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </p>
        <p className="mt-1 text-sm leading-relaxed">{text}</p>
      </div>
    </div>
  );
}

function InputPanel({
  text,
  onTextChange,
  onRun,
}: {
  text: string;
  onTextChange: (value: string) => void;
  onRun: () => void;
}) {
  const examples = [
    "I had fun playing games with my friend today.",
    "I am fine, but the room is too dark and I am scared to sleep alone.",
    "Leave me alone. I am angry and I do not want to talk.",
    "我没事，只是房间太黑了，我不敢一个人睡。",
  ];
  return (
    <Card>
      <SectionHeader
        eyebrow="Realtime demo input"
        title="On-device child support"
        sub="The child response runs immediately. Cloud Gemma is not called here."
        icon={Send}
      />
      <Textarea
        value={text}
        onChange={(event) => onTextChange(event.target.value)}
        className="min-h-24 resize-none rounded-lg bg-card"
      />
      <div className="mt-3 flex flex-wrap gap-2">
        {examples.map((example) => (
          <button
            key={example}
            onClick={() => onTextChange(example)}
            className="rounded-full border border-border bg-secondary px-3 py-1.5 text-[11px]"
          >
            {example}
          </button>
        ))}
      </div>
      <Button onClick={onRun} className="mt-4 w-full rounded-lg">
        <Play className="h-4 w-4" /> Run on-device response
      </Button>
    </Card>
  );
}

function ScenarioPanel({
  activeScenarioId,
  onRun,
}: {
  activeScenarioId: string;
  onRun: (scenario: DemoScenario) => void;
}) {
  return (
    <Card>
      <SectionHeader
        eyebrow="Reliable demo scenes"
        title="Three safety-checked scenarios"
        sub="Fixed scenes keep the judging demonstration stable."
        icon={Play}
      />
      <div className="space-y-2">
        {demoScenarios.map((scenario) => (
          <button
            key={scenario.id}
            onClick={() => onRun(scenario)}
            className={cn(
              "w-full rounded-lg border p-3 text-left",
              activeScenarioId === scenario.id
                ? "border-primary bg-primary/10"
                : "border-border bg-card",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold">{scenario.title}</span>
              <Badge variant="outline">{scenario.badge}</Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{scenario.description}</p>
          </button>
        ))}
      </div>
    </Card>
  );
}

function ComparisonPanel({
  baseline,
  multichannel,
}: {
  baseline: EmotiGotchiState;
  multichannel: EmotiGotchiState;
}) {
  return (
    <Card>
      <SectionHeader
        eyebrow="Technical proof"
        title="Text-only vs multichannel edge reasoning"
        sub="This demonstrates contradiction detection, not a validated accuracy claim."
        icon={Sparkles}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <ComparisonCard title="Text-only baseline" state={baseline} badge="SINGLE CHANNEL" />
        <ComparisonCard title="Multichannel edge" state={multichannel} badge="STRUCTURED SIGNALS" />
      </div>
    </Card>
  );
}

function ComparisonCard({
  title,
  state,
  badge,
}: {
  title: string;
  state: EmotiGotchiState;
  badge: string;
}) {
  const action = state.current_action;
  return (
    <div className="rounded-lg border border-border bg-secondary/45 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{title}</p>
        <Badge variant="outline" className="bg-card text-[9px]">
          {badge}
        </Badge>
      </div>
      <div className="mt-3 space-y-2 text-xs">
        <InfoBox label="Emotion" value={action?.emotion_detected ?? "-"} />
        <InfoBox label="Relationship" value={action?.modality_relationship ?? "-"} />
        <InfoBox label="Strategy" value={action?.interaction_strategy ?? "-"} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{action?.rationale}</p>
    </div>
  );
}

function TechnicalValidationLab({
  baseline,
  multichannel,
  cloud,
  cloudBusy,
  cloudStale,
  onRunCloud,
}: {
  baseline: EmotiGotchiState;
  multichannel: EmotiGotchiState;
  cloud: CloudBenchmark | null;
  cloudBusy: boolean;
  cloudStale: boolean;
  onRunCloud: () => void;
}) {
  return (
    <Card>
      <SectionHeader
        eyebrow="Gemma deployment proof"
        title="Same scene, three reasoning paths"
        sub="Rules and E2B update immediately. Cloud is a benchmark only and never controls the child response."
        icon={Gauge}
      />
      <div className="grid gap-3 lg:grid-cols-3">
        <ProofCard
          title="Text-only Rules"
          badge="NO GEMMA"
          state={baseline}
          footer="Fast, but cannot inspect acoustic contradiction."
        />
        <ProofCard
          title="Gemma 4 E2B Edge Sim"
          badge="REALTIME EDGE"
          state={multichannel}
          footer="Uses structured signals and remains independent from cloud latency."
          featured
        />
        <CloudProofCard cloud={cloud} busy={cloudBusy} stale={cloudStale} onRun={onRunCloud} />
      </div>
    </Card>
  );
}

function ProofCard({
  title,
  badge,
  state,
  footer,
  featured = false,
}: {
  title: string;
  badge: string;
  state: EmotiGotchiState;
  footer: string;
  featured?: boolean;
}) {
  const action = state.current_action;
  return (
    <div
      className={cn(
        "rounded-xl border p-4",
        featured ? "border-primary/50 bg-primary/10" : "border-border bg-secondary/45",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold">{title}</p>
        <Badge variant="outline" className="bg-card text-[9px]">
          {badge}
        </Badge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <InfoBox label="Emotion" value={action?.emotion_detected ?? "-"} />
        <InfoBox label="Anxiety" value={`${action?.anxiety_score ?? "-"} / 10`} />
        <InfoBox label="Signal conflict" value={action?.modality_relationship ?? "-"} />
        <InfoBox label="Strategy" value={action?.interaction_strategy ?? "-"} />
        <InfoBox
          label="Safety"
          value={state.is_critical_escalation ? "guardian path" : "audit passed"}
        />
        <InfoBox label="Latency" value={`${state.e2b_telemetry?.totalLatencyMs ?? "-"} ms`} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{footer}</p>
    </div>
  );
}

function CloudProofCard({
  cloud,
  busy,
  stale,
  onRun,
}: {
  cloud: CloudBenchmark | null;
  busy: boolean;
  stale: boolean;
  onRun: () => void;
}) {
  const result = cloud?.ok ? cloud.result : null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-semibold">Live Gemma 4 Cloud</p>
        <Badge variant="outline" className="bg-secondary text-[9px]">
          {stale ? "RESULT OUTDATED" : "BENCHMARK ONLY"}
        </Badge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <InfoBox label="Emotion" value={result?.emotion ?? "-"} />
        <InfoBox label="Anxiety" value={result ? `${result.anxietyScore} / 10` : "-"} />
        <InfoBox label="Signal conflict" value={result?.modalityRelationship ?? "-"} />
        <InfoBox label="Strategy" value={result?.interactionStrategy ?? "-"} />
        <InfoBox label="Safety" value={result?.safetyRecommendation ?? "-"} />
        <InfoBox label="Latency" value={cloud?.ok ? `${cloud.latencyMs} ms` : "-"} />
      </div>
      <Button onClick={onRun} disabled={busy} variant="outline" className="mt-4 w-full rounded-lg">
        <Cloud className="h-4 w-4" />
        {busy
          ? "Running live benchmark..."
          : cloud && !stale
            ? "Current result cached"
            : "Run live cloud benchmark"}
      </Button>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        {cloud && !cloud.ok
          ? cloud.error
          : (result?.rationale ??
            "Use a fixed synthetic scenario, then run on demand. It never blocks the child response.")}
      </p>
    </div>
  );
}

function SafetyCoverageMatrix() {
  const rows = [
    ["Calm sharing", "Basic positive match", "shared_joy", "Audit passed"],
    ["Calm words + acoustic distress", "Likely missed", "co_regulate", "Support recommended"],
    ["Anger without crisis", "Generic negative", "validate_and_contain", "No false crisis"],
    ["Explicit high risk", "Keyword hit", "safety_hold", "Guardian path forced"],
  ];
  return (
    <Card>
      <SectionHeader
        eyebrow="Safety & usefulness"
        title="Where Gemma E2B adds value without replacing safety rules"
        sub="The advantage is broader situation understanding and safer strategy selection, not an unverified accuracy claim."
        icon={Shield}
      />
      <div className="overflow-x-auto rounded-xl border border-border">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-[1.2fr_1fr_1.2fr_1fr] bg-secondary px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            <span>Scene</span>
            <span>Rules only</span>
            <span>Gemma E2B</span>
            <span>Safety audit</span>
          </div>
          {rows.map((row) => (
            <div
              key={row[0]}
              className="grid grid-cols-[1.2fr_1fr_1.2fr_1fr] border-t border-border px-4 py-3 text-xs"
            >
              {row.map((cell, index) => (
                <span key={cell} className={index === 2 ? "font-semibold text-primary" : ""}>
                  {cell}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <TraceStep
          title="1. Deterministic audit"
          text="Risk phrases and extreme thresholds always run locally."
        />
        <TraceStep
          title="2. Gemma E2B reasoning"
          text="Understands conflicting signals and selects a constrained support strategy."
        />
        <TraceStep
          title="3. Hardware schema"
          text="Only approved expressions, lights, sounds, and actions can execute."
        />
      </div>
    </Card>
  );
}

function FamilyClimatePanel({
  events,
  climate,
  onReset,
}: {
  events: FamilyEmotionEvent[];
  climate: ReturnType<typeof createFamilyClimateForecast>;
  onReset: () => void;
}) {
  const recent = events.slice(-7);
  const climateMeta: Record<FamilyClimate, { label: string; icon: typeof Sun; note: string; tone: string }> = {
    clear: { label: "Clear", icon: Sun, note: "Broadly settled", tone: "border-success/40 bg-success/10" },
    breezy: { label: "Breezy", icon: CloudSun, note: "Gentle shifts", tone: "border-accent/40 bg-accent/10" },
    unsettled: { label: "Unsettled", icon: CloudRain, note: "Reduce competing demands", tone: "border-primary/40 bg-primary/10" },
    watch: { label: "Safety watch", icon: Shield, note: "Use the explicit safety path", tone: "border-destructive/40 bg-destructive/10" },
  };
  const meta = climateMeta[climate.climate];
  const ClimateIcon = meta.icon;
  return (
    <Card>
      <SectionHeader
        eyebrow="Privacy-preserving family climate"
        title="7-Day Family Climate Forecast"
        sub="A household-level outlook, not a child behavior report. Individual events and exact counts stay hidden."
        icon={TrendingUp}
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="bg-card">DEMO SEED DATA</Badge>
        <Badge variant="outline" className="bg-card">AGGREGATE ONLY</Badge>
        <Badge variant="outline" className="bg-card">NON-DIAGNOSTIC</Badge>
        <Button onClick={onReset} size="sm" variant="outline" className="ml-auto rounded-full">
          <RefreshCw className="h-3.5 w-3.5" /> Restore seed
        </Button>
      </div>
      <div className="grid gap-4 lg:grid-cols-[.8fr_1.2fr]">
        <div className={cn("rounded-lg border p-5", meta.tone)}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Today&apos;s household climate</p>
              <p className="mt-2 text-2xl font-semibold">{meta.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">{meta.note}</p>
            </div>
            <ClimateIcon className="h-9 w-9" />
          </div>
          <div className="mt-5">
            <div className="flex items-end justify-between gap-2">
              <span className="text-xs font-semibold">Settling index</span>
              <span className="text-3xl font-semibold">{climate.settlingIndex}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-card">
              <div className="h-full rounded-full bg-success" style={{ width: `${climate.settlingIndex}%` }} />
            </div>
            <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">A household-environment indicator, not a psychological score.</p>
          </div>
        </div>
        <div className="rounded-lg border border-border bg-secondary/45 p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold">Climate wave</p>
              <p className="mt-1 text-[10px] text-muted-foreground">Relative household settling conditions across the demo week</p>
            </div>
            <Badge variant="outline" className="bg-card">{climate.broadTimeWindow}</Badge>
          </div>
          <div className="mt-5 flex h-28 items-end gap-2">
            {recent.map((event) => {
              const height = { low: 78, medium: 58, high: 36, critical: 20 }[event.anxietyBand];
              return (
                <div key={event.id} className="flex flex-1 flex-col items-center gap-1">
                  <div className={cn("w-full rounded-t-md", event.anxietyBand === "critical" ? "bg-destructive" : event.anxietyBand === "high" ? "bg-primary" : "bg-accent")} style={{ height: `${height}%` }} />
                  <span className="text-[8px] text-muted-foreground">{new Date(event.timestamp).toLocaleDateString(undefined, { weekday: "short" })}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {climate.conditions.map((condition) => (
          <div key={condition} className="rounded-lg border border-border bg-card p-3">
            <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Condition to notice</p>
            <p className="mt-2 text-sm font-semibold">{condition}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-lg border border-success/40 bg-success/10 p-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">One gentle environment adjustment</p>
        <p className="mt-2 text-sm font-semibold">{climate.environmentSuggestion}</p>
      </div>
    </Card>
  );
}

function ClimateInsightPanel({
  climate,
  insight,
  busy,
  status,
  onRun,
}: {
  climate: ReturnType<typeof createFamilyClimateForecast>;
  insight: FamilyInsight;
  busy: boolean;
  status: string;
  onRun: () => void;
}) {
  return (
    <Card>
      <SectionHeader
        eyebrow="Long-term environmental outlook / cloud"
        title="Gemma 4 Family Climate Outlook"
        sub="Cloud Gemma converts de-identified patterns into a household-level forecast. It never controls the immediate child response."
        icon={Cloud}
      />
      <div className="grid gap-4 lg:grid-cols-[1.25fr_.75fr]">
        <div className="rounded-lg border border-border bg-secondary/45 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">{climate.outlook}</p>
            <Badge variant="outline" className="bg-card">{climate.climate}</Badge>
          </div>
          <div className="mt-4 space-y-3">
            <CoachRow tone="why" label="Forecast window" text={`${climate.broadTimeWindow}; ${climate.eventCountBand} aggregate evidence.`} />
            <CoachRow tone="do" label="One environment adjustment" text={climate.environmentSuggestion} />
            <CoachRow tone="avoid" label="Avoid" text="Avoid using this forecast to interrogate, label, or reconstruct a child's private moments." />
          </div>
          <p className="mt-4 rounded-lg border border-border bg-card p-3 text-xs leading-relaxed text-muted-foreground">{climate.uncertaintyNote}</p>
          <Button onClick={onRun} disabled={busy} className="mt-4 w-full rounded-lg">
            <Sparkles className="h-4 w-4" /> {busy ? "Local forecast ready · refining in cloud..." : "Refresh climate outlook"}
          </Button>
          <p className="mt-2 text-xs text-muted-foreground">{status}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-semibold">Privacy boundary</p>
          <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">The parent forecast deliberately hides event-level behavior. Technical auditors can inspect the schema in Technical Proof without exposing it here.</p>
          <div className="mt-4 grid gap-2 text-xs">
            <InfoBox label="Raw audio" value="Not uploaded" />
            <InfoBox label="Full conversation" value="Not uploaded" />
            <InfoBox label="Exact events and counts" value="Hidden from parent view" />
            <InfoBox label="Identity fields" value="Not included" />
            <InfoBox label="Forecast data" value="Synthetic demo aggregates" />
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-muted-foreground">Internal evidence remains unavailable to the default parent view.</p>
        </div>
      </div>
    </Card>
  );
}

function FamilySafetyPanel({ state, onOpenConsent }: { state: EmotiGotchiState; onOpenConsent: () => void }) {
  return (
    <Card className={state.is_critical_escalation ? "border-destructive/50" : undefined}>
      <SectionHeader
        eyebrow="Explicit safety exception"
        title="Safety signals go directly to guardians"
        sub="Signals that need urgent attention are never reduced to a climate icon. The deterministic edge audit alerts the guardian directly."
        icon={Shield}
      />
      <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <div className={cn("rounded-lg border p-4", state.is_critical_escalation ? "border-destructive/45 bg-destructive/10" : "border-success/35 bg-success/10")}>
          <p className="flex items-center gap-2 font-semibold">
            {state.is_critical_escalation ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            {state.is_critical_escalation ? "Guardian Safety Alert is active" : "Deterministic safety audit is standing by"}
          </p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{state.escalation_reason ?? "Risk phrases and extreme acoustic thresholds are checked locally, even when Gemma or the network is unavailable."}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs font-semibold">Child psychology consultation referral</p>
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">After reviewing the minimum de-identified summary, a guardian can authorize a referral to a vetted child-psychology professional. This demo previews the flow and does not contact a real clinician.</p>
          <Button onClick={onOpenConsent} className="mt-4 w-full rounded-lg"><Phone className="h-4 w-4" /> Prepare authorized handoff</Button>
        </div>
      </div>
    </Card>
  );
}

function FamilyLoopPanel({
  events,
  summary,
  latestEvent,
  onAction,
  onFollowUp,
  onReset,
}: {
  events: FamilyEmotionEvent[];
  summary: ReturnType<typeof summarizeFamilyHistory>;
  latestEvent: FamilyEmotionEvent | null;
  onAction: (value: GuardianAction) => void;
  onFollowUp: (value: FollowUpState) => void;
  onReset: () => void;
}) {
  const recent = events.slice(-7);
  const triggerCounts = recent.reduce<Record<string, number>>(
    (counts, event) => ({
      ...counts,
      [event.triggerCategory]: (counts[event.triggerCategory] ?? 0) + 1,
    }),
    {},
  );
  const maxCount = Math.max(1, ...Object.values(triggerCounts));
  return (
    <Card>
      <SectionHeader
        eyebrow="Parent action loop"
        title="Observe → act → record what followed"
        sub="The product shows associations after actions. It never claims that a recommendation caused improvement."
        icon={TrendingUp}
      />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="bg-card">
          DEMO SEED DATA
        </Badge>
        <Badge variant="outline" className="bg-card">
          7-DAY VIEW
        </Badge>
        <Badge variant="outline" className="bg-card">
          NON-DIAGNOSTIC
        </Badge>
        <Button onClick={onReset} size="sm" variant="outline" className="ml-auto rounded-full">
          <RefreshCw className="h-3.5 w-3.5" /> Restore seed
        </Button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-border bg-secondary/45 p-4">
          <p className="text-xs font-semibold">Recent observation</p>
          <p className="mt-2 text-sm leading-relaxed">
            {formatCategory(summary.repeatedTrigger)} is the most repeated trigger in{" "}
            {summary.totalEvents} recorded demo events.
          </p>
          <div className="mt-4 flex h-24 items-end gap-2">
            {recent.map((event) => {
              const height = { low: 25, medium: 48, high: 72, critical: 95 }[event.anxietyBand];
              return (
                <div key={event.id} className="flex flex-1 flex-col items-center gap-1">
                  <div
                    className={cn(
                      "w-full rounded-t-sm",
                      event.anxietyBand === "critical"
                        ? "bg-destructive"
                        : event.anxietyBand === "high"
                          ? "bg-primary"
                          : "bg-accent",
                    )}
                    style={{ height: `${height}%` }}
                  />
                  <span className="text-[8px] text-muted-foreground">
                    {new Date(event.timestamp).toLocaleDateString(undefined, { weekday: "short" })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="rounded-lg border border-border bg-secondary/45 p-4">
          <p className="text-xs font-semibold">Repeated trigger factors</p>
          <div className="mt-3 space-y-3">
            {Object.entries(triggerCounts)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 4)
              .map(([trigger, count]) => (
                <div key={trigger}>
                  <div className="flex justify-between text-xs">
                    <span>{formatCategory(trigger)}</span>
                    <span>{count}</span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-accent"
                      style={{ width: `${(count / maxCount) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
          </div>
        </div>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <ChoiceGroup
          label="Guardian action taken"
          value={latestEvent?.guardianActionSelected ?? ""}
          items={GUARDIAN_ACTIONS}
          onChange={(value) => onAction(value as GuardianAction)}
        />
        <ChoiceGroup
          label="Later observed state"
          value={latestEvent?.followUpState ?? "unknown"}
          items={FOLLOW_UPS}
          onChange={(value) => onFollowUp(value as FollowUpState)}
        />
      </div>
      <div className="mt-4 rounded-lg border border-success/40 bg-success/10 p-3 text-sm">
        <p className="font-semibold">Observed association, not causation</p>
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
          {summary.actionAssociation}
        </p>
      </div>
    </Card>
  );
}

function ChoiceGroup({
  label,
  value,
  items,
  onChange,
}: {
  label: string;
  value: string;
  items: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold">{label}</p>
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(next) => next && onChange(next)}
        className="flex flex-wrap justify-start gap-2"
      >
        {items.map((item) => (
          <ToggleGroupItem
            key={item.value}
            value={item.value}
            className="h-auto rounded-full border border-border bg-card px-3 py-1.5 text-[11px] data-[state=on]:border-primary data-[state=on]:bg-primary/10"
          >
            {item.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  );
}

function FamilyInsightPanel({
  events,
  insight,
  busy,
  status,
  onRun,
}: {
  events: FamilyEmotionEvent[];
  insight: FamilyInsight;
  busy: boolean;
  status: string;
  onRun: () => void;
}) {
  const payload = events
    .slice(-7)
    .map(
      ({
        id,
        timestamp,
        emotion,
        anxietyBand,
        triggerCategory,
        modalityRelationship,
        interactionStrategy,
        guardianActionSelected,
        followUpState,
        rawAudioUploaded,
      }) => ({
        id,
        timestamp,
        emotion,
        anxietyBand,
        triggerCategory,
        modalityRelationship,
        interactionStrategy,
        guardianActionSelected,
        followUpState,
        rawAudioUploaded,
      }),
    );
  return (
    <Card>
      <SectionHeader
        eyebrow="Long-term family insight / cloud"
        title="Gemma 4 Family Insight"
        sub="Cloud Gemma analyzes structured de-identified events only. It never controls the immediate child response."
        icon={Cloud}
      />
      <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
        <div className="rounded-lg border border-border bg-secondary/45 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">{insight.observation}</p>
            <Badge variant="outline" className="bg-card">
              {insight.trend}
            </Badge>
          </div>
          <div className="mt-4 space-y-3">
            <CoachRow tone="why" label="Repeated pattern" text={insight.repeatedPattern} />
            <CoachRow tone="do" label="One gentle action" text={insight.recommendedAction} />
            <CoachRow tone="avoid" label="Avoid" text={insight.recommendedAvoid} />
          </div>
          <p className="mt-4 rounded-lg border border-border bg-card p-3 text-xs leading-relaxed text-muted-foreground">
            {insight.uncertaintyNote}
          </p>
          <p className="mt-3 text-[11px] text-muted-foreground">
            Evidence: {insight.evidenceEventIds.join(", ") || "insufficient data"}
          </p>
          <Button onClick={onRun} disabled={busy} className="mt-4 w-full rounded-lg">
            <Sparkles className="h-4 w-4" />{" "}
            {busy ? "Preview ready · refining in cloud..." : "Refresh Gemma 4 Family Insight"}
          </Button>
          <p className="mt-2 text-xs text-muted-foreground">{status}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="grid gap-2 text-xs">
            <InfoBox label="Raw audio" value="Not uploaded" />
            <InfoBox label="Full conversation" value="Not uploaded" />
            <InfoBox label="Events included" value={`${payload.length}`} />
          </div>
          <details className="mt-4 rounded-lg border border-border bg-secondary/45">
            <summary className="flex cursor-pointer items-center gap-2 p-3 text-xs font-semibold">
              <Database className="h-4 w-4" /> View de-identified upload payload
            </summary>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all border-t border-border p-3 text-[9px] leading-relaxed text-muted-foreground">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </details>
        </div>
      </div>
    </Card>
  );
}

function TracePanel({ state }: { state: EmotiGotchiState }) {
  return (
    <Card>
      <details>
        <summary className="flex cursor-pointer items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Technical details
            </p>
            <p className="mt-1 font-semibold">Open edge graph trace, schema, and telemetry</p>
          </div>
          <Activity className="h-5 w-5" />
        </summary>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <TraceStep title="local_gemma_node" text={state.current_action?.rationale ?? "-"} />
          <TraceStep
            title="security_audit_node"
            text={
              state.is_critical_escalation
                ? (state.escalation_reason ?? "P0 active")
                : "Deterministic safety audit passed."
            }
            danger={state.is_critical_escalation}
          />
          <TraceStep
            title="hardware_node"
            text={`Immediate action: ${state.current_action?.interaction_strategy ?? "-"}; cloud wait required: no.`}
          />
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <InfoBox label="Runtime" value={state.e2b_telemetry?.runtime ?? "-"} />
          <InfoBox label="Latency" value={`${state.e2b_telemetry?.totalLatencyMs ?? "-"} ms`} />
          <InfoBox label="Schema valid" value={state.e2b_telemetry?.schemaValid ? "yes" : "no"} />
          <InfoBox label="State version" value={`v${state.state_version}`} />
        </div>
      </details>
    </Card>
  );
}

function ActionProtocolProof({ state }: { state: EmotiGotchiState }) {
  const action = state.current_action;
  return (
    <Card>
      <SectionHeader
        eyebrow="Constrained action protocol"
        title="Gemma output must pass schema validation"
        sub="Gemma proposes a bounded action object. Deterministic validation decides whether hardware may execute it."
        icon={Database}
      />
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <InfoBox label="emotion_detected" value={action?.emotion_detected ?? "-"} />
        <InfoBox label="interaction_strategy" value={action?.interaction_strategy ?? "-"} />
        <InfoBox label="capsule_state" value={action?.capsule_state ?? "-"} />
        <InfoBox label="hardware_light_mode" value={action?.hardware_light_mode ?? "-"} />
        <InfoBox label="hardware_sound_trigger" value={action?.hardware_sound_trigger ?? "-"} />
        <InfoBox label="safety_level" value={action?.safety_level ?? "-"} />
        <InfoBox label="Schema valid" value={state.e2b_telemetry?.schemaValid ? "yes" : "no"} />
        <InfoBox
          label="Safety audit"
          value={state.is_critical_escalation ? "guardian path forced" : "passed"}
        />
        <InfoBox label="Cloud wait required" value="no" />
      </div>
    </Card>
  );
}

function TraceStep({
  title,
  text,
  danger = false,
}: {
  title: string;
  text: string;
  danger?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        danger ? "border-destructive/40 bg-destructive/10" : "border-success/35 bg-success/10",
      )}
    >
      <p className="flex items-center gap-2 text-sm font-semibold">
        {danger ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
        {title}
      </p>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{text}</p>
    </div>
  );
}

function InfoBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border bg-card/75 px-3 py-2">
      <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 break-words text-xs font-semibold">{value}</p>
    </div>
  );
}

function ConsentDialog({
  open,
  onOpenChange,
  state,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  state: EmotiGotchiState;
}) {
  const [handoffReady, setHandoffReady] = useState(false);
  const close = () => {
    setHandoffReady(false);
    onOpenChange(false);
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setHandoffReady(false);
        onOpenChange(next);
      }}
    >
      <DialogContent className="max-w-md rounded-xl border-destructive/30 bg-popover">
        <DialogHeader>
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-destructive text-destructive-foreground">
            <HeartHandshake className="h-6 w-6" />
          </div>
          <DialogTitle className="text-center">
            {handoffReady ? "Child psychology referral preview" : "Guardian safety path"}
          </DialogTitle>
          <DialogDescription className="text-center">
            {handoffReady
              ? "Guardian authorization recorded for this demo preview. No real clinician or external service has been contacted."
              : "Stay calm, go to the child, lower stimulation, and avoid interrogation. A child-psychology consultation referral requires explicit guardian consent."}
          </DialogDescription>
        </DialogHeader>
        {handoffReady ? (
          <div className="space-y-2">
            <InfoBox label="Shared summary" value="Safety tier + broad time window + guardian contact request" />
            <InfoBox label="Not shared" value="Raw audio, full conversation, identity profile" />
            <InfoBox label="Next real-world step" value="Guardian selects a vetted provider or local emergency resource" />
            <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-xs leading-relaxed text-muted-foreground">
              This prototype cannot provide emergency services. If there is immediate danger,
              contact local emergency services now.
            </p>
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-secondary p-3 text-xs text-muted-foreground">
            Safety reason: {state.escalation_reason ?? "Manual demo preview"}
          </div>
        )}
        <DialogFooter className="gap-2 sm:flex-col">
          {!handoffReady && (
            <Button
              onClick={() => setHandoffReady(true)}
              className="w-full rounded-lg bg-destructive text-destructive-foreground"
            >
              <Phone className="h-4 w-4" /> Authorize consultation referral preview
            </Button>
          )}
          <Button
            onClick={close}
            variant="outline"
            className="w-full rounded-lg"
          >
            {handoffReady ? "Close referral preview" : "Stay with the child first"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
