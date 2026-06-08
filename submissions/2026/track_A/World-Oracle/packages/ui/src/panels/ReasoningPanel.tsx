import { useSimulationStore } from "../stores/simulationStore";

export function ReasoningPanel() {
	const agents = useSimulationStore((s) => s.agents);
	const agentReasoning = useSimulationStore((s) => s.agentReasoning);
	const isRunningTurn = useSimulationStore((s) => s.isRunningTurn);

	const entries = agentReasoning.length > 0 ? agentReasoning : MOCK_REASONING;

	return (
		<div>
			{isRunningTurn && (
				<div
					style={{
						padding: "6px 8px",
						fontSize: 9,
						color: "var(--color-text-muted)",
						fontFamily: "var(--font-mono)",
						borderBottom: "1px solid var(--color-border-primary)",
						display: "flex",
						alignItems: "center",
						gap: 6,
					}}
				>
					<span style={{ animation: "pulse 1s infinite" }}>⬛</span>
					AGENTS REASONING...
				</div>
			)}
			{entries.map((entry, i) => {
				const agent = agents.find((a) => a.id === entry.agentId);
				return (
					<div
						key={`${entry.agentId}-${entry.turn}-${i}`}
						style={{
							padding: "8px",
							borderBottom: "1px solid var(--color-border-primary)",
						}}
					>
						<div
							style={{
								display: "flex",
								alignItems: "center",
								gap: 6,
								marginBottom: 4,
							}}
						>
							<div
								style={{
									width: 6,
									height: 6,
									borderRadius: "50%",
									background: agent?.color || "#666",
								}}
							/>
							<span
								style={{
									fontSize: 10,
									fontWeight: 600,
									color: agent?.color || "var(--color-text-secondary)",
								}}
							>
								{agent?.persona.name || entry.agentId}
							</span>
							<span
								style={{
									fontSize: 8,
									color: "var(--color-text-muted)",
									marginLeft: "auto",
									fontFamily: "var(--font-mono)",
								}}
							>
								T{entry.turn}
							</span>
						</div>
						<div
							style={{
								fontSize: 10,
								color: "var(--color-text-muted)",
								lineHeight: 1.5,
								fontStyle: "italic",
								paddingLeft: 12,
								borderLeft: `2px solid ${agent?.color || "#333"}22`,
							}}
						>
							"{entry.thought}"
						</div>
						{entry.toolTrace.length > 0 && (
							<div
								style={{
									marginTop: 6,
									paddingLeft: 12,
									display: "flex",
									flexDirection: "column",
									gap: 3,
								}}
							>
								{entry.toolTrace.slice(0, 3).map((tool) => (
									<div
										key={tool.id}
										style={{
											fontSize: 8,
											color: "var(--color-text-muted)",
											fontFamily: "var(--font-mono)",
											display: "grid",
											gridTemplateColumns: "74px 1fr",
											gap: 4,
											alignItems: "start",
										}}
									>
										<span style={{ color: "var(--color-status-live)" }}>
											{tool.status.toUpperCase()}
										</span>
										<span>
											{tool.name}: {tool.result}
										</span>
									</div>
								))}
							</div>
						)}
						{entry.memory && (
							<div
								style={{
									marginTop: 6,
									fontSize: 8,
									color: "var(--color-text-secondary)",
									fontFamily: "var(--font-mono)",
									paddingLeft: 12,
									opacity: 0.8,
								}}
							>
								MEMORY: {entry.memory}
							</div>
						)}
					</div>
				);
			})}
		</div>
	);
}

// Shown before first real turn runs
const MOCK_REASONING = [
	{
		agentId: "usa",
		turn: 47,
		thought:
			"Iranian fast-boat deployment threatens Hormuz transit. Repositioning CSG-2 to Arabian Sea to establish deterrent posture. Risk of direct engagement: 34%. Recommending DEFCON 3 posture in CENTCOM AOR.",
		memory: "Iranian maritime escalation near Hormuz increases the value of visible deterrence.",
		toolTrace: [
			{
				id: "mock-usa-memory",
				name: "retrieve_agent_memory",
				status: "context" as const,
				args: {},
				result: "Loaded prior US deterrence posture.",
			},
		],
	},
	{
		agentId: "iran",
		turn: 47,
		thought:
			"US carrier repositioning detected via satellite. Activating Hezbollah cells as diversionary measure. Fast-boat fleet to maintain harassment pattern in strait. Nuclear facility operations accelerated — estimated breakout: 6 weeks.",
		memory: "US carrier movement can be countered through proxy pressure without direct engagement.",
		toolTrace: [],
	},
	{
		agentId: "israel",
		turn: 47,
		thought:
			"Natanz activity spike confirmed by Mossad HUMINT source. Preparing contingency strike package (Operation Blue Horizon). Coordinating with US CENTCOM via back-channel. Iron Dome batteries moved to northern border.",
		memory: "Natanz activity remains the priority trigger for preemptive planning.",
		toolTrace: [],
	},
	{
		agentId: "russia",
		turn: 46,
		thought:
			"Deploying S-400 to Syrian coast signals commitment without direct engagement. Arms delivery to Iran via Caspian route authorized. UN veto preparation for any Chapter VII resolution in progress.",
		memory: "Indirect support preserves Russian leverage while avoiding direct US confrontation.",
		toolTrace: [],
	},
	{
		agentId: "china",
		turn: 46,
		thought:
			"Oil price spike threatens domestic stability. Activating Pakistan pipeline fallback. Diplomatic mediation offer prepared — leverage BRI debt with both Tehran and Gulf states. Avoid direct military entanglement.",
		memory: "Energy security and mediation leverage are linked in Gulf crisis management.",
		toolTrace: [],
	},
];
