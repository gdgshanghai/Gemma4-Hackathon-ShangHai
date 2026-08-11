import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { AppHeader } from "./AppHeader";

describe("parent workspace header", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("uses the registered product name and names the surface as a family workspace", async () => {
    await act(async () => {
      root.render(
        <MemoryRouter initialEntries={["/brief"]}>
          <AppHeader />
        </MemoryRouter>,
      );
    });

    expect(container.textContent).toContain("时间规划小助手");
    expect(container.textContent).toContain("家庭工作台");
    expect([...container.querySelectorAll("a")].map((item) => [
      item.textContent?.trim(),
      item.getAttribute("href"),
    ])).toEqual([
      ["今日作业单", "/brief"],
      ["本周校准", "/calibration"],
      ["晚间记录", "/result"],
    ]);
  });
});
