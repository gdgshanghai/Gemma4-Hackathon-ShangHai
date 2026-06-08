import { useEffect, useRef, useState } from "react";
import type { ActionToast } from "../stores/simulationStore";
import { useSimulationStore } from "../stores/simulationStore";

const TYPE_COLORS: Record<string, string> = {
  military:    "#ff4466",
  diplomatic:  "#4488ff",
  economic:    "#ffaa22",
  intelligence:"#aa44ff",
  propaganda:  "#22ddaa",
};

const TYPE_ICONS: Record<string, string> = {
  military:    "⚔",
  diplomatic:  "🤝",
  economic:    "💰",
  intelligence:"👁",
  propaganda:  "📡",
};

function Toast({ toast }: { toast: ActionToast }) {
  const dismissToast = useSimulationStore((s) => s.dismissToast);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Animate in
    const showTimer = requestAnimationFrame(() => setVisible(true));
    // Animate out after 5s
    const hideTimer = setTimeout(() => {
      setVisible(false);
      setTimeout(() => dismissToast(toast.id), 400);
    }, 5000);
    return () => {
      cancelAnimationFrame(showTimer);
      clearTimeout(hideTimer);
    };
  }, [toast.id, dismissToast]);

  const typeColor = TYPE_COLORS[toast.action.type] || "#888";
  const typeIcon = TYPE_ICONS[toast.action.type] || "•";
  const intensityPct = Math.round(toast.action.intensity * 100);

  return (
    <div
      style={{
        transform: visible ? "translateX(0)" : "translateX(120%)",
        opacity: visible ? 1 : 0,
        transition: "transform 0.35s cubic-bezier(0.22,1,0.36,1), opacity 0.35s ease",
        background: "rgba(10,12,20,0.92)",
        border: `1px solid ${toast.agentColor}44`,
        borderLeft: `3px solid ${toast.agentColor}`,
        borderRadius: 3,
        padding: "8px 10px",
        width: 260,
        backdropFilter: "blur(8px)",
        boxShadow: `0 4px 24px rgba(0,0,0,0.5), 0 0 0 1px ${toast.agentColor}11`,
        pointerEvents: "none",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: toast.agentColor, flexShrink: 0 }} />
        <span style={{ fontSize: 10, fontWeight: 700, color: toast.agentColor, fontFamily: "var(--font-mono)", flex: 1 }}>
          {toast.agentName.toUpperCase()}
        </span>
        <span style={{
          fontSize: 8,
          padding: "1px 5px",
          background: `${typeColor}22`,
          border: `1px solid ${typeColor}55`,
          borderRadius: 2,
          color: typeColor,
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.05em",
        }}>
          {typeIcon} {toast.action.type.toUpperCase()}
        </span>
      </div>

      {/* Description */}
      <div style={{ fontSize: 10, color: "var(--color-text-secondary)", lineHeight: 1.45, marginBottom: 5 }}>
        {toast.action.description}
      </div>

      {/* Footer row */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {toast.action.target && (
          <span style={{ fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            → {toast.action.target.toUpperCase()}
          </span>
        )}
        <div style={{ flex: 1 }} />
        {/* Intensity bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <div style={{
            width: 48,
            height: 3,
            background: "rgba(255,255,255,0.08)",
            borderRadius: 2,
            overflow: "hidden",
          }}>
            <div style={{
              width: `${intensityPct}%`,
              height: "100%",
              background: typeColor,
              borderRadius: 2,
            }} />
          </div>
          <span style={{ fontSize: 8, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)" }}>
            {intensityPct}%
          </span>
        </div>
      </div>
    </div>
  );
}

export function ActionToastOverlay() {
  const toasts = useSimulationStore((s) => s.actionToasts);
  const prevCountRef = useRef(0);

  // Auto-scroll awareness: stagger entrance so rapid toasts don't pile instantly
  useEffect(() => {
    prevCountRef.current = toasts.length;
  }, [toasts.length]);

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 48,
        right: 12,
        display: "flex",
        flexDirection: "column",
        gap: 6,
        zIndex: 100,
        maxHeight: "70vh",
        overflowY: "hidden",
        alignItems: "flex-end",
      }}
    >
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
