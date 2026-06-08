import { useSimulationStore } from "../stores/simulationStore";

export function TimelinePanel() {
	const turn = useSimulationStore((s) => s.turn);

	// Mock timeline data points
	const conflictIntensity = [
		15, 18, 22, 25, 20, 28, 35, 42, 48, 45, 52, 55, 50, 58, 62, 65, 60, 68, 72, 70, 75, 78,
		74, 80, 82, 78, 85, 82, 80, 78, 82, 85, 88, 85, 82, 78, 80, 85, 88, 90, 85, 82, 78, 75,
		78, 82, 85,
	];

	const maxVal = Math.max(...conflictIntensity);
	const barWidth = 100 / conflictIntensity.length;

	return (
		<div style={{ padding: "4px 0" }}>
				{/* Mini bar chart */}
				<div
					style={{
						display: "flex",
						alignItems: "flex-end",
						height: 60,
						gap: 1,
					}}
				>
					{conflictIntensity.map((val, i) => {
						const height = (val / maxVal) * 100;
						const isCurrent = i === conflictIntensity.length - 1;
						const color =
							val > 80
								? "var(--color-status-critical)"
								: val > 60
									? "var(--color-status-high)"
									: val > 40
										? "var(--color-status-elevated)"
										: "var(--color-status-low)";

						return (
							<div
								key={i}
								style={{
									flex: 1,
									height: `${height}%`,
									background: isCurrent ? color : `${color}88`,
									borderRadius: "1px 1px 0 0",
									minWidth: 2,
									transition: "height 0.3s ease",
								}}
							/>
						);
					})}
				</div>

				{/* Key events markers */}
				<div
					style={{
						marginTop: 12,
						borderTop: "1px solid var(--color-border-primary)",
						paddingTop: 8,
					}}
				>
					{[
						{ turn: 1, label: "War Declared", color: "var(--color-status-critical)" },
						{ turn: 12, label: "First Strike", color: "var(--color-status-high)" },
						{ turn: 24, label: "Stalemate", color: "var(--color-status-elevated)" },
						{ turn: 36, label: "Re-escalation", color: "var(--color-status-high)" },
						{ turn: 47, label: "Current", color: "var(--color-status-live)" },
					].map((evt) => (
						<div
							key={evt.turn}
							style={{
								display: "flex",
								alignItems: "center",
								gap: 8,
								padding: "3px 0",
								fontSize: 9,
							}}
						>
							<span
								style={{
									width: 6,
									height: 6,
									borderRadius: "50%",
									background: evt.color,
									flexShrink: 0,
								}}
							/>
							<span style={{ color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
								T{evt.turn}
							</span>
							<span style={{ color: "var(--color-text-secondary)" }}>{evt.label}</span>
						</div>
					))}
				</div>
		</div>
	);
}
