"""鉴权（architecture §10.3）。

ADMIN_TOKEN 解析优先级：
  1. ADMIN_TOKEN env 已设 → 直接使用（最高优先级）。
  2. SOUNDSPEED_DEV=1 → 固定返回 "devtoken"（前端可自动填，dev server 确定性）。
  3. 其他 → 随机生成并打印到 console（hackathon 现场友好）。

REST：require_admin 依赖校验 `Authorization: Bearer <token>`，不符 401。
auth 路径本身不变——固定 "devtoken" 只是让 dev token 可预测，不绕过鉴权。

token 在 create_app 时解析并存到 app.state.admin_token，require_admin 通过
request.app.state 读取——不在 import 时捕获环境（否则测试 monkeypatch.setenv 不生效）。

注意：用 HTTPBearer(auto_error=False)。默认 auto_error=True 时缺失 Authorization 头
会返回 403，而 contract 要求 401。这里关掉自动报错，自己抛 401。
"""
from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

_DEV_TOKEN = "devtoken"


def resolve_admin_token() -> str:
    """解析 ADMIN_TOKEN，优先级：env 显式设置 > DEV 固定值 > 随机生成。

    在 create_app 时调用（不在 import 时），保证测试 monkeypatch.setenv 生效。
    """
    token = os.environ.get("ADMIN_TOKEN")
    if token:
        return token
    if os.environ.get("SOUNDSPEED_DEV") == "1":
        print(f"[soundspeed] SOUNDSPEED_DEV=1，使用固定 ADMIN_TOKEN：{_DEV_TOKEN}")
        return _DEV_TOKEN
    token = secrets.token_urlsafe(32)
    print(f"[soundspeed] ADMIN_TOKEN 未设置，已随机生成：{token}")
    return token


def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """校验 Authorization: Bearer <token>，不符抛 401。

    缺失头 / scheme 非 bearer / token 不匹配 → 401（不是 403）。
    """
    expected: str = request.app.state.admin_token
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(
            credentials.credentials.encode("utf-8"), expected.encode("utf-8")
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
