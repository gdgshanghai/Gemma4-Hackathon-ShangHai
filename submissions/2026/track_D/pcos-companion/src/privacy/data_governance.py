"""
数据治理 —— 加密存储 / 最小必要 / 可删除（赛道 D 隐私保护实现层）。

要点：
  - 健康事件以 AES-GCM 加密后落本地（自托管），密钥来自环境变量/KMS。
  - user_id 在入口处做不可逆哈希假名化，库内不存微信 openid 明文。
  - 提供 erase_user(用户一键删除全部数据)，落实「被遗忘权」。
本文件为 MVP 演示实现，接口稳定，可平滑替换为生产级 KMS + 数据库。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _HAS_CRYPTO = True
except ImportError:  # 演示环境降级（生产必须装 cryptography）
    _HAS_CRYPTO = False

_STORE = Path(os.getenv("PROFILE_STORE", "/tmp/pcos_profiles"))
_STORE.mkdir(parents=True, exist_ok=True)
_KEY = bytes.fromhex(os.getenv("DATA_KEY_HEX", "00" * 32))   # 32 bytes，生产从 KMS 注入
_PEPPER = os.getenv("ID_PEPPER", "ta-health-pepper").encode()


def pseudonymize(openid: str) -> str:
    """把微信 openid 假名化为不可逆 user_id，库内不存明文。"""
    return hmac.new(_PEPPER, openid.encode(), hashlib.sha256).hexdigest()[:24]


def _path(user_id: str) -> Path:
    return _STORE / f"{user_id}.bin"


def _encrypt(plaintext: bytes) -> bytes:
    if not _HAS_CRYPTO:
        return plaintext
    nonce = os.urandom(12)
    return nonce + AESGCM(_KEY).encrypt(nonce, plaintext, None)


def _decrypt(blob: bytes) -> bytes:
    if not _HAS_CRYPTO:
        return blob
    return AESGCM(_KEY).decrypt(blob[:12], blob[12:], None)


def write_profile_event(user_id: str, event: dict[str, Any]) -> None:
    events = read_profile_events(user_id)
    events.append(event)
    blob = _encrypt(json.dumps(events, ensure_ascii=False).encode("utf-8"))
    _path(user_id).write_bytes(blob)


def read_profile_events(user_id: str) -> list[dict[str, Any]]:
    p = _path(user_id)
    if not p.exists():
        return []
    try:
        return json.loads(_decrypt(p.read_bytes()).decode("utf-8"))
    except Exception:
        return []


def erase_user(user_id: str) -> dict[str, Any]:
    """被遗忘权：一键彻底删除该用户全部数据。"""
    p = _path(user_id)
    existed = p.exists()
    if existed:
        p.unlink()
    return {"erased": existed, "user_id": user_id}
