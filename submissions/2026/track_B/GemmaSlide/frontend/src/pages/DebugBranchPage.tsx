import { type FormEvent, useState } from "react";

import { generateBranches, parsePptxOnly } from "../api";
import { AppTopBar } from "../components/AppTopBar";
import { DebugToolTabs } from "../components/DebugToolTabs";
import type {
  BranchActionType,
  BranchNode,
  BranchTreeResponse,
  ParsePptxResponse,
} from "../types";

// ── Color helpers for action types ──

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

// ── Branch Node Component ──

function BranchNodeCard({
  node,
  depth,
  selectedBranchId,
  onSelect,
}: {
  node: BranchNode;
  depth: number;
  selectedBranchId: string | null;
  onSelect: (id: string) => void;
}) {
  const colors = ACTION_COLORS[node.action.type] ?? ACTION_COLORS.none;
  const hasChildren = node.next_branches.length > 0;
  const indent = depth * 24;
  const isSelected = selectedBranchId === node.branch_id;
  const hasBbox =
    node.action.type !== "none" &&
    node.action.type !== "transition" &&
    node.action.bbox_1000.length === 4;

  return (
    <div style={{ marginLeft: `${indent}px` }}>
      {/* Node card */}
      <button
        onClick={() => onSelect(node.branch_id)}
        className={`w-full text-left rounded-xl border ${colors.border} ${colors.bg} p-3 mb-2 transition-all cursor-pointer hover:shadow-md ${
          isSelected ? "ring-2 ring-offset-1 ring-primary" : ""
        } ${hasBbox ? "hover:border-2" : ""}`}
      >
        {/* Header row: branch_id + action badge */}
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-xs font-mono font-semibold text-gray-500">
            {node.branch_id}
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${colors.text} ${colors.bg}`}
          >
            {colors.icon} {node.action.type}
            {node.action.type !== "none" &&
              node.action.type !== "transition" && (
                <span className="font-mono opacity-70">
                  [{node.action.bbox_1000.join(",")}]
                </span>
              )}
            {node.action.duration_ms > 0 &&
              node.action.type !== "none" &&
              node.action.type !== "transition" && (
                <span className="opacity-70">{node.action.duration_ms}ms</span>
              )}
          </span>
        </div>

        {/* Predicted text */}
        <p className="text-sm font-medium text-gray-800 mb-1">
          {node.predicted_text}
        </p>

        {/* Teleprompter */}
        {node.teleprompter !== node.predicted_text && (
          <p className="text-xs text-gray-500 italic">📋 {node.teleprompter}</p>
        )}

        {/* Child count badge */}
        {hasChildren && (
          <div className="mt-2 text-xs text-gray-400">
            ↓ {node.next_branches.length} child branch
            {node.next_branches.length !== 1 ? "es" : ""}
          </div>
        )}
      </button>

      {/* Connector line (visual tree) */}
      {hasChildren && (
        <div className="ml-2 border-l-2 border-gray-200 pl-3">
          {node.next_branches.map((child) => (
            <BranchNodeCard
              key={child.branch_id}
              node={child}
              depth={0}
              selectedBranchId={selectedBranchId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Slide Preview with BBox Overlay ──

/** Flatten all branches into a flat list of {branch_id, bbox_1000, action_type} */
function flattenBboxes(
  branches: BranchNode[],
): { branch_id: string; bbox_1000: number[]; action_type: BranchActionType }[] {
  const result: {
    branch_id: string;
    bbox_1000: number[];
    action_type: BranchActionType;
  }[] = [];
  const walk = (nodes: BranchNode[]) => {
    for (const n of nodes) {
      if (
        n.action.type !== "none" &&
        n.action.type !== "transition" &&
        n.action.bbox_1000.length === 4
      ) {
        result.push({
          branch_id: n.branch_id,
          bbox_1000: n.action.bbox_1000,
          action_type: n.action.type,
        });
      }
      walk(n.next_branches);
    }
  };
  walk(branches);
  return result;
}

const OVERLAY_COLORS: Record<BranchActionType, string> = {
  highlight: "rgba(234,179,8,0.35)",
  circle: "rgba(59,130,246,0.35)",
  arrow: "rgba(34,197,94,0.35)",
  transition: "transparent",
  none: "transparent",
};

const OVERLAY_BORDER: Record<BranchActionType, string> = {
  highlight: "#ca8a04",
  circle: "#2563eb",
  arrow: "#16a34a",
  transition: "transparent",
  none: "transparent",
};

function SlidePreviewOverlay({
  imageBase64,
  widthPx,
  heightPx,
  bboxes,
  selectedBranchId,
  onSelectBranch,
}: {
  imageBase64: string;
  widthPx: number;
  heightPx: number;
  bboxes: {
    branch_id: string;
    bbox_1000: number[];
    action_type: BranchActionType;
  }[];
  selectedBranchId: string | null;
  onSelectBranch: (id: string) => void;
}) {
  const maxWidth = 700;

  return (
    <div
      className="relative mx-auto border border-gray-200 rounded-lg overflow-hidden bg-white shadow-sm"
      style={{
        maxWidth: `${maxWidth}px`,
        aspectRatio: `${widthPx}/${heightPx}`,
      }}
    >
      <img
        src={imageBase64}
        alt="Slide preview"
        className="w-full h-full object-contain"
      />

      {/* BBox overlays */}
      {bboxes.map((bb) => {
        const [ymin, xmin, ymax, xmax] = bb.bbox_1000;
        const top = (ymin / 1000) * 100;
        const left = (xmin / 1000) * 100;
        const height = ((ymax - ymin) / 1000) * 100;
        const width = ((xmax - xmin) / 1000) * 100;
        const isSelected = selectedBranchId === bb.branch_id;
        const bg = OVERLAY_COLORS[bb.action_type] ?? "transparent";
        const border = OVERLAY_BORDER[bb.action_type] ?? "#999";

        return (
          <button
            key={bb.branch_id}
            onClick={(e) => {
              e.stopPropagation();
              onSelectBranch(bb.branch_id);
            }}
            className={`absolute transition-all cursor-pointer ${
              isSelected
                ? "ring-2 ring-offset-[-2px] ring-primary z-10"
                : "hover:ring-1 hover:ring-gray-400 z-0"
            }`}
            style={{
              top: `${top}%`,
              left: `${left}%`,
              height: `${height}%`,
              width: `${width}%`,
              backgroundColor: isSelected ? bg : bg.replace("0.35", "0.15"),
              border: `2px ${isSelected ? "solid" : "dashed"} ${border}`,
            }}
            title={`${bb.branch_id} — ${bb.action_type}`}
          >
            <span
              className="absolute -top-4 left-0 text-[10px] font-mono font-semibold px-1 rounded"
              style={{ backgroundColor: border, color: "#fff" }}
            >
              {bb.branch_id}
            </span>
          </button>
        );
      })}

      {/* Empty state */}
      {bboxes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
          No bbox actions in current branch tree
        </div>
      )}
    </div>
  );
}

// ── Stats bar ──

function BranchStats({ tree }: { tree: BranchTreeResponse }) {
  const countNodes = (branches: BranchNode[]): number => {
    let count = branches.length;
    for (const b of branches) {
      count += countNodes(b.next_branches);
    }
    return count;
  };

  const countByAction = (branches: BranchNode[]): Record<string, number> => {
    const counts: Record<string, number> = {};
    const walk = (nodes: BranchNode[]) => {
      for (const n of nodes) {
        counts[n.action.type] = (counts[n.action.type] ?? 0) + 1;
        walk(n.next_branches);
      }
    };
    walk(branches);
    return counts;
  };

  const total = countNodes(tree.branches);
  const actionCounts = countByAction(tree.branches);

  return (
    <div className="flex flex-wrap gap-3 text-xs text-gray-500">
      <span className="font-semibold">
        {tree.branches.length} top-level · {total} total nodes
      </span>
      {Object.entries(actionCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([type, count]) => (
          <span
            key={type}
            className={`rounded-full px-2 py-0.5 font-medium ${ACTION_COLORS[type as BranchActionType]?.text ?? "text-gray-500"}`}
          >
            {ACTION_COLORS[type as BranchActionType]?.icon} {type}: {count}
          </span>
        ))}
      <span className="ml-auto">⏱ {tree.generation_time_ms.toFixed(0)}ms</span>
    </div>
  );
}

// ── Main Page ──

export function DebugBranchPage() {
  const [file, setFile] = useState<File | null>(null);
  const [parseId, setParseId] = useState("");
  const [parseResult, setParseResult] = useState<ParsePptxResponse | null>(
    null,
  );
  const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);
  const [maxDepth, setMaxDepth] = useState(3);

  const [tree, setTree] = useState<BranchTreeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);

  const slides = parseResult?.slides ?? [];
  const currentSlide = slides[selectedSlideIndex];
  const slideImageB64 = currentSlide?.image?.image_base64 ?? null;
  const slideW = currentSlide?.image?.width_px ?? 960;
  const slideH = currentSlide?.image?.height_px ?? 540;

  // Collect all bboxes from the current branch tree for overlay
  const allBboxes = tree ? flattenBboxes(tree.branches) : [];

  // ── Upload PPTX to get parse_id ──
  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setError(null);
    setTree(null);
    try {
      const result = await parsePptxOnly(file, {
        includeImagesBase64: true,
        flattenGroups: true,
        elementTypes: [],
      });
      setParseResult(result);
      setParseId(result.parse_id);
      setSelectedSlideIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  // ── Generate branches ──
  const handleGenerate = async () => {
    if (!parseId) return;

    setLoading(true);
    setError(null);
    setTree(null);
    setSelectedBranchId(null);
    try {
      const result = await generateBranches({
        parse_id: parseId,
        slide_index: selectedSlideIndex,
        max_depth: maxDepth,
      });
      setTree(result);
      if (result.error) {
        setError(result.error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8 md:py-10">
        <AppTopBar
          title="GemmaSlide"
          subtitle="Branch Tree Debug"
          actionLabel="Back To Main UI"
          actionTo="/"
        />

        <DebugToolTabs />

        <header
          className={`rounded-xl bg-secondary mb-5 overflow-hidden p-6 md:p-8`}
        >
          <div className="relative">
            <p className="text-xs uppercase tracking-[0.24em] text-primary">
              Phase 3 — Branch Prediction
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.02em] text-foreground md:text-[2.3rem]">
              Branch Tree Generator
            </h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
              Upload a PPTX, select a slide, and generate a 3-level branch
              prediction tree. Each branch shows predicted text and the visual
              action (highlight/circle/arrow/transition) that would execute.
            </p>
          </div>
        </header>

        {/* ── Controls ── */}
        <div className={`rounded-xl border bg-card mb-5 p-5`}>
          {/* Upload section */}
          <form
            onSubmit={handleUpload}
            className="flex flex-wrap items-end gap-3 mb-4"
          >
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                PPTX File
              </label>
              <input
                type="file"
                accept=".pptx"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>
            <button
              type="submit"
              disabled={!file || uploading}
              className="rounded-full bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-40 transition"
            >
              {uploading ? "Uploading…" : "Upload & Parse"}
            </button>
          </form>

          {/* Manual parse_id + slide selector + depth */}
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[180px]">
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Parse ID
              </label>
              <input
                type="text"
                value={parseId}
                onChange={(e) => setParseId(e.target.value)}
                placeholder="Or paste parse_id..."
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            <div className="min-w-[80px]">
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Slide #
              </label>
              <input
                type="number"
                min={0}
                max={slides.length - 1}
                value={selectedSlideIndex}
                onChange={(e) => setSelectedSlideIndex(Number(e.target.value))}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            <div className="min-w-[80px]">
              <label className="block text-xs font-semibold text-muted-foreground mb-1">
                Depth
              </label>
              <select
                value={maxDepth}
                onChange={(e) => setMaxDepth(Number(e.target.value))}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              >
                <option value={1}>1 (top only)</option>
                <option value={2}>2 (+ children)</option>
                <option value={3}>3 (full tree)</option>
              </select>
            </div>

            <button
              onClick={handleGenerate}
              disabled={!parseId || loading}
              className="rounded-full bg-accent px-5 py-3 text-sm font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-40 transition"
            >
              {loading ? "Generating…" : "Generate Branches"}
            </button>
          </div>

          {/* Slide info */}
          {slides.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {slides.map((_slide, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setSelectedSlideIndex(idx);
                    setSelectedBranchId(null);
                  }}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    idx === selectedSlideIndex
                      ? "!bg-primary !text-primary-foreground"
                      : ""
                  }`}
                >
                  Slide {idx + 1}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* ── Slide Preview ── */}
        {slideImageB64 && (
          <div className={`rounded-xl border bg-card mb-5 p-5`}>
            <h2 className="text-lg font-semibold mb-3">
              Slide {selectedSlideIndex + 1} Preview
              {tree && (
                <span className="ml-2 text-sm font-normal text-gray-400">
                  — click a bbox or branch card to highlight
                </span>
              )}
            </h2>
            <SlidePreviewOverlay
              imageBase64={slideImageB64}
              widthPx={slideW}
              heightPx={slideH}
              bboxes={allBboxes}
              selectedBranchId={selectedBranchId}
              onSelectBranch={setSelectedBranchId}
            />
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div className="mb-5 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-700">
            ⚠️ {error}
          </div>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div className={`rounded-xl border bg-card mb-5 p-8 text-center`}>
            <div className="animate-pulse text-lg text-muted-foreground">
              🧠 LLM is generating branch tree…
            </div>
            <p className="mt-2 text-sm text-gray-400">
              This typically takes 3-8 seconds
            </p>
          </div>
        )}

        {/* ── Branch Tree ── */}
        {tree && !loading && (
          <div className={`rounded-xl border bg-card mb-5 p-5`}>
            <h2 className="text-lg font-semibold mb-3">
              Slide {tree.slide_index + 1} Branch Tree
            </h2>
            <BranchStats tree={tree} />

            <div className="mt-4 space-y-1">
              {tree.branches.length === 0 && !tree.error && (
                <p className="text-gray-400 text-sm italic">
                  No branches generated. The LLM may have returned an empty
                  response.
                </p>
              )}
              {tree.branches.map((branch) => (
                <BranchNodeCard
                  key={branch.branch_id}
                  node={branch}
                  depth={0}
                  selectedBranchId={selectedBranchId}
                  onSelect={setSelectedBranchId}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Raw JSON ── */}
        {tree && !loading && (
          <details className={`rounded-xl border bg-card mb-5 p-5`}>
            <summary className="cursor-pointer text-sm font-semibold text-muted-foreground">
              Raw JSON Response
            </summary>
            <pre className="mt-3 text-xs text-gray-600 overflow-auto max-h-[600px] whitespace-pre-wrap">
              {JSON.stringify(tree, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
