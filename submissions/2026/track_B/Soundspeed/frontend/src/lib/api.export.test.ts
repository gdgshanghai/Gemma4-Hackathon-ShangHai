import { describe, expect, it } from "vitest"

import { buildExportFilename, buildExportRequest, todayRange } from "@/lib/api"
import { DEFAULT_FILENAME_FORMAT } from "@/lib/filename-format"

// query 部分单独解析，避开 URLSearchParams 的编码细节（空格变 +、UTF-8 转义等），
// 直接按 decoded 值断言。
function queryOf(url: string): URLSearchParams {
  return new URLSearchParams(url.slice(url.indexOf("?") + 1))
}

describe("buildExportRequest", () => {
  it("无 range、无 token：摊平 fmt 7 参，不带 ts_*，headers 空", () => {
    const { url, headers } = buildExportRequest(DEFAULT_FILENAME_FORMAT, undefined, null)
    expect(url).toContain("/api/v1/takes/export?")

    const q = queryOf(url)
    expect(q.get("scene_prefix")).toBe("Sc")
    expect(q.get("scene_pad")).toBe("0")
    expect(q.get("shot_prefix")).toBe("S")
    expect(q.get("shot_pad")).toBe("0")
    expect(q.get("take_prefix")).toBe("T")
    expect(q.get("take_pad")).toBe("3")
    expect(q.get("sep")).toBe("_")
    expect(q.has("ts_from")).toBe(false)
    expect(q.has("ts_to")).toBe(false)
    expect(headers).toEqual({})
  })

  it("给定 range：附 ts_from/ts_to（半开区间端点原样）", () => {
    const { url } = buildExportRequest(DEFAULT_FILENAME_FORMAT, { from: 1000, to: 87400 }, null)
    const q = queryOf(url)
    expect(q.get("ts_from")).toBe("1000")
    expect(q.get("ts_to")).toBe("87400")
  })

  it("给定 token：带 Bearer Authorization 头", () => {
    const { headers } = buildExportRequest(DEFAULT_FILENAME_FORMAT, undefined, "devtoken")
    expect(headers).toEqual({ Authorization: "Bearer devtoken" })
  })

  it("非默认 fmt：分隔符与补零如实摊平（含含空格分隔符往返）", () => {
    const fmt = {
      scene: { prefix: "", pad: 2 },
      shot: { prefix: "Shot", pad: 1 },
      take: { prefix: "Take", pad: 0 },
      sep: " · ",
    }
    const q = queryOf(buildExportRequest(fmt, undefined, null).url)
    expect(q.get("scene_prefix")).toBe("")
    expect(q.get("scene_pad")).toBe("2")
    expect(q.get("shot_prefix")).toBe("Shot")
    expect(q.get("take_prefix")).toBe("Take")
    expect(q.get("take_pad")).toBe("0")
    expect(q.get("sep")).toBe(" · ")
  })
})

describe("todayRange", () => {
  it("给定 now：from=本地零点秒、to=from+86400", () => {
    const now = new Date(2026, 5, 7, 13, 30, 45)
    const { from, to } = todayRange(now)
    expect(from).toBe(new Date(2026, 5, 7, 0, 0, 0).getTime() / 1000)
    expect(to).toBe(from + 86400)
    expect(Number.isInteger(from)).toBe(true)
  })

  it("默认参数（不传 now）：区间宽度恒为 86400 秒", () => {
    const { from, to } = todayRange()
    expect(to - from).toBe(86400)
  })
})

describe("buildExportFilename", () => {
  it("today：soundspeed_takes_today_<本地日期>.csv", () => {
    expect(buildExportFilename("today", new Date(2026, 5, 7, 13, 30))).toBe(
      "soundspeed_takes_today_2026-06-07.csv",
    )
  })

  it("all：soundspeed_takes_all_<本地日期>.csv", () => {
    expect(buildExportFilename("all", new Date(2026, 5, 7, 13, 30))).toBe(
      "soundspeed_takes_all_2026-06-07.csv",
    )
  })

  it("月/日补零到两位", () => {
    expect(buildExportFilename("all", new Date(2026, 0, 5))).toBe("soundspeed_takes_all_2026-01-05.csv")
  })

  it("纯 ASCII 且恒以 .csv 结尾", () => {
    const name = buildExportFilename("today", new Date(2026, 11, 31))
    expect(name.endsWith(".csv")).toBe(true)
    // eslint-disable-next-line no-control-regex
    expect(/^[\x20-\x7e]+$/.test(name)).toBe(true)
  })
})
