import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResultView } from "./ResultView";

const NOT_FOUND = {
  error: { code: "not_found", message: "Not found.", issues: [] },
  trace_id: "trace-not-found",
  recovery: null,
};

describe("parent evening result", () => {
  let container: HTMLDivElement;
  let root: Root;
  let queryClient: QueryClient;
  const fetchMock = vi.fn();

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    fetchMock.mockResolvedValue({ ok: false, status: 404, json: async () => NOT_FOUND });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    queryClient.clear();
    vi.unstubAllGlobals();
  });

  it("remains usable without requesting an empty session date", async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}><ResultView /></QueryClientProvider>,
      );
    });
    const dateInput = container.querySelector<HTMLInputElement>("input[type='date']");
    expect(dateInput).not.toBeNull();

    await act(async () => {
      if (!dateInput) return;
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(dateInput, "");
      dateInput.dispatchEvent(new Event("input", { bubbles: true }));
      dateInput.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(container.querySelector("main")).not.toBeNull();
    expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith("session_date="))).toBe(false);
  });
});
