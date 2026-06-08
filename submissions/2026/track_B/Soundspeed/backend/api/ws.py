"""WS 转发（1.I 切片 B）：ConnectionManager + /ws 端点。

ConnectionManager 是同步↔异步桥接 seam（设计决策 2）：Orchestrator 的 handler 是
同步的，可能从 event loop 线程内触发（take.changed），也可能从后台线程触发
（asr.*，未来 1.A ASR 线程）。broadcast 是同步方法，按调用线程选投递路径：

  - loop 线程内 → loop.create_task（take.changed 路径）
  - 其它线程   → run_coroutine_threadsafe（asr 路径）

topic 无关：asr.* 与 take.changed 共用一个 seam。frozen dataclass payload 用
asdict() 序列化为 dict。

边界处理（codex 要求）：
  - loop 未设置 / 已关闭 → broadcast 安全 no-op（无 ws 连接时也安全）
  - run_coroutine_threadsafe 的 Future 异常不静默丢弃（done callback 记 warning）
  - 广播时连接集合被并发修改 → 快照迭代（list(self._active)）
  - 广播中途连接 disconnect → 单个 send 失败 catch → 标记移除

/ws 端点鉴权（design §鉴权）：query `?token=<token>` 比对 app.state.admin_token，
用 secrets.compare_digest。不符则 close(1008) 且不 accept；符合则 connect 后
循环 receive_text 保活，WebSocketDisconnect 时 disconnect 清理。
本切片连上即接收全部转发 topic，不做客户端订阅协议。
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from concurrent.futures import Future
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.events import VIEWER_COUNT, ViewerCountPayload

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """WS 连接池 + 同步↔异步桥接 seam。

    持有 event loop 引用（startup 时 set_loop）与活跃连接集合。
    broadcast 同步方法供 Orchestrator handler 直接调用。
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active: set[WebSocket] = set()

    def set_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """记录服务端 event loop 引用（lifespan startup 时调用）。

        shutdown 时传 None 清引用，使后续 broadcast 安全 no-op（loop 停后防泄漏）。
        """
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        """accept WS 并加入活跃集合，随后广播新的在线观看数。

        先加入再广播：新连接此刻已在 _active 里，故它自己也会收到首帧 count，
        解决前端初始值问题（无需额外 REST 拉取）。
        """
        await ws.accept()
        self._active.add(ws)
        self._broadcast_count()

    def disconnect(self, ws: WebSocket) -> None:
        """从活跃集合移除（断开时调用，幂等），随后广播新的在线观看数。"""
        self._active.discard(ws)
        self._broadcast_count()

    def _broadcast_count(self) -> None:
        """连接数变化后向全部活跃连接广播当前在线观看数（viewer.count）。

        复用 broadcast：它按调用线程选投递路径，并在 loop 未设 / 已关 / 已停时安全
        no-op。connect / disconnect 都在 loop 线程内调用（端点协程及其 finally），
        故走 create_task 路径。断开时本连接已从 _active 移除，不会再向死连接投递。
        """
        self.broadcast(VIEWER_COUNT, ViewerCountPayload(count=len(self._active)))

    def broadcast(self, topic: str, payload: Any) -> None:
        """同步广播：把 frozen dataclass payload 序列化后投递给全部活跃连接。

        Orchestrator 的同步 handler 直接调本方法。按调用线程选投递路径。
        无 loop / loop 已关 / loop 已停（stopped-but-not-closed）时安全 no-op。
        """
        # is_running() 守卫：stopped-but-not-closed 的 loop 能过 is_closed() 检查，
        # run_coroutine_threadsafe 调度到不跑的 loop → coroutine 永不执行而泄漏。
        # None 守卫必须在最前短路，否则对 None 调 is_closed() 自炸。
        # 注：loop 内路径（running is self._loop）时 loop 必在跑，不受此守卫影响；
        # 本守卫主要保护跨线程路径（shutdown 后 / loop 未启动时）。
        if self._loop is None or self._loop.is_closed() or not self._loop.is_running():
            return  # 边界：loop 未设 / 已关 / 已停，安全 no-op
        data = {"topic": topic, "payload": asdict(payload)}  # frozen dataclass → dict
        coro = self._async_broadcast(data)

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is self._loop:
            # loop 线程内（take.changed 路径）
            self._loop.create_task(coro)
        else:
            # 其它线程（asr 路径，未来 1.A）
            try:
                fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            except RuntimeError:
                # loop 在守卫与此处之间被停（竞态窗口）：run_coroutine_threadsafe 抛
                # RuntimeError，coro 不会被调度 → 显式 close 防 coroutine 泄漏。
                coro.close()
                logger.debug("ws broadcast skipped: loop not accepting work", exc_info=True)
                return
            fut.add_done_callback(self._log_future_exception)

    @staticmethod
    def _log_future_exception(fut: Future[Any]) -> None:
        """run_coroutine_threadsafe 的 done callback：Future 异常不静默丢弃（记 warning）。

        cancelled 的 Future 调 .exception() 会抛 CancelledError，callback 自身崩，
        故先判 fut.cancelled() 提前返回（shutdown 时 loop 取消未决任务的正常路径）。
        """
        if fut.cancelled():
            return  # cancelled future 取 exception() 会抛 CancelledError → 提前 no-op
        exc = fut.exception()
        if exc is not None:
            logger.warning("ws broadcast failed: %r", exc)

    async def _async_broadcast(self, data: dict[str, Any]) -> None:
        """异步逐个发送（在 loop 线程内执行）。

        快照迭代（边界：广播时并发改集合）；单个连接 send 失败 catch 后标记移除
        （边界：广播中途 disconnect 的死连接清理）。
        """
        for ws in list(self._active):
            try:
                await ws.send_json(data)
            except Exception:
                logger.debug("ws send failed, removing dead connection", exc_info=True)
                self._active.discard(ws)


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    """/ws 端点：query token 鉴权 → connect → receive 保活 → disconnect 清理。

    不符鉴权：close(1008) 且不 accept（握手被拒）。
    """
    cm: ConnectionManager = websocket.app.state.connection_manager
    expected: str = websocket.app.state.admin_token
    token = websocket.query_params.get("token", "")

    # bytes 比对：secrets.compare_digest(str, str) 对含非 ASCII 的 str 抛 TypeError，
    # 在 close(1008) 之前抛 → 握手异常终止。encode 后 bytes 比对对非 ASCII 安全。
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        await websocket.close(code=1008)  # 不 accept，握手被拒
        return

    await cm.connect(websocket)
    try:
        while True:
            # 保活：本切片不消费客户端消息，只等断开
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        # finally 保证任何退出路径都清理连接：WebSocketDisconnect 正常断开，或
        # binary frame 致 receive_text() 抛 KeyError（message 无 "text"）等。
        # KeyError 仍会从端点 task 传播（被记录），但连接已清理，不泄漏在 _active。
        cm.disconnect(websocket)
