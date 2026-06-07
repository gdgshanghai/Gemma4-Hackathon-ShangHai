import { useState } from "react";
import type {
  BranchActionType,
  BranchMatchResult,
  BranchNode,
  BranchTrackResult,
} from "../types";

// Re-use ACTION_COLORS from MainPage
const ACTION_COLORS: Record<
  BranchActionType,
  { bg: string; text: string; border: string; icon: string }
> = {
  highlight: {
    bg: "bg-yellow-100",
    text: "text-yellow-800",
    border: "border-yellow-400",
    icon: "🖍️",
  },
  circle: {
    bg: "bg-blue-100",
    text: "text-blue-800",
    border: "border-blue-400",
    icon: "⭕",
  },
  arrow: {
    bg: "bg-green-100",
    text: "text-green-800",
    border: "border-green-400",
    icon: "➡️",
  },
  transition: {
    bg: "bg-purple-100",
    text: "text-purple-800",
    border: "border-purple-400",
    icon: "📄",
  },
  none: {
    bg: "bg-gray-100",
    text: "text-gray-600",
    border: "border-gray-300",
    icon: "💬",
  },
};

interface Props {
  branches: BranchNode[];
  matchResult: BranchMatchResult | null;
  trackResult: BranchTrackResult | null;
  slideIndex: number;
  totalSlides: number;
}

function flattenTree(
  nodes: BranchNode[],
  depth: number = 0,
): { node: BranchNode; depth: number }[] {
  const result: { node: BranchNode; depth: number }[] = [];
  for (const n of nodes) {
    result.push({ node: n, depth });
    result.push(...flattenTree(n.next_branches, depth + 1));
  }
  return result;
}

function BranchRow({
  node,
  depth,
  isMatched,
  isCovered,
  confidence,
}: {
  node: BranchNode;
  depth: number;
  isMatched: boolean;
  isCovered: boolean;
  confidence: number | null;
}) {
  const c = ACTION_COLORS[node.action.type];
  const borderClass = isMatched
    ? "border-l-4 border-amber-400 bg-amber-50/60"
    : isCovered
      ? "border-l-4 border-emerald-400 bg-emerald-50/30"
      : "border-l-4 border-transparent";

  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 text-xs font-mono ${borderClass} transition-colors`}
      style={{ paddingLeft: `${12 + depth * 20}px` }}
    >
      {/* Tree connector */}
      {depth > 0 && (
        <span className="text-gray-300 select-none shrink-0">
          {"  ".repeat(depth - 1)}└
        </span>
      )}

      {/* Branch ID */}
      <span
        className={`shrink-0 font-bold ${isMatched ? "text-amber-700" : isCovered ? "text-emerald-700" : "text-gray-500"}`}
      >
        {node.branch_id}
      </span>

      {/* Action badge */}
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold shrink-0 ${c.text} ${c.bg} border ${c.border}`}
      >
        {c.icon} {node.action.type}
      </span>

      {/* Confidence (only if matched) */}
      {isMatched && confidence != null && (
        <span className="shrink-0 text-[10px] font-bold text-amber-600 bg-amber-100 rounded px-1.5 py-0.5">
          {Math.round(confidence * 100)}%
        </span>
      )}

      {/* Predicted text (truncated) */}
      <span
        className="truncate text-gray-600 min-w-0"
        title={node.predicted_text}
      >
        {node.predicted_text}
      </span>

      {/* Covered check */}
      {isCovered && !isMatched && (
        <span className="shrink-0 text-emerald-500 text-[10px]">✓</span>
      )}

      {/* Teleprompter hint */}
      {node.teleprompter && node.teleprompter !== node.predicted_text && (
        <span
          className="shrink-0 text-[10px] text-gray-400 italic"
          title={node.teleprompter}
        >
          📋
        </span>
      )}
    </div>
  );
}

export function BranchTreeDebug({
  branches,
  matchResult,
  trackResult,
  slideIndex,
  totalSlides,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const flat = flattenTree(branches);
  const coveredIds = trackResult?.all_covered_ids ?? [];
  const matchedId = matchResult?.branch_id ?? null;
  const matchedConf = matchResult?.confidence ?? null;

  // Summary stats
  const totalNodes = flat.length;
  const coveredCount = flat.filter(({ node }) =>
    coveredIds.includes(node.branch_id),
  ).length;
  const transitionNodes = flat.filter(
    ({ node }) => node.action.type === "transition",
  );

  return (
    <div className="mt-4 rounded-2xl border border-border bg-secondary overflow-hidden">
      {/* Header (clickable to toggle) */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-card transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-foreground">
            🔍 Branch Debug
          </span>
          <span className="text-[11px] text-muted-foreground">
            Slide {slideIndex + 1}/{totalSlides}
          </span>
          <span className="text-[11px] text-muted-foreground">
            {totalNodes} nodes
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          <span>
            Matched:{" "}
            <span className="font-bold text-amber-600">{matchedId ?? "—"}</span>
            {matchedConf != null && ` (${Math.round(matchedConf * 100)}%)`}
          </span>
          <span>
            Covered:{" "}
            <span className="font-bold text-emerald-600">
              {coveredCount}/{totalNodes}
            </span>
          </span>
          <span className="text-gray-400 text-sm">{expanded ? "▼" : "▶"}</span>
        </div>
      </button>

      {/* Body */}
      {expanded && (
        <div className="border-t border-border">
          {/* Legend bar */}
          <div className="flex items-center gap-4 px-4 py-2 bg-card border-b border-border text-[10px]">
            <span className="flex items-center gap-1 text-gray-500">
              <span className="w-3 h-3 rounded-sm bg-amber-50/60 border-l-4 border-amber-400" />{" "}
              Matched
            </span>
            <span className="flex items-center gap-1 text-gray-500">
              <span className="w-3 h-3 rounded-sm bg-emerald-50/30 border-l-4 border-emerald-400" />{" "}
              Covered
            </span>
            <span className="flex items-center gap-1 text-gray-500">
              <span className="w-3 h-3 rounded-sm border-l-4 border-transparent" />{" "}
              Pending
            </span>
            {transitionNodes.length > 0 && (
              <span className="flex items-center gap-1 text-purple-500 ml-auto">
                📄 {transitionNodes.length} transition
                {transitionNodes.length > 1 ? "s" : ""}:{" "}
                {transitionNodes.map((t) => t.node.branch_id).join(", ")}
              </span>
            )}
          </div>

          {/* Branch tree */}
          <div className="max-h-[360px] overflow-y-auto">
            {flat.length === 0 ? (
              <div className="px-4 py-8 text-center text-xs text-gray-400">
                No branch data for this slide yet.
              </div>
            ) : (
              flat.map(({ node, depth }) => (
                <BranchRow
                  key={node.branch_id}
                  node={node}
                  depth={depth}
                  isMatched={node.branch_id === matchedId}
                  isCovered={coveredIds.includes(node.branch_id)}
                  confidence={node.branch_id === matchedId ? matchedConf : null}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
