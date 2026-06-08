import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";
import { useSimulationStore } from "../stores/simulationStore";
import { latLngToVec3 } from "./utils";

const TYPE_COLORS: Record<string, string> = {
  military:     "#ff4466",
  diplomatic:   "#4488ff",
  economic:     "#ffaa22",
  intelligence: "#aa44ff",
  propaganda:   "#22ddaa",
};

const TYPE_EMOJI: Record<string, string> = {
  military:     "🚀",
  diplomatic:   "✉️",
  economic:     "💰",
  intelligence: "🤖",
  propaganda:   "📢",
};

export function ActionArcs() {
  const toasts = useSimulationStore((s) => s.actionToasts);
  const agents = useSimulationStore((s) => s.agents);

  const arcs = useMemo(() => {
    return toasts.flatMap((toast) => {
      if (!toast.action.target) return [];
      const from = agents.find((a) => a.id === toast.agentId);
      const to   = agents.find((a) => a.id === toast.action.target);
      if (!from || !to) return [];
      return [{
        id:        toast.id,
        from:      latLngToVec3(from.position.lat, from.position.lng, 1.01),
        to:        latLngToVec3(to.position.lat,   to.position.lng,   1.01),
        color:     TYPE_COLORS[toast.action.type] ?? toast.agentColor,
        intensity: toast.action.intensity,
        type:      toast.action.type,
      }];
    });
  }, [toasts, agents]);

  return (
    <group>
      {arcs.map((arc) => (
        <ActionArc key={arc.id} {...arc} />
      ))}
    </group>
  );
}

function ActionArc({
  from, to, color, intensity, type,
}: {
  from: THREE.Vector3;
  to: THREE.Vector3;
  color: string;
  intensity: number;
  type: string;
}) {
  const dotGroupRef = useRef<THREE.Group>(null);
  const lineRef     = useRef<THREE.Line>(null);
  const tRef        = useRef(0);

  const curve = useMemo(() => {
    const mid  = new THREE.Vector3().addVectors(from, to).multiplyScalar(0.5);
    const lift = from.distanceTo(to) * (0.4 + intensity * 0.2);
    mid.add(mid.clone().normalize().multiplyScalar(lift));
    return new THREE.QuadraticBezierCurve3(from, mid, to);
  }, [from, to, intensity]);

  const geometry = useMemo(() => {
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(64));
  }, [curve]);

  useFrame((_, delta) => {
    tRef.current = Math.min(tRef.current + delta * 0.28, 1);
    const t = tRef.current;

    if (dotGroupRef.current) {
      dotGroupRef.current.position.copy(curve.getPoint(t));
    }

    if (lineRef.current) {
      const mat = lineRef.current.material as THREE.LineBasicMaterial;
      mat.opacity = t < 0.5 ? t * 2 * 0.6 : (1 - t) * 2 * 0.6;
    }
  });

  const threeColor = useMemo(() => new THREE.Color(color), [color]);
  const emoji = TYPE_EMOJI[type] ?? "🚀";

  return (
    <group>
      <line_ ref={lineRef} geometry={geometry}>
        <lineBasicMaterial color={threeColor} transparent opacity={0} depthWrite={false} />
      </line_>

      <group ref={dotGroupRef} position={from}>
        <Html center style={{ pointerEvents: "none", userSelect: "none" }}>
          <div style={{ fontSize: 20, lineHeight: 1, filter: "drop-shadow(0 0 4px rgba(0,0,0,0.8))" }}>
            {emoji}
          </div>
        </Html>
      </group>
    </group>
  );
}
