import { useSimulationStore } from "../stores/simulationStore";

export function PredictionsPanel() {
	const predictions = useSimulationStore((s) => s.outcomePredictions);

	return (
		<div>
			{predictions.map((pred) => (
					<div
						key={pred.outcome}
						style={{
							padding: "8px 6px",
							borderBottom: "1px solid var(--color-border-primary)",
						}}
					>
						<div
							style={{
								display: "flex",
								justifyContent: "space-between",
								alignItems: "center",
								marginBottom: 4,
							}}
						>
							<span
								style={{
									fontSize: 10,
									color: "var(--color-text-secondary)",
									maxWidth: 190,
									overflow: "hidden",
									textOverflow: "ellipsis",
									whiteSpace: "nowrap",
								}}
							>
								{pred.outcome}
							</span>
							<div style={{ display: "flex", alignItems: "center", gap: 4 }}>
								<span
									style={{
										fontSize: 9,
										color:
											pred.trend === "up"
												? "var(--color-status-moderate)"
												: pred.trend === "down"
													? "var(--color-status-critical)"
													: "var(--color-text-muted)",
									}}
								>
									{pred.trend === "up" ? "▲" : pred.trend === "down" ? "▼" : "─"}
								</span>
								<span
									style={{
										fontSize: 11,
										fontWeight: 700,
										color: "var(--color-text-primary)",
										fontFamily: "var(--font-mono)",
									}}
								>
									{Math.round(pred.probability * 100)}%
								</span>
							</div>
						</div>
						<div
							style={{
								height: 4,
								background: "var(--color-bg-tertiary)",
								borderRadius: 2,
								overflow: "hidden",
							}}
						>
							<div
								style={{
									width: `${pred.probability * 100}%`,
									height: "100%",
									background:
										pred.probability > 0.3
											? "var(--color-status-low)"
											: pred.probability > 0.15
												? "var(--color-status-elevated)"
												: "var(--color-text-muted)",
									borderRadius: 2,
									transition: "width 0.5s ease",
								}}
							/>
						</div>
						<div
							style={{
								marginTop: 4,
								fontSize: 8,
								lineHeight: 1.35,
								color: "var(--color-text-muted)",
							}}
						>
							{pred.rationale}
						</div>
					</div>
			))}
		</div>
	);
}
