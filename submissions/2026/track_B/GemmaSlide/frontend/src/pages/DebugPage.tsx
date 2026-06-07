import { type CSSProperties, type FormEvent, useMemo, useState } from "react";

import { parsePptx } from "../api";
import { AppTopBar } from "../components/AppTopBar";
import { DebugToolTabs } from "../components/DebugToolTabs";
import {
  colorFromType,
  computeCanvasSize,
  EMPTY_SLIDES,
  formatBBox,
} from "../lib/pptx-utils";
import type { ParsePptxResponse } from "../types";

export function DebugParserPage() {
  const [file, setFile] = useState<File | null>(null);
  const [includeImagesBase64, setIncludeImagesBase64] = useState(true);
  const [flattenGroups, setFlattenGroups] = useState(true);
  const [requestedElementTypes, setRequestedElementTypes] = useState("");

  const [response, setResponse] = useState<ParsePptxResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedSlideIndex, setSelectedSlideIndex] = useState(0);
  const [selectedElementId, setSelectedElementId] = useState<string | null>(
    null,
  );
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState<Record<string, boolean>>({});
  const [showLabels, setShowLabels] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [coordinateMode, setCoordinateMode] = useState<"px" | "norm" | "emu">(
    "px",
  );

  const slides = response?.slides ?? EMPTY_SLIDES;
  const currentSlide = slides[selectedSlideIndex] ?? null;

  const allTypesInDeck = useMemo(() => {
    const bucket = new Set<string>();
    for (const slide of slides) {
      for (const element of slide.elements) {
        bucket.add(element.shape_type_name);
      }
    }
    return [...bucket].sort((a, b) => a.localeCompare(b));
  }, [slides]);

  const visibleElements = useMemo(() => {
    if (!currentSlide) {
      return [];
    }

    const normalizedQuery = searchTerm.trim().toLowerCase();

    return currentSlide.elements.filter((element) => {
      const typeAllowed =
        Object.keys(typeFilter).length === 0 ||
        Boolean(typeFilter[element.shape_type_name]);
      const queryAllowed =
        normalizedQuery.length === 0 ||
        element.name.toLowerCase().includes(normalizedQuery) ||
        element.shape_type_name.toLowerCase().includes(normalizedQuery) ||
        (element.text ?? "").toLowerCase().includes(normalizedQuery);

      return typeAllowed && queryAllowed;
    });
  }, [currentSlide, searchTerm, typeFilter]);

  const selectedElement = useMemo(() => {
    if (!currentSlide || !selectedElementId) {
      return null;
    }
    return (
      currentSlide.elements.find(
        (element) => element.element_id === selectedElementId,
      ) ?? null
    );
  }, [currentSlide, selectedElementId]);

  const canvasSize = useMemo(() => {
    if (!currentSlide) {
      return { width: 960, height: 540 };
    }
    return computeCanvasSize(currentSlide, zoom);
  }, [currentSlide, zoom]);

  function initializeSlideAndFilters(apiResponse: ParsePptxResponse): void {
    setSelectedSlideIndex(0);
    setSelectedElementId(
      apiResponse.slides[0]?.elements[0]?.element_id ?? null,
    );

    const nextFilter: Record<string, boolean> = {};
    for (const slide of apiResponse.slides) {
      for (const element of slide.elements) {
        nextFilter[element.shape_type_name] = true;
      }
    }
    setTypeFilter(nextFilter);
  }

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();

    if (!file) {
      setError("Please choose a .pptx file before uploading.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const parsedElementTypes = requestedElementTypes
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter(Boolean);

      const apiResponse = await parsePptx(file, {
        includeImagesBase64,
        flattenGroups,
        elementTypes: parsedElementTypes,
      });

      setResponse(apiResponse);
      initializeSlideAndFilters(apiResponse);
      setCoordinateMode(includeImagesBase64 ? "px" : "norm");
    } catch (submissionError) {
      setResponse(null);
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Failed to parse file.",
      );
    } finally {
      setLoading(false);
    }
  }

  function toggleType(typeName: string): void {
    setTypeFilter((current) => ({
      ...current,
      [typeName]: !current[typeName],
    }));
  }

  function selectAllTypes(nextValue: boolean): void {
    const nextFilter: Record<string, boolean> = {};
    for (const typeName of allTypesInDeck) {
      nextFilter[typeName] = nextValue;
    }
    setTypeFilter(nextFilter);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-[1600px] px-4 py-6 md:px-8 md:py-10">
        <AppTopBar
          title="GemmaSlide"
          subtitle="Debug Inspector"
          actionLabel="Back To Main UI"
          actionTo="/"
        />

        <DebugToolTabs />

        <header
          className={`rounded-xl bg-secondary mb-5 overflow-hidden p-6 md:p-8`}
        >
          <div className="absolute inset-x-0 top-0 h-24 bg-[linear-gradient(90deg,hsl(var(--primary)/0.2),transparent_65%)] opacity-90" />
          <div className="relative">
            <p className="text-xs uppercase tracking-[0.24em] text-primary">
              GemmaSlide Visual Inspector
            </p>
            <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className="text-3xl font-semibold tracking-[-0.02em] text-foreground md:text-[2.75rem]">
                  PPTX Render Verification Workbench
                </h1>
                <p className="mt-3 max-w-4xl text-sm leading-6 text-muted-foreground md:text-base">
                  Upload a presentation, inspect each rendered slide, and
                  compare parser coordinates to image output. Select an element
                  from the panel or click a bounding box to validate placement.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm md:min-w-[360px]">
                <div className="rounded-[24px] bg-primary/20 px-4 py-3 text-primary shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.14em] opacity-75">
                    Inspect
                  </p>
                  <p className="mt-1 font-medium">Rendered slide fidelity</p>
                </div>
                <div className="rounded-[24px] bg-secondary px-4 py-3 text-secondary-foreground shadow-sm">
                  <p className="text-[11px] uppercase tracking-[0.14em] opacity-75">
                    Compare
                  </p>
                  <p className="mt-1 font-medium">EMU, normalized, pixel</p>
                </div>
              </div>
            </div>
          </div>
        </header>

        <form
          onSubmit={handleSubmit}
          className={`rounded-xl border bg-card grid gap-4 p-5 md:grid-cols-12 md:p-6`}
        >
          <div className="md:col-span-4">
            <label className="mb-2 block text-sm font-medium text-foreground">
              PPTX file
            </label>
            <input
              type="file"
              accept=".pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-[18px] border border-border bg-accent px-4 py-3 text-sm text-foreground file:mr-3 file:rounded-full file:border-0 file:bg-secondary file:px-4 file:py-2 file:text-xs file:font-medium file:text-secondary-foreground hover:file:bg-primary/20"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              {file
                ? `Selected: ${file.name}`
                : "Choose a .pptx file to begin."}
            </p>
          </div>

          <div className="md:col-span-5">
            <label
              htmlFor="element-types"
              className="mb-2 block text-sm font-medium text-foreground"
            >
              Optional backend element_types (comma-separated)
            </label>
            <input
              id="element-types"
              type="text"
              value={requestedElementTypes}
              onChange={(event) => setRequestedElementTypes(event.target.value)}
              placeholder="picture, text_box, group"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              Leave empty to request all shape types from the backend.
            </p>
          </div>

          <div className="flex items-end md:col-span-3">
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-primary px-5 py-3 text-sm font-medium text-primary-foreground shadow-md transition hover:brightness-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Parsing..." : "Upload and Parse"}
            </button>
          </div>

          <label className="inline-flex items-center gap-2 text-sm text-muted-foreground md:col-span-3">
            <input
              type="checkbox"
              checked={includeImagesBase64}
              onChange={(event) => setIncludeImagesBase64(event.target.checked)}
              className="h-4 w-4 rounded border-border bg-accent accent-primary"
            />
            include_images_base64
          </label>

          <label className="inline-flex items-center gap-2 text-sm text-muted-foreground md:col-span-3">
            <input
              type="checkbox"
              checked={flattenGroups}
              onChange={(event) => setFlattenGroups(event.target.checked)}
              className="h-4 w-4 rounded border-border bg-accent accent-primary"
            />
            flatten_groups
          </label>

          <label className="inline-flex items-center gap-2 text-sm text-muted-foreground md:col-span-3">
            <input
              type="checkbox"
              checked={showLabels}
              onChange={(event) => setShowLabels(event.target.checked)}
              className="h-4 w-4 rounded border-border bg-accent accent-primary"
            />
            show overlay labels
          </label>

          <div className="md:col-span-3">
            <label
              htmlFor="zoom"
              className="mb-1 block text-xs uppercase tracking-wide text-muted-foreground"
            >
              Zoom: {(zoom * 100).toFixed(0)}%
            </label>
            <input
              id="zoom"
              type="range"
              min={0.4}
              max={2.4}
              step={0.1}
              value={zoom}
              onChange={(event) => setZoom(Number(event.target.value))}
              className="w-full"
            />
          </div>
        </form>

        {error && (
          <div className="mt-4 rounded-[20px] border border-destructive bg-destructive/10 p-4 text-sm text-destructive shadow-sm">
            {error}
          </div>
        )}

        {response && (
          <section className="mt-5 grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)_370px]">
            <aside className={`rounded-xl border bg-card p-4`}>
              <h2 className="text-lg font-semibold text-foreground">Slides</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {response.file_name}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-secondary-foreground">
                <div className="rounded-[20px] bg-secondary p-3">
                  Slides: {response.total_slides}
                </div>
                <div className="rounded-[20px] bg-accent p-3 text-accent-foreground">
                  Elements: {response.total_elements}
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {slides.map((slide, index) => (
                  <button
                    key={slide.slide_index}
                    type="button"
                    onClick={() => {
                      setSelectedSlideIndex(index);
                      setSelectedElementId(
                        slide.elements[0]?.element_id ?? null,
                      );
                    }}
                    className={`w-full rounded-[20px] border px-4 py-3 text-left text-sm transition ${
                      index === selectedSlideIndex
                        ? "border-primary bg-primary/20 text-primary shadow-sm"
                        : "border-border bg-secondary text-foreground hover:bg-card"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span>Slide {slide.slide_index}</span>
                      <span className="text-xs opacity-80">
                        {slide.elements.length}
                      </span>
                    </div>
                    {slide.warnings.length > 0 && (
                      <p className="mt-1 text-xs text-destructive">
                        {slide.warnings[0]}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            </aside>

            <main className={`rounded-xl border bg-card p-4`}>
              {!currentSlide && (
                <p className="text-sm text-muted-foreground">
                  No slides returned by backend.
                </p>
              )}

              {currentSlide && (
                <>
                  <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded-full bg-accent px-3 py-1.5 text-muted-foreground">
                      slide_id: {currentSlide.slide_id ?? "N/A"}
                    </span>
                    <span className="rounded-full bg-accent px-3 py-1.5 text-muted-foreground">
                      image:{" "}
                      {currentSlide.image
                        ? `${currentSlide.image.width_px}x${currentSlide.image.height_px}`
                        : "none"}
                    </span>
                    <label className="ml-auto inline-flex items-center gap-2 text-muted-foreground">
                      Coordinates
                      <select
                        value={coordinateMode}
                        onChange={(event) =>
                          setCoordinateMode(
                            event.target.value as "px" | "norm" | "emu",
                          )
                        }
                        className="rounded-full border border-border bg-accent px-3 py-1.5 text-xs text-foreground outline-none"
                      >
                        <option value="px">Pixel</option>
                        <option value="norm">Normalized</option>
                        <option value="emu">EMU</option>
                      </select>
                    </label>
                  </div>

                  <div className="overflow-auto rounded-[24px] border border-border bg-secondary p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.5)]">
                    <div
                      className="relative overflow-hidden rounded-[18px] bg-white"
                      style={{
                        width: canvasSize.width,
                        height: canvasSize.height,
                      }}
                    >
                      {currentSlide.image?.image_base64 ? (
                        <img
                          src={currentSlide.image.image_base64}
                          alt={`Slide ${currentSlide.slide_index}`}
                          width={canvasSize.width}
                          height={canvasSize.height}
                          className="select-none rounded-[18px]"
                        />
                      ) : (
                        <div
                          className="grid place-items-center rounded-[18px] border border-dashed border-border bg-card text-xs text-muted-foreground"
                          style={{
                            width: canvasSize.width,
                            height: canvasSize.height,
                          }}
                        >
                          No rendered image available for this slide.
                        </div>
                      )}

                      {visibleElements.map((element) => {
                        const color = colorFromType(element.shape_type_name);
                        const selected =
                          selectedElementId === element.element_id;

                        const style: CSSProperties = element.bbox_px
                          ? {
                              left: `${Math.round(element.bbox_px.x * zoom)}px`,
                              top: `${Math.round(element.bbox_px.y * zoom)}px`,
                              width: `${Math.max(1, Math.round(element.bbox_px.width * zoom))}px`,
                              height: `${Math.max(1, Math.round(element.bbox_px.height * zoom))}px`,
                            }
                          : {
                              left: `${element.bbox_norm.x * 100}%`,
                              top: `${element.bbox_norm.y * 100}%`,
                              width: `${element.bbox_norm.width * 100}%`,
                              height: `${element.bbox_norm.height * 100}%`,
                            };

                        return (
                          <button
                            key={element.element_id}
                            type="button"
                            onClick={() =>
                              setSelectedElementId(element.element_id)
                            }
                            className="absolute cursor-pointer overflow-hidden rounded-[10px] border text-left transition-[box-shadow,transform] hover:shadow-sm"
                            style={{
                              ...style,
                              borderColor: color,
                              borderWidth: selected ? 3 : 1,
                              boxShadow: selected
                                ? `0 0 0 2px color-mix(in srgb, ${color} 30%, black)`
                                : undefined,
                              background: selected
                                ? "rgba(103,80,164,0.12)"
                                : "transparent",
                            }}
                            title={`${element.name} (${element.shape_type_name})`}
                          >
                            {showLabels && (
                              <span
                                className="absolute left-1 top-1 max-w-[calc(100%-8px)] truncate rounded-full px-2 py-1 text-[10px] font-medium leading-none text-white shadow-sm"
                                style={{ backgroundColor: color }}
                              >
                                {element.shape_type_name}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </>
              )}
            </main>

            <aside className={`rounded-xl border bg-card p-4`}>
              <h2 className="text-lg font-semibold text-foreground">
                Elements
              </h2>

              <div className="mt-3 space-y-3">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder="Search by name, type, text"
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                />

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => selectAllTypes(true)}
                    className="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
                  >
                    All
                  </button>
                  <button
                    type="button"
                    onClick={() => selectAllTypes(false)}
                    className="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
                  >
                    None
                  </button>
                </div>

                <div className="max-h-36 space-y-1 overflow-auto rounded-[20px] border border-border bg-secondary p-3">
                  {allTypesInDeck.length === 0 && (
                    <p className="text-xs text-muted-foreground">
                      No shape types.
                    </p>
                  )}
                  {allTypesInDeck.map((typeName) => (
                    <label
                      key={typeName}
                      className="flex items-center gap-2 rounded-full px-2 py-1 text-xs text-muted-foreground hover:bg-card"
                    >
                      <input
                        type="checkbox"
                        checked={Boolean(typeFilter[typeName])}
                        onChange={() => toggleType(typeName)}
                        className="h-3.5 w-3.5 rounded accent-primary"
                      />
                      <span className="truncate">{typeName}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="mt-3 max-h-52 space-y-2 overflow-auto rounded-[20px] border border-border bg-secondary p-3">
                {visibleElements.map((element) => {
                  const selected = element.element_id === selectedElementId;
                  return (
                    <button
                      key={element.element_id}
                      type="button"
                      onClick={() => setSelectedElementId(element.element_id)}
                      className={`w-full rounded-[18px] border p-3 text-left text-xs transition ${
                        selected
                          ? "border-primary bg-primary/20 text-primary shadow-sm"
                          : "border-border bg-background text-foreground hover:bg-card"
                      }`}
                    >
                      <p className="font-semibold">
                        {element.name || "(unnamed)"}
                      </p>
                      <p className="mt-0.5 text-[11px] opacity-90">
                        {element.shape_type_name}
                      </p>
                      <p className="mt-1 text-[10px] opacity-80">
                        {formatBBox(element, coordinateMode)}
                      </p>
                    </button>
                  );
                })}
              </div>

              {selectedElement && (
                <div className="mt-3 rounded-[24px] border border-border bg-accent p-4 text-xs text-foreground shadow-sm">
                  <p className="text-sm font-semibold text-foreground">
                    Selected Detail
                  </p>
                  <p className="mt-2">id: {selectedElement.element_id}</p>
                  <p className="mt-1">name: {selectedElement.name}</p>
                  <p className="mt-1">
                    type: {selectedElement.shape_type_name}
                  </p>
                  <p className="mt-1">
                    bbox ({coordinateMode}):{" "}
                    {formatBBox(selectedElement, coordinateMode)}
                  </p>
                  {selectedElement.text && (
                    <p className="mt-2 whitespace-pre-wrap rounded-[16px] bg-background p-3 text-[11px] text-muted-foreground">
                      {selectedElement.text}
                    </p>
                  )}
                  {Object.keys(selectedElement.extra).length > 0 && (
                    <pre className="mt-2 max-h-32 overflow-auto rounded-[16px] bg-background p-3 text-[10px] text-muted-foreground">
                      {JSON.stringify(selectedElement.extra, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </aside>
          </section>
        )}
      </div>
    </div>
  );
}
