import { useFrame, extend } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";
import { useSimulationStore } from "../stores/simulationStore";
import { latLngToVec3 } from "./utils";

extend({ Line_: THREE.Line });

export function InfluenceArcs() {
	const agents = useSimulationStore((s) => s.agents);
	const conflicts = useSimulationStore((s) => s.conflicts);

	// Create arcs from agents to conflicts they're involved in
	const arcs = useMemo(() => {
		const result: { from: THREE.Vector3; to: THREE.Vector3; color: string }[] = [];
		for (const conflict of conflicts) {
			for (const partyId of conflict.parties) {
				const agent = agents.find((a) => a.id === partyId);
				if (agent) {
					result.push({
						from: latLngToVec3(agent.position.lat, agent.position.lng, 1.005),
						to: latLngToVec3(conflict.location.lat, conflict.location.lng, 1.005),
						color: agent.color,
					});
				}
			}
		}
		return result;
	}, [agents, conflicts]);

	return (
		<group>
			{arcs.map((arc, i) => (
				<Arc key={i} from={arc.from} to={arc.to} color={arc.color} />
			))}
		</group>
	);
}

function Arc({
	from,
	to,
	color,
}: {
	from: THREE.Vector3;
	to: THREE.Vector3;
	color: string;
}) {
	const lineRef = useRef<THREE.Line>(null);

	const geometry = useMemo(() => {
		const points: THREE.Vector3[] = [];
		const mid = new THREE.Vector3().addVectors(from, to).multiplyScalar(0.5);
		// Lift the midpoint away from the globe surface for arc effect
		const midNorm = mid.clone().normalize();
		const dist = from.distanceTo(to);
		mid.add(midNorm.multiplyScalar(dist * 0.3));

		const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
		const curvePoints = curve.getPoints(50);
		points.push(...curvePoints);

		const geo = new THREE.BufferGeometry().setFromPoints(points);
		return geo;
	}, [from, to]);

	useFrame(({ clock }) => {
		if (lineRef.current) {
			const mat = lineRef.current.material as THREE.LineBasicMaterial;
			mat.opacity = 0.2 + Math.sin(clock.getElapsedTime() * 2) * 0.1;
		}
	});

	return (
		<line_ ref={lineRef} geometry={geometry}>
			<lineBasicMaterial color={color} transparent opacity={0.3} depthWrite={false} />
		</line_>
	);
}
