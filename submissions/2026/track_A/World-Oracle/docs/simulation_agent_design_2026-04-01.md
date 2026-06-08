# World Oracle: Agent Simulation Design Document

**Date:** 2026-04-01
**Status:** Draft for review
**Context:** US-Iran conflict escalation scenario, informed by Polymarket intelligence report

---

## 1. Why Polymarket Alone Is Insufficient

Polymarket answers: **"What will happen?"** (probability of outcomes)
Simulation needs: **"Why will it happen, and what happens next?"** (causal reasoning)

A simulation engine must model **decision-making agents** that interact, react, and adapt. Each agent needs:
- **Objectives** — what they're trying to achieve
- **Capabilities** — what tools/resources they have
- **Constraints** — what limits their actions
- **Doctrine** — how they make decisions under uncertainty
- **Relationships** — how they relate to every other agent

Polymarket serves as an **output validation layer**: if our simulation produces outcomes wildly divergent from market consensus, either we're wrong or we've found an edge the market hasn't priced in.

---

## 2. Data Source Strategy

### Tier 1: Polymarket (already integrated)
- Binary outcome probabilities with conviction weighting
- Event timeline and sequencing
- Real-time sentiment shifts
- **Role:** Calibration & validation

### Tier 2: Structured OSINT (needed)
- Military order of battle (IISS, GlobalFirepower)
- Economic data (World Bank, IMF, OPEC reports)
- Diplomatic cables and UN voting records
- Sanctions lists and trade flow data
- **Role:** Agent capability initialization

### Tier 3: LLM-Synthesized Intelligence (proposed)
- Use Claude/GPT to synthesize agent doctrines from public speeches, military strategy documents, historical behavior patterns
- Generate structured decision trees per agent
- **Role:** Agent behavior modeling

### Tier 4: Real-Time Feeds (future)
- News APIs (Reuters, AP) for event triggers
- Oil price feeds (Brent, WTI)
- Stock indices (defense sector, tech, emerging markets)
- Shipping data (Strait of Hormuz transit)
- **Role:** Live scenario injection

---

## 3. Agent Dossiers

### 3.1 UNITED STATES

**Role in Conflict:** Primary aggressor / coalition leader

**Objectives:**
1. Prevent Iranian nuclear breakout (existential red line for allies)
2. Degrade Iranian military infrastructure
3. Maintain Strait of Hormuz freedom of navigation
4. Avoid protracted ground war (domestic political constraint)
5. Demonstrate credibility of US extended deterrence globally

**Military Capabilities:**
- 50,000+ troops deployed to CENTCOM AOR (as of Mar 2026)
- 2 carrier strike groups (CSG) in Arabian Sea / Persian Gulf
- B-2/B-52 strategic bombers operating from Diego Garcia and Qatar
- F-35A/F-22 air superiority from UAE/Bahrain bases
- Tomahawk cruise missile inventory (~4,000 in theater estimate)
- Cyber Command capabilities (Stuxnet precedent)
- Special Operations Command (JSOC) assets in region
- Space-based ISR (real-time satellite coverage)

**Economic Leverage:**
- SWIFT sanctions authority
- Dollar hegemony / OFAC enforcement
- Strategic Petroleum Reserve (~400M barrels)
- Defense budget: ~$900B/yr

**Constraints:**
- Domestic war fatigue (post-Iraq/Afghanistan)
- 2026 midterm elections (November)
- Trump removal priced at 52.5% — policy continuity uncertain
- Overstretched military if China-Taiwan flares simultaneously
- Oil price sensitivity (domestic inflation)
- Congressional authorization questions for ground operations

**Doctrine:**
- Air-first, minimize ground footprint
- "Maximum pressure" economic warfare
- Coalition-dependent (needs Israel, Gulf states for basing)
- Escalation dominance philosophy but politically constrained on duration

