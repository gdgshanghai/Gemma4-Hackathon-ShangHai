import * as THREE from "three";

/**
 * Compute the sun's direction vector in world space based on current UTC time.
 * Uses a simplified solar position model (accurate to ~1°).
 */
export function getSunDirection(date: Date = new Date()): THREE.Vector3 {
	const dayOfYear = getDayOfYear(date);
	const utcHours =
		date.getUTCHours() +
		date.getUTCMinutes() / 60 +
		date.getUTCSeconds() / 3600;

	// Solar declination (angle of sun above/below equator)
	// Approximation using sinusoidal model
	const declination =
		-23.44 * Math.cos(((360 / 365) * (dayOfYear + 10) * Math.PI) / 180);
	const decRad = (declination * Math.PI) / 180;

	// Hour angle: sun is at longitude 0 at 12:00 UTC
	// Each hour = 15° of longitude
	const solarLongitude = (12 - utcHours) * 15;
	const lonRad = (solarLongitude * Math.PI) / 180;

	// Convert solar lat/lng to 3D direction
	// Using the same coordinate system as the globe
	const x = Math.cos(decRad) * Math.cos(lonRad);
	const y = Math.sin(decRad);
	const z = -Math.cos(decRad) * Math.sin(lonRad);

	return new THREE.Vector3(x, y, z).normalize();
}

function getDayOfYear(date: Date): number {
	const start = new Date(date.getUTCFullYear(), 0, 0);
	const diff = date.getTime() - start.getTime();
	return Math.floor(diff / (1000 * 60 * 60 * 24));
}
