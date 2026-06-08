import { useSimulationStore } from "../stores/simulationStore";
import { useGlobeStore } from "../stores/globeStore";

export function AgentPanel() {
	const agents = useSimulationStore((s) => s.agents);
	const selectedAgentId = useGlobeStore((s) => s.selectedAgentId);
	const setSelectedAgent = useGlobeStore((s) => s.setSelectedAgent);
	const setCameraTarget = useGlobeStore((s) => s.setCameraTarget);

	return (
		<div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
				{agents.map((agent) => {
					const isSelected = selectedAgentId === agent.id;
					return (
						<button
							key={agent.id}
							onClick={() => {
								const nextId = isSelected ? null : agent.id;
								setSelectedAgent(nextId);
								if (nextId) {
									setCameraTarget({ lat: agent.position.lat, lng: agent.position.lng });
								}
							}}
							type="button"
							style={{
								display: "flex",
								flexDirection: "column",
								gap: 6,
								padding: "8px 10px",
								background: isSelected
									? "var(--color-bg-tertiary)"
									: "var(--color-bg-panel)",
								border: isSelected
									? `1px solid ${agent.color}33`
									: "1px solid transparent",
								borderRadius: 3,
								cursor: "pointer",
								textAlign: "left",
								width: "100%",
								color: "inherit",
								fontFamily: "inherit",
							}}
						>
							<div style={{ display: "flex", alignItems: "center", gap: 8 }}>
								<div
									style={{
										width: 8,
										height: 8,
										borderRadius: "50%",
										background: agent.color,
										boxShadow: `0 0 6px ${agent.color}`,
									}}
								/>
								<span
									style={{
										fontSize: 11,
										fontWeight: 600,
										color: agent.color,
									}}
								>
									{agent.persona.name}
								</span>
								<span
									style={{
										fontSize: 9,
										color: "var(--color-text-muted)",
										marginLeft: "auto",
									}}
								>
									{agent.persona.role}
								</span>
							</div>

							{/* Resource bars */}
							<div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
								<ResourceBar
									label="MIL"
									value={agent.resources.military}
									color="var(--color-status-critical)"
								/>
								<ResourceBar
									label="ECO"
									value={agent.resources.economic}
									color="var(--color-status-elevated)"
								/>
								<ResourceBar
									label="POL"
									value={agent.resources.political}
									color="var(--color-status-low)"
								/>
								<ResourceBar
									label="INT"
									value={agent.resources.intelligence}
									color="var(--color-influence-intelligence)"
								/>
							</div>

							{/* Morale & Stability */}
							<div
								style={{
									display: "flex",
									gap: 12,
									fontSize: 9,
									color: "var(--color-text-muted)",
								}}
							>
								<span>
									MORALE{" "}
									<span style={{ color: "var(--color-text-secondary)" }}>
										{agent.morale}
									</span>
								</span>
								<span>
									STAB{" "}
									<span style={{ color: "var(--color-text-secondary)" }}>
										{agent.stability}
									</span>
								</span>
							</div>

							{/* Strategy */}
							{isSelected && (
								<div
									style={{
										fontSize: 9,
										color: "var(--color-text-muted)",
										fontStyle: "italic",
										borderTop: "1px solid var(--color-border-primary)",
										paddingTop: 4,
										marginTop: 2,
									}}
								>
									{agent.currentStrategy}
								</div>
							)}
						</button>
					);
				})}
		</div>
	);
}

function ResourceBar({
	label,
	value,
	color,
}: { label: string; value: number; color: string }) {
	return (
		<div style={{ display: "flex", alignItems: "center", gap: 6 }}>
			<span
				style={{
					fontSize: 8,
					color: "var(--color-text-muted)",
					width: 22,
					fontFamily: "var(--font-mono)",
				}}
			>
				{label}
			</span>
			<div
				style={{
					flex: 1,
					height: 3,
					background: "var(--color-bg-tertiary)",
					borderRadius: 1,
					overflow: "hidden",
				}}
			>
				<div
					style={{
						width: `${value}%`,
						height: "100%",
						background: color,
						borderRadius: 1,
						opacity: 0.7,
					}}
				/>
			</div>
			<span
				style={{
					fontSize: 8,
					color: "var(--color-text-muted)",
					width: 18,
					textAlign: "right",
					fontFamily: "var(--font-mono)",
				}}
			>
				{value}
			</span>
		</div>
	);
}