**Historical Behavior Patterns:**
- 2020: Soleimani strike — targeted assassination, no follow-up ground war
- 2003: Iraq — full invasion when diplomacy exhausted
- 1988: Operation Praying Mantis — limited naval engagement with Iran
- Pattern: Prefers decisive strikes over prolonged engagement

---

### 3.2 IRAN (Islamic Republic)

**Role in Conflict:** Primary defender / asymmetric warfare actor

**Current Status:** Supreme Leader Khamenei killed Feb 2026. Mojtaba Khamenei designated successor. IRGC holds operational control. Regime survival at 89.5% per Polymarket.

**Objectives:**
1. Regime survival (overriding priority)
2. Nuclear capability preservation or acceleration
3. Deter ground invasion through cost imposition
4. Maintain proxy network activation capability
5. Preserve territorial integrity
6. Rally domestic support through nationalism

**Military Capabilities:**
- IRGC: ~190,000 (ground + navy + aerospace)
- Artesh (regular army): ~420,000
- Basij militia: 90,000 active, potentially millions mobilizable
- Ballistic missiles: Shahab-3 (1,300km), Emad, Sejjil-2 (2,000km)
- Cruise missiles: Soumar, Hoveyzeh (1,350km range)
- Fast-attack boats: ~1,500 IRGCN vessels in Persian Gulf
- Drone fleet: Shahed-136 (one-way attack), Mohajer-6
- Air defense: Russian S-300PMU2, indigenous Bavar-373
- Underground facilities: Fordow (nuclear), mountain bunkers
- Anti-ship missiles: Noor, Qader (coastal defense)

**Proxy Network (force multipliers):**
- Hezbollah (Lebanon): 100,000+ rockets aimed at Israel
- Houthis (Yemen): Red Sea shipping disruption capability
- PMF/Iraqi militias: Can threaten US bases in Iraq/Syria
- Hamas remnants: Gaza destabilization
- Afghan Fatemiyoun / Pakistani Zeinabiyoun brigades

**Economic Position:**
- Oil exports: ~1.5M bpd (heavily sanctioned, China is primary buyer)
- Kharg Island: 90% of oil export capacity (not struck as of Mar 31)
- GDP: ~$400B (PPP), heavily strained by sanctions
- Currency: Severe rial depreciation
- China economic lifeline: ~$30B annual trade

