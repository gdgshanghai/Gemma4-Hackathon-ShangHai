import { useSimulationStore } from "../stores/simulationStore";
import { GEMMA_MODEL } from "../services/gemma";

export function Header() {
	const { status, turn, maxTurns, isPlaying, isRunningTurn, togglePlay, runTurn } = useSimulationStore();

	return (
		<header
			style={{
				display: "flex",
				alignItems: "center",
				justifyContent: "space-between",
				padding: "0 16px",
				height: 42,
				background: "var(--color-bg-secondary)",
				borderBottom: "1px solid var(--color-border-primary)",
				flexShrink: 0,
			}}
		>
			{/* Left: Logo */}
			<div style={{ display: "flex", alignItems: "center", gap: 12 }}>
				<div
					style={{
						fontSize: 13,
						fontWeight: 700,
						letterSpacing: "0.1em",
						color: "var(--color-text-primary)",
						fontFamily: "var(--font-mono)",
					}}
				>
					WORLD ORACLE
				</div>
				<div
					style={{
						fontSize: 9,
						padding: "2px 6px",
						background: "rgba(0,255,136,0.1)",
						border: "1px solid rgba(0,255,136,0.3)",
						borderRadius: 2,
						color: "var(--color-status-live)",
						fontWeight: 600,
						letterSpacing: "0.05em",
					}}
					className="animate-pulse-live"
				>
					LIVE
				</div>
			</div>

			{/* Center: Simulation controls */}
			<div style={{ display: "flex", alignItems: "center", gap: 16 }}>
				<div style={{ display: "flex", alignItems: "center", gap: 8 }}>
					<button
						onClick={runTurn}
						disabled={isRunningTurn}
						style={{
							background: "var(--color-bg-tertiary)",
							border: "1px solid var(--color-border-secondary)",
							borderRadius: 3,
							color: isRunningTurn ? "var(--color-text-muted)" : "var(--color-text-primary)",
							padding: "4px 12px",
							cursor: isRunningTurn ? "not-allowed" : "pointer",
							fontSize: 11,
							fontFamily: "var(--font-mono)",
							display: "flex",
							alignItems: "center",
							gap: 4,
						}}
					>
						{isRunningTurn ? "II GEMMA" : "▶ GEMMA TURN"}
					</button>
				</div>

				<div
					style={{
						fontSize: 11,
						color: "var(--color-text-secondary)",
						fontFamily: "var(--font-mono)",
					}}
				>
					TURN{" "}
					<span style={{ color: "var(--color-text-primary)", fontWeight: 600 }}>{turn}</span>
					<span style={{ color: "var(--color-text-muted)" }}>/{maxTurns}</span>
				</div>

				<div
					style={{
						fontSize: 11,
						color: "var(--color-text-secondary)",
						fontFamily: "var(--font-mono)",
					}}
				>
					STATUS{" "}
					<span style={{ color: "var(--color-status-live)", fontWeight: 600 }}>
						{status.toUpperCase()}
					</span>
				</div>
			</div>

			<div
				style={{
					width: 188,
					display: "flex",
					justifyContent: "flex-end",
					alignItems: "center",
					gap: 6,
					fontFamily: "var(--font-mono)",
				}}
			>
				<span
					style={{
						fontSize: 8,
						color: "var(--color-text-muted)",
						letterSpacing: "0.08em",
					}}
				>
					LOCAL
				</span>
				<span
					style={{
						fontSize: 9,
						color: "var(--color-status-live)",
						border: "1px solid rgba(0,255,136,0.25)",
						padding: "2px 5px",
						borderRadius: 2,
						maxWidth: 138,
						overflow: "hidden",
						textOverflow: "ellipsis",
						whiteSpace: "nowrap",
					}}
					title={GEMMA_MODEL}
				>
					{GEMMA_MODEL}
				</span>
			</div>
		</header>
	);
}
