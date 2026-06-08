const CLOB_BASE = "/api/clob";

// "Iran x Israel/US conflict ends by December 31?" — YES token
const WAR_ENDS_2026_TOKEN =
	"30474492153316523915604855839063847245493287455989692695957038531302522868025";

export async function getWarEndsProbability(): Promise<number> {
	const url = `${CLOB_BASE}/midpoint?token_id=${WAR_ENDS_2026_TOKEN}`;
	const res = await fetch(url);
	if (!res.ok) throw new Error(`Midpoint fetch failed: ${res.status}`);
	const data = await res.json();
	return Number.parseFloat(data.mid);
}
