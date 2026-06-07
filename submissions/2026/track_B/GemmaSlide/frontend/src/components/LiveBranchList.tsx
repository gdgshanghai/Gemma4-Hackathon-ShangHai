import type {
  BranchActionType,
  BranchMatchResult,
  BranchNode,
  BranchTrackResult,
} from "../types";

const ACTION_COLORS: Record<
  BranchActionType,
  { bg: string; text: string; border: string; icon: string }
> = {
  highlight: {
    bg: "bg-yellow-50",
    text: "text-yellow-800",
    border: "border-yellow-300",
    icon: "🖍️",
  },
  circle: {
    bg: "bg-blue-50",
    text: "text-blue-800",
    border: "border-blue-300",
    icon: "⭕",
  },
  arrow: {
    bg: "bg-green-50",
    text: "text-green-800",
    border: "border-green-300",
    icon: "➡️",
  },
  transition: {
    bg: "bg-purple-50",
    text: "text-purple-800",
    border: "border-purple-300",
    icon: "📄",
  },
  none: {
    bg: "bg-gray-50",
    text: "text-gray-600",
    border: "border-gray-200",
    icon: "💬",
  },
};

const OVERLAY_BORDER: Record<BranchActionType, string> = {
  highlight: "#ca8a04",
  circle: "#2563eb",
  arrow: "#16a34a",
  transition: "transparent",
  none: "transparent",
};

function flattenBranches(branches: BranchNode[]): BranchNode[] {
  const result: BranchNode[] = [];
  const walk = (nodes: BranchNode[]) => {
    for (const n of nodes) {
      result.push(n);
      walk(n.next_branches);
    }
  };
  walk(branches);
  return result;
}

function findNextUncovered(
  branches: BranchNode[],
  coveredIds: string[],
  currentBranchId: string | null,
): BranchNode | null {
  const flat = flattenBranches(branches);
  // Skip past current match + all covered, find the first one after
  let foundCurrent = !currentBranchId;
  for (const n of flat) {
    if (
      foundCurrent &&
      !coveredIds.includes(n.branch_id) &&
      n.branch_id !== currentBranchId
    ) {
      return n;
    }
    if (n.branch_id === currentBranchId) {
      foundCurrent = true;
    }
  }
  return null;
}

interface Props {
  branches: BranchNode[];
  matchResult: BranchMatchResult | null;
  trackResult: BranchTrackResult | null;
  status: string;
}

export function LiveBranchList({
  branches,
  matchResult,
  trackResult,
  status,
}: Props) {
  const coveredIds = trackResult?.all_covered_ids ?? [];
  const flatCount = flattenBranches(branches).length;
  const m = matchResult;

  // ── Empty / idle ──
  if (flatCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-secondary p-8">
        <p className="text-sm text-muted-foreground">
          {status === "recording"
            ? "🎙️ Listening... speak to match a cue"
            : "Press Start Mic to begin"}
        </p>
      </div>
    );
  }

  const nextBranch = findNextUncovered(
    branches,
    coveredIds,
    m?.branch_id ?? null,
  );
  const c = ACTION_COLORS[m?.action.type ?? "none"];

  // ── Two cards: Now + Up Next, positions NEVER swap ──
  return (
    <div className="flex flex-col gap-4">
      {/* ── Now card ── */}
      <div
        className="rounded-2xl border-2 p-5 shadow-sm transition-all duration-300"
        style={{
          borderColor: m ? OVERLAY_BORDER[m.action.type] : "hsl(var(--border))",
          background: m ? "#fff" : "hsl(var(--background))",
        }}
      >
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">
            Now
          </span>
          {m?.is_covered && (
            <span className="text-[10px] font-bold text-green-600 bg-green-100 px-2 py-0.5 rounded-full">
              COVERED
            </span>
          )}
        </div>
        {m ? (
          <>
            <div className="flex items-center gap-2.5 mb-3">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${c.text} ${c.bg}`}
              >
                {c.icon} {m.action.type}
              </span>
              <span className="text-xs text-gray-400">
                {(m.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-lg font-semibold text-gray-900 leading-relaxed transition-all duration-300">
              {m.predicted_text}
            </p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            {status === "recording"
              ? "🎙️ Listening..."
              : "Press Start to begin"}
          </p>
        )}
      </div>

      {/* ── Up Next card ── */}
      <div className="rounded-2xl border border-border bg-background p-5 transition-all duration-300">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">
            Up Next
          </span>
          <span className="text-[10px] text-gray-400 ml-auto">
            {coveredIds.length}/{flatCount} done
          </span>
        </div>
        {nextBranch ? (
          <>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${ACTION_COLORS[nextBranch.action.type].text} ${ACTION_COLORS[nextBranch.action.type].bg}`}
            >
              {ACTION_COLORS[nextBranch.action.type].icon}{" "}
              {nextBranch.action.type}
            </span>
            <p className="mt-2 text-sm font-medium text-gray-600 leading-relaxed transition-all duration-300">
              {nextBranch.predicted_text}
            </p>
            {nextBranch.teleprompter &&
              nextBranch.teleprompter !== nextBranch.predicted_text && (
                <p className="mt-1.5 text-xs text-gray-400 italic">
                  📋 {nextBranch.teleprompter}
                </p>
              )}
          </>
        ) : (
          <p className="text-sm text-gray-400">All cues covered ✓</p>
        )}
      </div>
    </div>
  );
}
