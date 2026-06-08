import { useEffect } from "react";
import { ActionToastOverlay } from "./components/ActionToastOverlay";
import { Header } from "./components/Header";
import { ProbabilityGauge } from "./components/ProbabilityGauge";
import { AccordionSection } from "./components/AccordionSection";
import { GlobeScene } from "./globe/GlobeScene";
import { AgentPanel } from "./panels/AgentPanel";
import { IntelFeedPanel } from "./panels/IntelFeedPanel";
import { PredictionsPanel } from "./panels/PredictionsPanel";
import { ReasoningPanel } from "./panels/ReasoningPanel";
import { RelationsPanel } from "./panels/RelationsPanel";
import { TimelinePanel } from "./panels/TimelinePanel";
import { useSimulationStore } from "./stores/simulationStore";

export function App() {
	const loadMockScenario = useSimulationStore((s) => s.loadMockScenario);
	const agents = useSimulationStore((s) => s.agents);
	const worldEvents = useSimulationStore((s) => s.worldEvents);
	const turn = useSimulationStore((s) => s.turn);
	const globalTension = useSimulationStore((s) => s.globalTension);

	useEffect(() => {
		loadMockScenario();
	}, [loadMockScenario]);

	return (
		<div
			style={{
				display: "flex",
				flexDirection: "column",
				height: "100vh",
				width: "100vw",
				overflow: "hidden",
				background: "var(--color-bg-primary)",
			}}
		>
			<Header />

			{/* Main content: Globe + Right Panel */}
			<div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
				{/* Globe — hero area */}
				<div
					style={{
						flex: 1,
						position: "relative",
						overflow: "hidden",
					}}
				>
					<GlobeScene />
					<ActionToastOverlay />

					{/* Globe overlay: event title */}
					<div
						style={{
							position: "absolute",
							top: 12,
							left: 16,
							pointerEvents: "none",
						}}
					>
						<div
							style={{
								fontSize: 14,
								fontWeight: 700,
								color: "var(--color-text-primary)",
								letterSpacing: "0.05em",
								fontFamily: "var(--font-mono)",
								textShadow: "0 2px 8px rgba(0,0,0,0.6)",
							}}
						>
							US-IRAN CONFLICT ESCALATION
						</div>
						<div
							style={{
								fontSize: 10,
								color: "var(--color-text-muted)",
								marginTop: 4,
								fontFamily: "var(--font-mono)",
								textShadow: "0 1px 4px rgba(0,0,0,0.8)",
							}}
						>
							GEMMA 4 MULTI-AGENT SIMULATION &bull; MIDDLE EAST &bull; 8 AGENTS ACTIVE
						</div>
					</div>

					{/* Probability gauge */}
					<div
						style={{
							position: "absolute",
							top: 8,
							right: 12,
							pointerEvents: "none",
						}}
					>
						<ProbabilityGauge />
					</div>

					{/* Layer toggles */}
					<div
						style={{
							position: "absolute",
							bottom: 12,
							left: 16,
							display: "flex",
							gap: 6,
						}}
					>
						{(
							[
								"military",
								"conflicts",
								"influence",
								"economic",
								"diplomatic",
							] as const
						).map((layer) => (
							<button
								key={layer}
								type="button"
								style={{
									fontSize: 8,
									padding: "3px 8px",
									background: "rgba(15,15,24,0.8)",
									border: "1px solid var(--color-border-secondary)",
									borderRadius: 2,
									color: "var(--color-text-secondary)",
									cursor: "pointer",
									fontFamily: "var(--font-mono)",
									textTransform: "uppercase",
									letterSpacing: "0.05em",
									backdropFilter: "blur(4px)",
								}}
							>
								{layer}
							</button>
						))}
					</div>
				</div>

				{/* Right sidebar — single panel with accordion sections */}
				<div
					style={{
						width: 300,
						flexShrink: 0,
						borderLeft: "1px solid var(--color-border-primary)",
						background: "var(--color-bg-panel)",
						overflowY: "auto",
						overflowX: "hidden",
					}}
				>
					<AccordionSection
						title="Agents"
						badge={agents.length}
						defaultOpen
					>
						<AgentPanel />
					</AccordionSection>

					<AccordionSection title="Timeline" defaultOpen>
						<TimelinePanel />
					</AccordionSection>

					<AccordionSection title="Agent Reasoning" defaultOpen>
						<ReasoningPanel />
					</AccordionSection>

					<AccordionSection
						title="Intel Feed"
						badge={worldEvents.length}
					>
						<IntelFeedPanel />
					</AccordionSection>

					<AccordionSection title="Relations">
						<RelationsPanel />
					</AccordionSection>

					<AccordionSection title="Predictions">
						<PredictionsPanel />
					</AccordionSection>
				</div>
			</div>
		</div>
	);
}
