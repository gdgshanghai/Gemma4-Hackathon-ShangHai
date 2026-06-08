import { randomId } from "@/lib/uuid"

// 每个 tab 一个稳定连接标识：发 QP 查询时带上，后端把答案广播到 qp.answer.{CONN_ID}，
// 本 tab 据此认领自己的答案（其他 tab 收到也按前缀过滤掉）。import 时生成一次。
export const CONN_ID: string = randomId("conn")
