import * as THREE from "three";

/**
 * Convert latitude/longitude to a THREE.Vector3 on a sphere of given radius.
 */
export function latLngToVec3(lat: number, lng: number, radius: number): THREE.Vector3 {
	const phi = (90 - lat) * (Math.PI / 180);
	const theta = (lng + 180) * (Math.PI / 180);

	return new THREE.Vector3(
		-radius * Math.sin(phi) * Math.cos(theta),
		radius * Math.cos(phi),
		radius * Math.sin(phi) * Math.sin(theta),
	);
}
