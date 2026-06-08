import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";
import { useSimulationStore } from "../stores/simulationStore";
import { useGlobeStore } from "../stores/globeStore";
import { latLngToVec3 } from "./utils";

export function AgentMarkers() {
	const agents = useSimulationStore((s) => s.agents);
	const selectedAgentId = useGlobeStore((s) => s.selectedAgentId);
	const setSelectedAgent = useGlobeStore((s) => s.setSelectedAgent);

	return (
		<group>
			{agents.map((agent) => (
				<AgentMarker
					key={agent.id}
					id={agent.id}
					lat={agent.position.lat}
					lng={agent.position.lng}
					color={agent.color}
					name={agent.persona.name}
					isSelected={selectedAgentId === agent.id}
					onSelect={() => setSelectedAgent(agent.id)}
				/>
			))}
		</group>
	);
}

function AgentMarker({
	id,
	lat,
	lng,
	color,
	name,
	isSelected,
	onSelect,
}: {
	id: string;
	lat: number;
	lng: number;
	color: string;
	name: string;
	isSelected: boolean;
	onSelect: () => void;
}) {
	const pulseRef = useRef<THREE.Mesh>(null);
	const position = useMemo(() => latLngToVec3(lat, lng, 1.012), [lat, lng]);

	// Orient so ring/circle faces outward from globe center
	const quaternion = useMemo(() => {
		const normal = position.clone().normalize();
		const q = new THREE.Quaternion();
		q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
		return q;
	}, [position]);

	useFrame(({ clock }) => {
		if (pulseRef.current) {
			const scale = 1 + Math.sin(clock.getElapsedTime() * 2) * 0.3;
			pulseRef.current.scale.setScalar(scale);
		}
	});

	return (
		<group position={position} quaternion={quaternion}>
			{/* Pulse ring — oriented outward */}
			<mesh ref={pulseRef}>
				<ringGeometry args={[0.012, 0.018, 32]} />
				<meshBasicMaterial color={color} transparent opacity={0.4} side={THREE.DoubleSide} />
			</mesh>

			{/* Core dot — small sphere so it's visible from all angles */}
			<mesh onClick={onSelect}>
				<sphereGeometry args={[0.008, 16, 16]} />
				<meshBasicMaterial color={color} />
			</mesh>

			{/* Label */}
			<Html
				position={[0, 0.04, 0]}
				center
				style={{ pointerEvents: "none", userSelect: "none" }}
			>
				<div
					style={{
						color: color,
						fontSize: "9px",
						fontFamily: "JetBrains Mono, monospace",
						fontWeight: 600,
						textTransform: "uppercase",
						letterSpacing: "0.05em",
						whiteSpace: "nowrap",
						textShadow: "0 0 8px rgba(0,0,0,0.9), 0 0 16px rgba(0,0,0,0.6)",
						opacity: isSelected ? 1 : 0.8,
					}}
				>
					{name}
				</div>
			</Html>
		</group>
	);
}