**Constraints:**
- Leadership succession chaos (Mojtaba lacks father's authority)
- IRGC internal factions may fracture under pressure
- Air force largely obsolete (F-14s, MiG-29s from 1980s)
- Air defense gaps against stealth aircraft
- Economic exhaustion from decades of sanctions
- Domestic population not uniformly pro-regime
- Nuclear facilities partially damaged by strikes

**Doctrine:**
- Asymmetric / hybrid warfare (avoid conventional force-on-force)
- "Axis of Resistance" proxy activation
- Strategic patience + cost imposition
- Threaten Strait of Hormuz as economic hostage
- Underground/dispersed force posture
- Information/psychological warfare

**Historical Behavior Patterns:**
- 1980-1988: Iran-Iraq war — willingness to absorb massive casualties
- 2019-2020: Calibrated responses to US provocations (Erbil missile strike after Soleimani)
- Pattern: Prefers proxy retaliation over direct confrontation, but will escalate if existentially threatened

---

### 3.3 ISRAEL

**Role in Conflict:** Coalition partner / independent strike capability

**Objectives:**
1. Destroy Iranian nuclear capability permanently
2. Degrade Hezbollah rocket threat on northern border
3. Maintain qualitative military edge in region
4. Secure US strategic partnership and support
5. Manage domestic political coalitions

**Military Capabilities:**
- IDF active: ~170,000 (plus ~465,000 reserves)
- Air Force: F-35I Adir (50+), F-15I Ra'am, F-16I Sufa
- Ballistic missiles: Jericho III (ICBM-class, nuclear capable)
- Nuclear arsenal: ~90 warheads (undeclared)
- Iron Dome / David's Sling / Arrow-3 multi-layer missile defense
- Submarine fleet: Dolphin-class (cruise missile capable)
- Intelligence: Mossad HUMINT, Unit 8200 SIGINT (world-class)
- Cyber: Offensive capabilities (Stuxnet co-developer)
- Satellite reconnaissance: Ofek series

**Economic Position:**
- GDP: ~$540B, high-tech economy
- US military aid: $3.8B/year
- Defense spending: ~5.5% of GDP during conflict
- Tech sector globally integrated

**Constraints:**
- Rocket/missile saturation threat from Hezbollah (150,000+ rockets)
- Multi-front war risk (Lebanon, Gaza, Syria, Iran simultaneously)
- Small geographic size — no strategic depth
- Reservist-dependent military strains civilian economy
- Netanyahu political survival intertwined with war decisions (39.5% removal)
- International legitimacy concerns
- Dependent on US resupply for prolonged operations

**Doctrine:**
- Preemptive strike / "Begin Doctrine" (prevent existential threats)
- Air superiority as foundation
- Intelligence-led precision targeting
- Rapid decisive operations (avoid prolonged campaigns)
- Nuclear ambiguity as ultimate deterrent

**Historical Behavior Patterns:**
- 1981: Osirak reactor strike (Iraq)
- 2007: Al-Kibar reactor strike (Syria)
- 2023-2024: Gaza operations — willingness to sustain international criticism
- Pattern: Will act unilaterally on existential nuclear threats

---

### 3.4 RUSSIA

**Role in Conflict:** Iranian ally / strategic opportunist

**Objectives:**
1. Preserve influence in Middle East (Syria, Iran)
2. Distract US attention from Ukraine
3. Sell arms and gain leverage
4. Prevent precedent of regime change via airstrikes (own vulnerability)
5. Maintain energy market influence
6. Secure diplomatic relevance as mediator

**Military Capabilities (relevant to this theater):**
- S-400 deployment to Syrian coast
- Naval presence in Mediterranean (Tartus base)
- Arms supply pipeline to Iran (Caspian route)
- Nuclear arsenal (strategic deterrent against US escalation)
- Limited direct intervention capacity (forces committed in Ukraine)

**Economic Leverage:**
- Energy superpower: Oil + gas exports
- Arms sales to Iran, Syria, others
- BRICS alternative financial infrastructure
- UN Security Council veto

**Constraints:**
- Military heavily committed in Ukraine
- Cannot directly confront US militarily without nuclear escalation
- Economic sanctions already constraining
- Ceasefire probability (54.5%) may redirect attention
- Dependent on China for economic survival

**Doctrine:**
- Indirect support (arms, intelligence, diplomatic cover)
- UN veto as shield
- Escalation management (avoid direct US-Russia confrontation)
- Arms deliveries via deniable channels
- Information warfare / disinformation campaigns

**Historical Behavior Patterns:**
- 2015-present: Syria intervention (direct military, air campaign)
- 2022: Ukraine — willingness to absorb massive costs for strategic goals
- Pattern: Will provide material support to Iran but avoid direct military confrontation with US

---

### 3.5 CHINA

**Role in Conflict:** Economic stakeholder / strategic calculator

**Objectives:**
1. Secure energy supply (Iran is major oil supplier)
2. Avoid disruption to BRI investments in region
3. Observe US military performance/capacity for Taiwan planning
4. Position as diplomatic mediator for global influence
5. Prevent oil price spike from destabilizing domestic economy
6. Maintain strategic ambiguity on Taiwan

**Military Capabilities (relevant to this theater):**
- PLAN anti-piracy task force in Gulf of Aden
- Djibouti military base
- No direct combat role expected
- Growing naval capability (but focused on Western Pacific)

**Economic Leverage:**
- Iran's largest oil buyer (~700K bpd)
- BRI debt leverage across Gulf states and Iran
- Pakistan pipeline as alternative energy route
- Manufacturing dependency leverage over global supply chains
- $3T+ foreign reserves

**Constraints:**
- Taiwan situation (51.5% invasion probability — may be the real play)
- Domestic economic slowdown
- No alliance treaty with Iran
- Doesn't want to be seen as anti-US (trade relationship)
- Limited military projection in Middle East

**Doctrine:**
- Economic leverage over military force
- Strategic patience / "hide and bide"
- Diplomatic mediation offers (leverage BRI debts)
- Avoid direct military entanglement
- Use crises to test US multi-theater capacity

**Critical Question for Simulation:**
China-Taiwan at 51.5% is the elephant in the room. Is the Iran conflict creating a window of opportunity? The simulation must model whether China interprets US overextension as an invitation.

---

### 3.6 SAUDI ARABIA

**Role in Conflict:** Hedging regional power / US ally with independent interests

**Objectives:**
1. Prevent Iranian regional hegemony
2. Protect oil infrastructure (Aramco, Ras Tanura)
3. Maintain OPEC+ production leverage
4. Avoid becoming a target for Iranian retaliation
5. Diversify alliances (China, Russia relationships)
6. Vision 2030 economic transformation continuity

**Military Capabilities:**
- Modern air force: F-15SA, Eurofighter Typhoon
- Patriot PAC-3 / THAAD missile defense
- Naval forces in Persian Gulf and Red Sea
- National Guard: ~100,000
- Overflight/basing permissions critical for US operations

**Economic Leverage:**
- OPEC swing producer (~10M bpd capacity)
- Sovereign wealth fund: ~$700B (PIF)
- Oil price manipulation capability
- US arms customer (~$100B in deals)

**Constraints:**
- Houthi threat from Yemen (drone/missile attacks on oil facilities)
- 2019 Aramco attack precedent — vulnerability to Iranian proxies
- Cannot afford to alienate China (largest oil customer)
- Domestic stability depends on economic growth (Vision 2030)
- MBS needs to balance US alignment with regional hedging

**Doctrine:**
- Checkbook diplomacy
- Coalition participation without leading
- Oil production as geopolitical weapon
- Private channels / back-channel diplomacy
- Externalize defense costs to US

---

### 3.7 HOUTHIS (Ansar Allah)

**Role in Conflict:** Iranian proxy / Red Sea disruptor

**Objectives:**
1. Demonstrate relevance to Iran's axis of resistance
2. Disrupt Red Sea shipping (economic warfare)
3. Gain domestic legitimacy in Yemen
4. Force international recognition
5. Target Saudi Arabia and UAE interests

**Military Capabilities:**
- Anti-ship ballistic missiles (targeting Red Sea shipping)
- Iranian-supplied drones (Shahed variants)
- Ballistic missiles targeting Saudi Arabia
- Asymmetric naval warfare (sea mines, suicide boats)
- Estimated 20,000-30,000 fighters

**Economic Impact:**
- Red Sea shipping disruption (12-15% of global trade)
- Insurance cost spikes for Suez transit
- Rerouting around Cape of Good Hope adds 10-14 days + fuel costs
- Oil tanker targeting capability

**Constraints:**
- Dependent on Iranian supply chain (weapons, training, funding)
- Limited air defense against US/coalition strikes
- Internal Yemen fragmentation
- No international legitimacy
- Supply lines vulnerable to naval interdiction

**Doctrine:**
- Asymmetric harassment / cost imposition
- "Flood the zone" with cheap drones/missiles
- Target high-value commercial shipping
- Propaganda warfare (Al Masirah TV)
- Coordinate timing with Iranian strategic objectives

---

### 3.8 HEZBOLLAH

**Role in Conflict:** Iranian proxy / northern front threat to Israel

**Objectives:**
1. Deter Israeli action through rocket threat
2. Support Iranian strategic objectives
3. Maintain political power in Lebanon
4. Force multi-front war on Israel if activated
5. Organizational survival post-2024 leadership losses

**Military Capabilities:**
- 150,000+ rockets and missiles (short, medium, long range)
- Precision-guided munitions (Fateh-110 variants)
- Anti-tank guided missiles (Kornet, Metis-M)
- Radwan special forces (~2,000 elite fighters)
- Tunnel network along Israeli border
- Drone capabilities (Iranian-supplied)
- Total fighters: ~30,000-50,000

**Constraints:**
- Severely degraded after 2024 Israel operations (leadership losses)
- Lebanese economic collapse limits domestic support
- Supply lines from Iran through Syria vulnerable
- 2006 war devastation of southern Lebanon still in memory
- UNIFIL presence complicates operations
- Internal Lebanese politics (anti-Hezbollah factions)

**Doctrine:**
- Deterrence through rocket saturation threat
- "The equation" — calibrated retaliation for Israeli strikes
- Tunnel warfare / anti-armor ambushes
- Media/information warfare
- Integration with IRGC strategic planning

---

## 4. Relationship Matrix

Scale: -100 (hostile) to +100 (allied)

| | USA | Iran | Israel | Russia | China | Saudi | Houthis | Hezbollah |
|---|---|---|---|---|---|---|---|---|
| **USA** | — | -90 | +85 | -60 | -40 | +55 | -70 | -65 |
| **Iran** | -90 | — | -95 | +60 | +55 | -50 | +80 | +85 |
| **Israel** | +85 | -95 | — | -30 | -10 | +25 | -40 | -90 |
| **Russia** | -60 | +60 | -30 | — | +50 | +15 | +20 | +25 |
| **China** | -40 | +55 | -10 | +50 | — | +40 | 0 | 0 |
| **Saudi** | +55 | -50 | +25 | +15 | +40 | — | -85 | -40 |
| **Houthis** | -70 | +80 | -40 | +20 | 0 | -85 | — | +50 |
| **Hezbollah** | -65 | +85 | -90 | +25 | 0 | -40 | +50 | — |

---

## 5. Proposed Agent Schema

```typescript
interface AgentDossier {
  id: string;
  name: string;
  flag: string;
  color: string;

  // Role classification
  role: "state-actor" | "non-state-actor" | "proxy";
  alignment: "western-coalition" | "resistance-axis" | "independent";

  // Objectives (ordered by priority)
  objectives: {
    id: string;
    description: string;
    priority: 1 | 2 | 3 | 4 | 5; // 1 = existential
    redLine?: string; // trigger for escalation
  }[];

  // Capabilities
  capabilities: {
    military: {
      conventional: number;    // 0-100
      asymmetric: number;      // 0-100
      nuclear: number;         // 0-100
      cyber: number;           // 0-100
      airDefense: number;      // 0-100
      navalPower: number;      // 0-100
      missilePower: number;    // 0-100
      intelligence: number;    // 0-100
      forceProjection: number; // 0-100
    };
    economic: {
      gdp: number;             // billions USD
      reserves: number;        // billions USD
      sanctionResilience: number; // 0-100
      energyLeverage: number;  // 0-100
      tradeNetworks: number;   // 0-100
    };
    diplomatic: {
      unscVeto: boolean;
      allianceNetwork: number; // 0-100
      softPower: number;       // 0-100
      mediationCapability: number; // 0-100
    };
  };

  // Decision-making model
  doctrine: {
    riskTolerance: number;     // 0-100 (0=risk averse, 100=reckless)
    escalationThreshold: number; // 0-100 (how much provocation before escalating)
    preferredWarfare: ("conventional" | "asymmetric" | "economic" | "cyber" | "proxy" | "diplomatic")[];
    historicalPrecedents: string[]; // key past decisions for pattern matching
    decisionSpeed: "fast" | "moderate" | "slow"; // bureaucratic agility
  };

  // Relationships
  relationships: Record<string, {
    alignment: number;   // -100 to +100
    trust: number;       // 0-100
    dependency: number;  // 0-100 (how much this agent depends on them)
    leverageOver: number; // 0-100 (how much leverage this agent has)
  }>;

  // Constraints
  constraints: {
    domesticPolitics: string;
    economicLimits: string;
    militaryOverstretch: string;
    internationalLaw: string;
    publicOpinion: string;
  };

  // Live market calibration
  marketSignals?: {
    conditionId: string;
    description: string;
    probability: number;
    volume: number;
    lastUpdated: string;
  }[];
}
```

---

## 6. Simulation Loop Design

```
┌─────────────────────────────────────────────┐
│              SCENARIO CONTEXT                │
│  (initial conditions, event triggers)        │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│           FOR EACH TURN:                     │
│                                              │
│  1. OBSERVE: Each agent sees world state     │
│     - Other agents' last actions             │
│     - Market probability shifts              │
│     - New events / intelligence              │
│                                              │
│  2. REASON: Each agent runs decision logic   │
│     - Evaluate objectives vs current state   │
│     - Assess threats and opportunities       │
│     - Consider constraints                   │
│     - Weigh escalation vs de-escalation     │
│                                              │
│  3. ACT: Each agent selects action           │
│     - Military, economic, diplomatic, cyber  │
│     - Target selection                       │
│     - Intensity calibration                  │
│                                              │
│  4. RESOLVE: World state updates             │
│     - Actions interact (conflicts resolve)   │
│     - Casualties / damage calculated         │
│     - Economic impacts propagated            │
│     - Relationships shift                    │
│     - Global tension recalculated            │
│                                              │
│  5. VALIDATE: Compare to market signals      │
│     - Are we diverging from Polymarket?      │
│     - If so, flag for review or adjust       │
│                                              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
              NEXT TURN
```

---

## 7. Implementation Priorities

### Phase 1: Agent Data Layer
- [ ] Define `AgentDossier` TypeScript interface in shared types
- [ ] Create JSON dossier files for all 8 agents
- [ ] Integrate into simulationStore alongside existing `AgentState`
- [ ] Display enriched agent info in AgentPanel

### Phase 2: Multi-Market Polymarket Integration
- [ ] Expand `polymarket.ts` to fetch multiple market condition IDs
- [ ] Create market-to-agent mapping (which markets inform which agents)
- [ ] Build `PolymarketIntelStore` with all war-relevant markets
- [ ] Show multi-market dashboard in PredictionsPanel (replace hardcoded data)

### Phase 3: LLM-Driven Agent Reasoning
- [ ] Send agent dossier + world state + market signals to Claude API
- [ ] Each agent gets a system prompt derived from their dossier
- [ ] Claude generates reasoning + action selection per turn
- [ ] Stream reasoning to ReasoningPanel (replace mock data)

### Phase 4: Validation Loop
- [ ] After each simulation turn, compare predicted outcome trajectory to Polymarket probabilities
- [ ] Visualize divergence on the ProbabilityGauge (AI vs Market)
- [ ] Flag scenarios where simulation disagrees with market for analyst review

---

## 8. Open Questions

1. **Turn duration:** What does one turn represent? Hours? Days? Weeks? This affects action granularity.
2. **Fog of war:** Should agents have perfect information or limited visibility? Asymmetric info makes it more realistic but harder to implement.
3. **Stochastic vs deterministic:** Should identical inputs produce identical outputs, or should there be randomness?
4. **Player mode:** Should a human be able to take over any agent's decisions?
5. **Multi-scenario:** Should we run Monte Carlo simulations (1000+ runs) to generate probability distributions, or focus on single narrative runs?
6. **China-Taiwan coupling:** The 51.5% Taiwan invasion probability suggests this isn't independent of the Iran conflict. Should we model it as a correlated event?

---

*This document should be reviewed and iterated on before implementation begins. The agent dossiers contain assessments that reflect market signals and public information as of 2026-04-01 and will need updating as the situation evolves.*
