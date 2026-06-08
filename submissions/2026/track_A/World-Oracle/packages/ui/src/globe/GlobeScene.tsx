import { OrbitControls, Stars } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Suspense, useRef, useEffect, forwardRef } from "react";
import * as THREE from "three";
import { useGlobeStore } from "../stores/globeStore";
import { useSimulationStore } from "../stores/simulationStore";
import { AgentMarkers } from "./AgentMarkers";
import { ConflictHotspots } from "./ConflictHotspots";
import { Earth } from "./Earth";
import { InfluenceArcs } from "./InfluenceArcs";
import { ActionArcs } from "./ActionArcs";
import { latLngToVec3 } from "./utils";
import { getSunDirection } from "./sunPosition";

function CameraController({
	controlsRef,
	globeRef,
}: {
	controlsRef: React.RefObject<any>;
	globeRef: React.RefObject<THREE.Group | null>;
}) {
	const { camera } = useThree();
	const cameraTarget = useGlobeStore((s) => s.cameraTarget);
	const targetPos = useRef<THREE.Vector3 | null>(null);
	const animating = useRef(false);

	useEffect(() => {
		if (cameraTarget && globeRef.current) {
			const surfacePoint = latLngToVec3(cameraTarget.lat, cameraTarget.lng, 1);
			surfacePoint.applyMatrix4(globeRef.current.matrixWorld);
			const cameraPos = surfacePoint.clone().normalize().multiplyScalar(2.2);
			targetPos.current = cameraPos;
			animating.current = true;
		}
	}, [cameraTarget, globeRef]);

	useFrame(() => {
		if (animating.current && targetPos.current) {
			camera.position.lerp(targetPos.current, 0.06);
			if (controlsRef.current) {
				controlsRef.current.target.lerp(new THREE.Vector3(0, 0, 0), 0.06);
				controlsRef.current.update();
			}
			if (camera.position.distanceTo(targetPos.current) < 0.01) {
				animating.current = false;
				targetPos.current = null;
			}
		}
	});

	return null;
}

const RotatingGlobe = forwardRef<THREE.Group, { isDraggingRef: React.RefObject<boolean> }>(
	function RotatingGlobe({ isDraggingRef }, ref) {
		const groupRef = useRef<THREE.Group>(null);
		const isRunningTurn = useSimulationStore((s) => s.isRunningTurn);
		const autoSpinRef = useRef(true);

		useEffect(() => {
			if (typeof ref === "function") ref(groupRef.current);
			else if (ref) ref.current = groupRef.current;
		});

		useFrame((_, delta) => {
			// Permanently disable auto-spin once user drags or simulation runs
			if (isDraggingRef.current || isRunningTurn) {
				autoSpinRef.current = false;
			}
			if (groupRef.current && autoSpinRef.current) {
				groupRef.current.rotation.y += delta * 0.02;
			}
		});

		return (
			<group ref={groupRef}>
				<Earth />
				<AgentMarkers />
				<ConflictHotspots />
				<InfluenceArcs />
				<ActionArcs />
			</group>
		);
	},
);

function SunLight() {
	const lightRef = useRef<THREE.DirectionalLight>(null);

	useFrame(() => {
		if (lightRef.current) {
			const sunDir = getSunDirection();
			lightRef.current.position.set(sunDir.x * 5, sunDir.y * 5, sunDir.z * 5);
		}
	});

	return <directionalLight ref={lightRef} intensity={1.2} />;
}

export function GlobeScene() {
	const controlsRef = useRef<any>(null);
	const globeRef = useRef<THREE.Group>(null);
	const isDraggingRef = useRef(false);

	return (
		<div style={{ width: "100%", height: "100%", background: "#050510" }}>
			<Canvas
				camera={{ position: [0, 0, 2.5], fov: 45 }}
				gl={{ antialias: true, alpha: false }}
				style={{ background: "#050510" }}
			>
				<color attach="background" args={["#050510"]} />
				<ambientLight intensity={0.15} />
				<SunLight />
				<pointLight position={[-5, -3, -5]} intensity={0.2} color="#334466" />

				<Suspense fallback={null}>
					<RotatingGlobe ref={globeRef} isDraggingRef={isDraggingRef} />
				</Suspense>

				<Stars radius={100} depth={50} count={3000} factor={4} saturation={0} fade speed={1} />

				<CameraController controlsRef={controlsRef} globeRef={globeRef} />

				<OrbitControls
					ref={controlsRef}
					enablePan={false}
					minDistance={1.2}
					maxDistance={5}
					enableDamping
					dampingFactor={0.05}
					rotateSpeed={0.5}
					zoomSpeed={0.8}
					onStart={() => { isDraggingRef.current = true; }}
					onEnd={() => { isDraggingRef.current = false; }}
				/>
			</Canvas>
		</div>
	);
}
