import { useSimulationStore } from "../stores/simulationStore";

export function RelationsPanel() {
	const agents = useSimulationStore((s) => s.agents);

	// Build pairwise relations
	const pairs: {
		a: string;
		b: string;
		colorA: string;
		colorB: string;
		alignment: number;
		label: string;
	}[] = [];

	for (let i = 0; i < agents.length; i++) {
		for (let j = i + 1; j < agents.length; j++) {
			const rel = agents[i].relationships[agents[j].id];
			if (rel) {
				pairs.push({
					a: agents[i].persona.name,
					b: agents[j].persona.name,
					colorA: agents[i].color,
					colorB: agents[j].color,
					alignment: rel.alignment,
					label:
						rel.alignment > 50
							? "Allied"
							: rel.alignment > 0
								? "Neutral+"
								: rel.alignment > -50
									? "Tense"
									: "Hostile",
				});
			}
		}
	}

	return (
		<div>
			{pairs.map((pair) => {
					const pct = ((pair.alignment + 100) / 200) * 100;
					const barColor =
						pair.alignment > 50
							? "var(--color-status-moderate)"
							: pair.alignment > 0
								? "var(--color-status-low)"
								: pair.alignment > -50
									? "var(--color-status-elevated)"
									: "var(--color-status-critical)";

					return (
						<div
							key={`${pair.a}-${pair.b}`}
							style={{
								padding: "6px 4px",
								borderBottom: "1px solid var(--color-border-primary)",
							}}
						>
							<div
								style={{
									display: "flex",
									justifyContent: "space-between",
									alignItems: "center",
									marginBottom: 3,
								}}
							>
								<div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 9 }}>
									<span style={{ color: pair.colorA, fontWeight: 600 }}>{pair.a}</span>
									<span style={{ color: "var(--color-text-muted)" }}>↔</span>
									<span style={{ color: pair.colorB, fontWeight: 600 }}>{pair.b}</span>
								</div>
								<span
									style={{
										fontSize: 8,
										color: barColor,
										fontWeight: 600,
									}}
								>
									{pair.label}
								</span>
							</div>
							<div
								style={{
									height: 3,
									background: "var(--color-bg-tertiary)",
									borderRadius: 2,
									overflow: "hidden",
								}}
							>
								<div
									style={{
										width: `${pct}%`,
										height: "100%",
										background: barColor,
										borderRadius: 2,
									}}
								/>
							</div>
						</div>
					);
			})}
		</div>
	);
}
