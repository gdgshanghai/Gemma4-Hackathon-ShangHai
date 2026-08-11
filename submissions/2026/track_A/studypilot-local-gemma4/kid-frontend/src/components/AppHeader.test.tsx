import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppHeader } from "./AppHeader";

describe("demo header controls", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });

  it("requires confirmation before reopening today's demo", async () => {
    const onResetDemo = vi.fn(async () => undefined);
    vi.stubGlobal("confirm", vi.fn(() => false));
    await act(async () => {
      root.render(
        <AppHeader
          session={undefined}
          reviewOpen={false}
          notice={null}
          demoMode
          onResetDemo={onResetDemo}
          onDismissNotice={() => undefined}
        />,
      );
    });
    const reset = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("重开今日演示"),
    );
    expect(reset).toBeDefined();
    await act(async () => reset?.click());
    expect(onResetDemo).not.toHaveBeenCalled();

    vi.mocked(confirm).mockReturnValue(true);
    await act(async () => reset?.click());
    expect(onResetDemo).toHaveBeenCalledOnce();
  });

  it("asks for an explicit reset when the fixed demo script changed", async () => {
    await act(async () => {
      root.render(
        <AppHeader
          session={undefined}
          reviewOpen={false}
          notice={null}
          demoMode
          demoOutdated
          onResetDemo={async () => undefined}
          onDismissNotice={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain("演示脚本已更新，请重开今日演示");
  });

  it("shows what each step helps the child accomplish", async () => {
    await act(async () => {
      root.render(
        <AppHeader
          session={undefined}
          reviewOpen={false}
          notice={null}
          onDismissNotice={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain("今晚盘点");
    expect(container.textContent).toContain("把作业说清");
    expect(container.textContent).toContain("今晚全貌");
    expect(container.textContent).toContain("看见全部任务");
    expect(container.textContent).toContain("我的路线");
    expect(container.textContent).toContain("确定今晚顺序");
    expect(container.textContent).toContain("睡前复盘");
    expect(container.textContent).toContain("只说没完成");
  });

  it("uses the registered product name and a positive child promise", async () => {
    await act(async () => {
      root.render(
        <AppHeader
          session={undefined}
          reviewOpen={false}
          notice={null}
          onDismissNotice={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain("时间规划小助手");
    expect(container.textContent).toContain("先看清今晚，再一步步完成");
    expect(container.textContent).not.toContain("今晚不是做不完");
  });
});
