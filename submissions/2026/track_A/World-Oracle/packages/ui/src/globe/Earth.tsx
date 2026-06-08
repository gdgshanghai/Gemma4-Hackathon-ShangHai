import { useTexture } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { Component, type ReactNode } from "react";
import { getSunDirection } from "./sunPosition";

const atmosphereVertexShader = `
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const atmosphereFragmentShader = `
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vec3 viewDir = normalize(-vPosition);
    float fresnel = 1.0 - dot(viewDir, vNormal);
    fresnel = pow(fresnel, 5.0);
    vec3 color = vec3(0.15, 0.3, 0.6);
    gl_FragColor = vec4(color, fresnel * 0.35);
  }
`;

const earthVertexShader = `
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vWorldNormal;
  varying vec3 vPosition;
  void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);
    vWorldNormal = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
    vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const earthFragmentShader = `
  uniform sampler2D dayMap;
  uniform sampler2D bumpMap;
  uniform sampler2D nightMap;
  uniform vec3 sunDirection;
  uniform bool hasNightMap;
  varying vec2 vUv;
  varying vec3 vNormal;
  varying vec3 vWorldNormal;
  varying vec3 vPosition;

  void main() {
    vec3 dayColor = texture2D(dayMap, vUv).rgb;
    float sunDot = dot(vWorldNormal, sunDirection);

    // Smooth transition from day to night across the terminator
    float dayFactor = smoothstep(-0.15, 0.2, sunDot);

    // Day side: lit by sun with some ambient
    vec3 litDay = dayColor * (0.3 + 0.7 * max(sunDot, 0.0));

    // Night side: dark with city lights
    vec3 nightColor;
    if (hasNightMap) {
      nightColor = texture2D(nightMap, vUv).rgb;
    } else {
      // Synthetic city lights from the day texture brightness
      float brightness = dot(dayColor, vec3(0.299, 0.587, 0.114));
      // Coastal/populated areas tend to be brighter in the day texture
      float cityMask = smoothstep(0.15, 0.5, brightness) * 0.6;
      nightColor = vec3(1.0, 0.85, 0.5) * cityMask;
    }
    vec3 darkNight = dayColor * 0.03 + nightColor;

    vec3 finalColor = mix(darkNight, litDay, dayFactor);

    // Subtle blue tint at the terminator
    float terminatorGlow = exp(-sunDot * sunDot * 40.0) * 0.15;
    finalColor += vec3(0.1, 0.15, 0.3) * terminatorGlow;

    gl_FragColor = vec4(finalColor, 1.0);
  }
`;

const EARTH_TEXTURE =
	"https://unpkg.com/three-globe@2.41.12/example/img/earth-blue-marble.jpg";
const EARTH_TOPOLOGY =
	"https://unpkg.com/three-globe@2.41.12/example/img/earth-topology.png";
const EARTH_NIGHT =
	"https://unpkg.com/three-globe@2.41.12/example/img/earth-night.jpg";

function EarthWithTexture() {
	const [colorMap, bumpMap] = useTexture([EARTH_TEXTURE, EARTH_TOPOLOGY]);
	const [nightMap, setNightMap] = useState<THREE.Texture | null>(null);
	const materialRef = useRef<THREE.ShaderMaterial>(null);

	// Load night texture separately (non-blocking)
	useEffect(() => {
		let mounted = true;
		new THREE.TextureLoader().load(EARTH_NIGHT, (tex) => {
			if (mounted) setNightMap(tex);
		});
		return () => { mounted = false; };
	}, []);

	const uniforms = useMemo(
		() => ({
			dayMap: { value: colorMap },
			bumpMap: { value: bumpMap },
			nightMap: { value: nightMap },
			sunDirection: { value: new THREE.Vector3(1, 0, 0) },
			hasNightMap: { value: nightMap !== null },
		}),
		[colorMap, bumpMap, nightMap],
	);

	// Update sun direction every frame based on real time
	useFrame(() => {
		if (materialRef.current) {
			const sunDir = getSunDirection();
			materialRef.current.uniforms.sunDirection.value.copy(sunDir);
			if (nightMap && !materialRef.current.uniforms.hasNightMap.value) {
				materialRef.current.uniforms.nightMap.value = nightMap;
				materialRef.current.uniforms.hasNightMap.value = true;
			}
		}
	});

	return (
		<mesh>
			<sphereGeometry args={[1, 64, 64]} />
			<shaderMaterial
				ref={materialRef}
				vertexShader={earthVertexShader}
				fragmentShader={earthFragmentShader}
				uniforms={uniforms}
			/>
		</mesh>
	);
}

