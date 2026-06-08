import type { AgentTurnResult } from "../services/simulationEngine";

type ReplayTurnResult = Omit<AgentTurnResult, "memory" | "toolTrace">;

/**
 * Replayed from debug/run-2026-04-03_03-40-53.jsonl
 * Used for UI development without consuming API quota.
 */
export const REPLAY_FIXTURE: ReplayTurnResult[] = [
  {
    agentId: "usa",
    reasoning:
      "The rocket attack on Al-Tanf and Hezbollah rearmament signals Iranian escalation through proxies while avoiding direct attribution. With Hormuz disruption fears already priced in and China securing alternative supply routes, the window for decisive air action is narrowing. I need to degrade proxy capability immediately while preparing for potential nuclear facility strikes, using this provocation as justification without triggering full regional war.",
    action: {
      type: "military",
      target: "houthis",
      description:
        "Launch precision strikes on Kata'ib Hezbollah rocket positions and arms depots in eastern Syria using F-35s from Al-Udeid with Israeli intelligence support",
      intensity: 0.45,
    },
  },
  {
    agentId: "iran",
    reasoning:
      "US precision strikes on Kata'ib Hezbollah in Syria demonstrate continued willingness to escalate against our proxies. Direct retaliation risks exposing our remaining strategic assets to US/Israeli counterstrikes. We must escalate asymmetrically through our most capable and survivable proxy — Hezbollah in Lebanon — while maintaining plausible deniability and forcing Israel to divert resources from strikes against our homeland.",
    action: {
      type: "military",
      target: "hezbollah",
      description:
        "Authorize Hezbollah to launch precision rocket and drone saturation attack against Israeli military infrastructure in Galilee and Golan, with IRGC Quds Force providing targeting intelligence and advanced Fateh-110 guidance upgrades",
      intensity: 0.7,
    },
  },
  {
    agentId: "israel",
    reasoning:
      "Iran has escalated to 0.7 intensity with Hezbollah's precision attack on northern Israel, threatening mass casualties and forcing Iron Dome saturation. This is the multi-front scenario we've prepared for. With US already engaged against Kata'ib Hezbollah in Syria, we have operational synergy but limited time before Hezbollah's rocket inventory depletes our interceptors.",
    action: {
      type: "military",
      target: "hezbollah",
      description:
        "Launch Operation Northern Shield: F-35I Adir squadrons conduct simultaneous strikes on Hezbollah precision missile launchers, Fateh-110 storage sites, and drone infrastructure in southern Lebanon and Bekaa Valley",
      intensity: 0.8,
    },
  },
  {
    agentId: "russia",
    reasoning:
      "The US-Israel-Iran escalation creates optimal conditions for Russian objectives: US resources diverted from Ukraine, arms sales opportunities, and potential mediator role. Direct intervention risks nuclear confrontation, but deniable support to Iran and diplomatic positioning maximizes leverage while preserving escalation control.",
    action: {
      type: "intelligence",
      target: "iran",
      description:
        "Provide satellite reconnaissance and ELINT on Israeli air defense gaps and US strike patterns to IRGC via Caspian Sea secure channel, while simultaneously signaling willingness to mediate to both Washington and Tehran.",
      intensity: 0.4,
    },
  },
  {
    agentId: "china",
    reasoning:
      "US-Israel-Iran escalation creates ideal conditions to observe American multi-theater capacity and deplete precision munitions stockpiles. We must secure our energy interests and position as indispensable mediator while calculating whether this distraction opens Taiwan window.",
    action: {
      type: "diplomatic",
      target: "usa",
      description:
        "Propose confidential backchannel mediation framework to Washington offering to restrain Iranian oil revenue pressure in exchange for US commitment to Hormuz freedom of navigation guarantees.",
      intensity: 0.6,
    },
  },
  {
    agentId: "saudi",
    reasoning:
      "The regional escalation risks drawing Saudi Arabia into direct confrontation, which we must avoid. Our oil infrastructure remains vulnerable to Houthi retaliation if we appear too aligned with US/Israeli strikes. We need to signal measured cooperation with Washington while privately reassuring Tehran through backchannels that we seek de-escalation.",
    action: {
      type: "diplomatic",
      target: "usa",
      description:
        "Privately assure US of continued oil production increases and intelligence sharing on Houthi threats while demanding explicit security guarantees for Aramco facilities.",
      intensity: 0.5,
    },
  },
  {
    agentId: "houthis",
    reasoning:
      "The regional escalation creates a critical window to demonstrate strategic value to Tehran while the world's attention is focused north. With US assets concentrated on Syria-Lebanon and Israeli air defense saturated, our Red Sea position offers unique leverage.",
    action: {
      type: "military",
      target: "usa",
      description:
        "Launch coordinated drone and missile swarm against three commercial vessels near Bab el-Mandeb strait, timed to coincide with peak Israeli-Hezbollah exchange to maximize disruption.",
      intensity: 0.6,
    },
  },
  {
    agentId: "hezbollah",
    reasoning:
      "Iran's authorization for a 0.7 intensity strike combined with Israel's 0.8 intensity Operation Northern Shield places us in a dangerous escalation spiral before reconstitution is complete. Our degraded military cannot sustain a high-intensity exchange without risking organizational collapse. We must execute Iran's directive at reduced intensity.",
    action: {
      type: "military",
      target: "israel",
      description:
        "Execute limited precision rocket and drone salvo against Israeli military targets in Golan and northern Galilee, deliberately withholding 60% of remaining precision munitions to preserve core deterrent stockpile.",
      intensity: 0.4,
    },
  },
];
