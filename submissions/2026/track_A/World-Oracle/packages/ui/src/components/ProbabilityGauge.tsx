import { useEffect, useRef, useState } from "react";
import {
	startPolymarketRefresh,
	stopPolymarketRefresh,
	usePolymarketStore,
} from "../stores/polymarketStore";
import { useAiProbabilityStore } from "../stores/aiProbabilityStore";

const AI_COLOR = "#ff44cc";
const MKT_COLOR = "#00d4ff";

// Use strokeDasharray/strokeDashoffset for reliable arc filling.
// A semicircle's circumference = π * r
// dasharray = full semicircle length, dashoffset = unfilled portion

export function ProbabilityGauge() {
	const {
		probability,
		loading,
		lastUpdated: mktLastUpdated,
		sourceLabel,
		headline,
	} = usePolymarketStore();
	const { probability: aiProbability, lastUpdated: aiLastUpdated } = useAiProbabilityStore();

	const [mktFlash, setMktFlash] = useState(false);
	const [aiFlash, setAiFlash] = useState(false);
	const mktFlashKeyRef = useRef(0);
	const aiFlashKeyRef = useRef(0);

	useEffect(() => {
		startPolymarketRefresh();
		return () => stopPolymarketRefresh();
	}, []);

	// Flash the market arc on every refresh
	useEffect(() => {
		if (mktLastUpdated) {
			mktFlashKeyRef.current += 1;
			setMktFlash(true);
			const t = setTimeout(() => setMktFlash(false), 800);
			return () => clearTimeout(t);
		}
	}, [mktLastUpdated]);

	// Flash the AI arc on every simulation turn re-evaluation
	useEffect(() => {
		if (aiLastUpdated) {
			aiFlashKeyRef.current += 1;
			setAiFlash(true);
			const t = setTimeout(() => setAiFlash(false), 800);
			return () => clearTimeout(t);
		}
	}, [aiLastUpdated]);

	const mktPct = probability ?? 0;
	const aiPct = aiProbability;

	const aiStr = `${Math.round(aiPct * 100)}%`;
	const mktStr =
		loading && probability === null
			? "..."
			: probability !== null
				? `${Math.round(probability * 100)}%`
				: "—";

	// SVG dimensions
	const W = 160;
	const H = 110;
	const CX = W / 2;
	const CY = 88;

	const aiR = 62;
	const mktR = 38;

	// Semicircle path (left to right, curving upward)
	// M (cx-r, cy) A r r 0 0 1 (cx+r, cy)
	const aiTrack = `M${CX - aiR},${CY} A${aiR},${aiR} 0 0 1 ${CX + aiR},${CY}`;
	const mktTrack = `M${CX - mktR},${CY} A${mktR},${mktR} 0 0 1 ${CX + mktR},${CY}`;

	const aiLen = Math.PI * aiR;
	const mktLen = Math.PI * mktR;

	// dashoffset = unfilled portion (from right side)
	const aiOffset = aiLen * (1 - aiPct);
	const mktOffset = mktLen * (1 - mktPct);

	return (
		<div style={{ width: W, position: "relative", userSelect: "none" }}>
			<svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
				{/* AI track bg */}
				<path d={aiTrack} fill="none" stroke="rgba(255,68,204,0.1)" strokeWidth={5} strokeLinecap="round" />
				{/* AI filled */}
				<path
					d={aiTrack}
					fill="none"
					stroke={AI_COLOR}
					strokeWidth={5}
					strokeLinecap="round"
					strokeDasharray={aiLen}
					strokeDashoffset={aiOffset}
					style={{ transition: "stroke-dashoffset 0.8s ease" }}
				/>
				{/* AI glow */}
				<path
					d={aiTrack}
					fill="none"
					stroke={AI_COLOR}
					strokeWidth={12}
					strokeLinecap="round"
					opacity={0.08}
					strokeDasharray={aiLen}
					strokeDashoffset={aiOffset}
				/>

				{/* MKT track bg */}
				<path d={mktTrack} fill="none" stroke="rgba(0,212,255,0.08)" strokeWidth={2.5} strokeLinecap="round" />
				{/* MKT filled */}
				<path
					d={mktTrack}
					fill="none"
					stroke={MKT_COLOR}
					strokeWidth={2.5}
					strokeLinecap="round"
					opacity={0.7}
					strokeDasharray={mktLen}
					strokeDashoffset={mktOffset}
					style={{ transition: "stroke-dashoffset 0.8s ease" }}
				/>
				{/* AI refresh flash */}
				{aiFlash && (
					<path
						key={aiFlashKeyRef.current}
						d={aiTrack}
						fill="none"
						stroke={AI_COLOR}
						strokeWidth={18}
						strokeLinecap="round"
						strokeDasharray={aiLen}
						strokeDashoffset={aiOffset}
						style={{
							opacity: 0,
							animation: "mkt-flash 0.8s ease-out forwards",
						}}
					/>
				)}

				{/* MKT refresh flash */}
				{mktFlash && (
					<path
						key={mktFlashKeyRef.current}
						d={mktTrack}
						fill="none"
						stroke={MKT_COLOR}
						strokeWidth={8}
						strokeLinecap="round"
						strokeDasharray={mktLen}
						strokeDashoffset={mktOffset}
						style={{
							opacity: 0,
							animation: "mkt-flash 0.8s ease-out forwards",
						}}
					/>
				)}

				{/* Ticks on outer ring */}
				{[0, 0.25, 0.5, 0.75, 1].map((f) => {
					const a = Math.PI * (1 - f);
					const ix = CX + (aiR - 5) * Math.cos(a);
					const iy = CY - (aiR - 5) * Math.sin(a);
					const ox = CX + (aiR + 5) * Math.cos(a);
					const oy = CY - (aiR + 5) * Math.sin(a);
					return <line key={f} x1={ix} y1={iy} x2={ox} y2={oy} stroke="rgba(255,255,255,0.1)" strokeWidth={0.8} />;
				})}

				{/* 0 / 100 */}
				<text x={CX - aiR - 8} y={CY + 4} textAnchor="middle" fontSize={7} fill="rgba(255,255,255,0.18)" fontFamily="var(--font-mono)">0</text>
				<text x={CX + aiR + 10} y={CY + 4} textAnchor="middle" fontSize={7} fill="rgba(255,255,255,0.18)" fontFamily="var(--font-mono)">100</text>
			</svg>

			{/* Text */}
			<div style={{ textAlign: "center", lineHeight: 1, marginTop: -8 }}>
				<div style={{ fontSize: 22, fontWeight: 700, color: AI_COLOR, fontFamily: "var(--font-mono)" }}>
					{aiStr}
				</div>
				<div style={{ fontSize: 10, color: MKT_COLOR, fontFamily: "var(--font-mono)", opacity: 0.55, marginTop: 2 }}>
					{sourceLabel} {mktStr}
				</div>
				<div style={{ fontSize: 10, color: "var(--color-text-secondary)", fontFamily: "var(--font-mono)", fontWeight: 600, letterSpacing: "0.1em", marginTop: 4 }}>
					WAR ENDS 2026
				</div>
				<div
					style={{
						fontSize: 7,
						color: "var(--color-text-muted)",
						fontFamily: "var(--font-mono)",
						marginTop: 3,
						maxWidth: 150,
						overflow: "hidden",
						textOverflow: "ellipsis",
						whiteSpace: "nowrap",
					}}
					title={headline}
				>
					{headline}
				</div>
			</div>

			{/* Legend */}
			<div style={{ position: "absolute", top: 2, right: 0, display: "flex", flexDirection: "column", gap: 3 }}>
				<div style={{ display: "flex", alignItems: "center", gap: 4 }}>
					<div style={{ width: 8, height: 3, background: AI_COLOR, borderRadius: 1 }} />
					<span style={{ fontSize: 7, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>GEMMA</span>
				</div>
				<div style={{ display: "flex", alignItems: "center", gap: 4 }}>
					<div style={{ width: 8, height: 2, background: MKT_COLOR, borderRadius: 1, opacity: 0.6 }} />
					<span style={{ fontSize: 7, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>{sourceLabel}</span>
				</div>
			</div>
		</div>
	);
}