function EarthFallback() {
	return (
		<mesh>
			<sphereGeometry args={[1, 64, 64]} />
			<meshStandardMaterial
				color="#0a1628"
				emissive="#040810"
				emissiveIntensity={0.5}
				roughness={0.9}
				metalness={0.1}
			/>
		</mesh>
	);
}

export function Earth() {
	const [textureLoaded, setTextureLoaded] = useState(true);

	const atmosphereMaterial = useMemo(() => {
		return new THREE.ShaderMaterial({
			vertexShader: atmosphereVertexShader,
			fragmentShader: atmosphereFragmentShader,
			transparent: true,
			side: THREE.BackSide,
			depthWrite: false,
			blending: THREE.AdditiveBlending,
		});
	}, []);

	return (
		<group>
			{textureLoaded ? (
				<ErrorBoundaryFallback onError={() => setTextureLoaded(false)}>
					<EarthWithTexture />
				</ErrorBoundaryFallback>
			) : (
				<EarthFallback />
			)}

			<GridLines />

			{/* Atmosphere glow — outside the rotating group so it doesn't rotate */}
			<mesh material={atmosphereMaterial}>
				<sphereGeometry args={[1.04, 64, 64]} />
			</mesh>
		</group>
	);
}

function GridLines() {
	const geometry = useMemo(() => {
		const geo = new THREE.BufferGeometry();
		const positions: number[] = [];
		const radius = 1.002;

		for (let lat = -60; lat <= 60; lat += 30) {
			const phi = (90 - lat) * (Math.PI / 180);
			for (let lng = 0; lng < 360; lng += 2) {
				const theta1 = lng * (Math.PI / 180);
				const theta2 = (lng + 2) * (Math.PI / 180);
				positions.push(
					radius * Math.sin(phi) * Math.cos(theta1),
					radius * Math.cos(phi),
					radius * Math.sin(phi) * Math.sin(theta1),
					radius * Math.sin(phi) * Math.cos(theta2),
					radius * Math.cos(phi),
					radius * Math.sin(phi) * Math.sin(theta2),
				);
			}
		}

		for (let lng = 0; lng < 360; lng += 30) {
			const theta = lng * (Math.PI / 180);
			for (let lat = -90; lat < 90; lat += 2) {
				const phi1 = (90 - lat) * (Math.PI / 180);
				const phi2 = (90 - (lat + 2)) * (Math.PI / 180);
				positions.push(
					radius * Math.sin(phi1) * Math.cos(theta),
					radius * Math.cos(phi1),
					radius * Math.sin(phi1) * Math.sin(theta),
					radius * Math.sin(phi2) * Math.cos(theta),
					radius * Math.cos(phi2),
					radius * Math.sin(phi2) * Math.sin(theta),
				);
			}
		}

		geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
		return geo;
	}, []);

	return (
		<lineSegments geometry={geometry}>
			<lineBasicMaterial color="#22aaaa" transparent opacity={0.08} />
		</lineSegments>
	);
}

class ErrorBoundaryFallback extends Component<
	{ children: ReactNode; onError: () => void },
	{ hasError: boolean }
> {
	state = { hasError: false };

	static getDerivedStateFromError() {
		return { hasError: true };
	}

	componentDidCatch() {
		this.props.onError();
	}

	render() {
		if (this.state.hasError) return null;
		return this.props.children;
	}
}
