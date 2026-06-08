import { useSimulationStore } from "../stores/simulationStore";

const severityColors: Record<string, string> = {
	critical: "var(--color-status-critical)",
	high: "var(--color-status-high)",
	medium: "var(--color-status-elevated)",
	low: "var(--color-status-low)",
};

const typeIcons: Record<string, string> = {
	military: "MIL",
	diplomatic: "DIP",
	economic: "ECO",
	intelligence: "INT",
	propaganda: "PSY",
};

export function IntelFeedPanel() {
	const worldEvents = useSimulationStore((s) => s.worldEvents);
	const agents = useSimulationStore((s) => s.agents);

	return (
		<div>
			{worldEvents.map((event, i) => {
					const agent = agents.find((a) => a.id === event.agentId);
					return (
						<div
							key={i}
							style={{
								padding: "6px 8px",
								borderBottom: "1px solid var(--color-border-primary)",
								display: "flex",
								flexDirection: "column",
								gap: 3,
							}}
						>
							<div style={{ display: "flex", alignItems: "center", gap: 6 }}>
								<span
									style={{
										fontSize: 8,
										fontWeight: 700,
										padding: "1px 4px",
										borderRadius: 2,
										background: `${severityColors[event.severity]}22`,
										color: severityColors[event.severity],
										fontFamily: "var(--font-mono)",
									}}
								>
									{typeIcons[event.type] || event.type.substring(0, 3).toUpperCase()}
								</span>
								<span
									style={{
										fontSize: 9,
										color: "var(--color-text-muted)",
										fontFamily: "var(--font-mono)",
									}}
								>
									T{event.turn}
								</span>
								{agent && (
									<span
										style={{
											fontSize: 9,
											color: agent.color,
											fontWeight: 600,
										}}
									>
										{agent.persona.name}
									</span>
								)}
								<span
									style={{
										marginLeft: "auto",
										width: 6,
										height: 6,
										borderRadius: "50%",
										background: severityColors[event.severity],
									}}
								/>
							</div>
							<div
								style={{
									fontSize: 10,
									color: "var(--color-text-secondary)",
									lineHeight: 1.4,
								}}
							>
								{event.description}
							</div>
						</div>
					);
			})}
		</div>
	);
}
