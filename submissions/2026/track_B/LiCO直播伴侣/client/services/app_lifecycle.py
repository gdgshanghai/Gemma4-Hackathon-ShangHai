# -*- coding: utf-8 -*-
import asyncio
from typing import Callable, Optional

_shutdown_request: Optional[Callable[[], None]] = None
_shutting_down = False


def register_shutdown_request(callback: Callable[[], None]) -> None:
    global _shutdown_request
    _shutdown_request = callback


def begin_shutdown() -> None:
    global _shutting_down
    _shutting_down = True


def is_shutting_down() -> bool:
    return _shutting_down


def request_shutdown() -> bool:
    if _shutdown_request is None:
        return False
    # 让当前 HTTP 响应先完成，再在下一轮事件循环里触发关闭
    loop = asyncio.get_running_loop()
    loop.call_soon(_shutdown_request)
    return True


def install_asyncio_exception_handler() -> None:
    loop = asyncio.get_running_loop()
    default_handler = loop.get_exception_handler()

    def handler(inner_loop, context):
        exc = context.get('exception')
        if isinstance(exc, asyncio.CancelledError) and is_shutting_down():
            return
        if (
            is_shutting_down()
            and isinstance(exc, RuntimeError)
            and exc is not None
            and 'Session is closed' in str(exc)
        ):
            return
        if default_handler is not None:
            default_handler(inner_loop, context)
        else:
            inner_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
