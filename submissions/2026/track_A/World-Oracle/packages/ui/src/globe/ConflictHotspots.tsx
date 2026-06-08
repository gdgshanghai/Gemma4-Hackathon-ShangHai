import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";
import { useSimulationStore } from "../stores/simulationStore";
import { latLngToVec3 } from "./utils";

export function ConflictHotspots() {
	const conflicts = useSimulationStore((s) => s.conflicts);

	return (
		<group>
			{conflicts.map((conflict) => (
				<Hotspot
					key={conflict.id}
					name={conflict.name}
					lat={conflict.location.lat}
					lng={conflict.location.lng}
					intensity={conflict.intensity}
					type={conflict.type}
				/>
			))}
		</group>
	);
}

function Hotspot({
	name,
	lat,
	lng,
	intensity,
	type,
}: {
	name: string;
	lat: number;
	lng: number;
	intensity: number;
	type: string;
}) {
	const groupRef = useRef<THREE.Group>(null);
	const outerRef = useRef<THREE.Mesh>(null);
	const innerRef = useRef<THREE.Mesh>(null);
	const position = useMemo(() => latLngToVec3(lat, lng, 1.008), [lat, lng]);

	const color = useMemo(() => {
		switch (type) {
			case "conventional":
				return "#ff2244";
			case "proxy":
				return "#ff6622";
			case "cyber":
				return "#00ffcc";
			case "hybrid":
				return "#ff44aa";
			default:
				return "#ffaa00";
		}
	}, [type]);

	useFrame(({ clock }) => {
		const t = clock.getElapsedTime();
		if (outerRef.current) {
			const scale = 1 + Math.sin(t * 3 + lat) * 0.4 * intensity;
			outerRef.current.scale.setScalar(scale);
			(outerRef.current.material as THREE.MeshBasicMaterial).opacity =
				0.15 + Math.sin(t * 2) * 0.1;
		}
		if (innerRef.current) {
			(innerRef.current.material as THREE.MeshBasicMaterial).opacity =
				0.5 + Math.sin(t * 4) * 0.2;
		}
	});

	const size = 0.008 + intensity * 0.012;

	// Orient the group so circles face outward from globe center
	const quaternion = useMemo(() => {
		const normal = position.clone().normalize();
		const q = new THREE.Quaternion();
		q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
		return q;
	}, [position]);

	return (
		<group position={position} quaternion={quaternion}>
			{/* Outer pulse */}
			<mesh ref={outerRef}>
				<circleGeometry args={[size * 1.5, 32]} />
				<meshBasicMaterial
					color={color}
					transparent
					opacity={0.15}
					side={THREE.DoubleSide}
					depthWrite={false}
				/>
			</mesh>

			{/* Inner glow */}
			<mesh ref={innerRef}>
				<circleGeometry args={[size, 32]} />
				<meshBasicMaterial
					color={color}
					transparent
					opacity={0.5}
					side={THREE.DoubleSide}
					depthWrite={false}
				/>
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
						fontSize: "8px",
						fontFamily: "JetBrains Mono, monospace",
						fontWeight: 500,
						textTransform: "uppercase",
						letterSpacing: "0.05em",
						whiteSpace: "nowrap",
						textShadow: "0 0 8px rgba(0,0,0,0.9), 0 0 16px rgba(0,0,0,0.6)",
						opacity: 0.7,
					}}
				>
					{name}
				</div>
			</Html>
		</group>
	);
}
