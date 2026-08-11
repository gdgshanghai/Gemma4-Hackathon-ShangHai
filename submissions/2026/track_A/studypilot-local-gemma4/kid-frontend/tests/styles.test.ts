import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const styles = readFileSync("src/styles.css", "utf8");

describe("auditorium-sized desktop UI", () => {
  it("uses the V3 desktop scale without changing mobile defaults", () => {
    const desktopStart = styles.indexOf("@media (min-width: 1100px)");

    expect(desktopStart).toBeGreaterThanOrEqual(0);
    const mobileAndTablet = styles.slice(0, desktopStart);
    const desktop = styles.slice(desktopStart);
    expect(desktop).toContain("--font-body: 19px");
    expect(desktop).toContain("--font-control: 18px");
    expect(desktop).toContain("--font-secondary: 16px");
    expect(desktop).toContain("--font-h1: 36px");
    expect(desktop).toContain("--font-h2: 26px");
    expect(desktop).toContain("--content-width: 1400px");
    expect(desktop).toContain("--header-width: 1440px");
    expect(desktop).toContain("--control-height: 54px");
    expect(desktop).toContain("min-height: 92px");
    expect(desktop).toContain("width: 50px");
    expect(desktop).toContain("font-size: 58px");

    expect(mobileAndTablet).toContain("--font-body: 18px");
    expect(mobileAndTablet).toContain("--font-control: 17px");
    expect(mobileAndTablet).toContain("--content-width: 1320px");
  });
});
