#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时弹幕分析 Agent Pipeline

功能:
1) 连接 blivechat 的 WebSocket 弹幕流 (/api/chat)
2) 每个时间窗聚合一次弹幕特征
3) 调用本地 /api/qwen/chat 让大模型输出主播状态指数
4) 结果打印并落盘为 JSONL

示例:
    python agent_pipeline.py --room-id 5633518 --window-seconds 60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import aiohttp


CMD_HEARTBEAT = 0
CMD_JOIN_ROOM = 1
CMD_ADD_TEXT = 2
CMD_ADD_GIFT = 3
CMD_ADD_MEMBER = 4
CMD_ADD_SUPER_CHAT = 5
CMD_DEL_SUPER_CHAT = 6
CMD_UPDATE_TRANSLATION = 7
CMD_FATAL_ERROR = 8


@dataclass
class TextMessage:
    timestamp: int
    author_name: str
    content: str
    author_level: int
    is_gift_danmaku: bool
    is_mirror: bool
    translation: str
    uid: str


class WindowAggregator:
    POSITIVE_WORDS = {
        "哈哈", "好", "喜欢", "牛", "厉害", "可爱", "爱了", "支持", "加油", "稳", "棒", "赞",
    }
    NEGATIVE_WORDS = {
        "烦", "无聊", "菜", "拉", "差", "崩", "生气", "失望", "恶心", "别播", "滚",
    }
    PRESSURE_WORDS = {
        "快点", "快播", "别停", "怎么还不", "催", "播啊", "上强度", "加班", "连麦", "PK",
    }

    def __init__(self, sample_size: int = 15):
        self.sample_size = sample_size
        self._lock = asyncio.Lock()
        self._reset_state()

    def _reset_state(self) -> None:
        self.window_started_at = time.time()
        self.text_messages: List[TextMessage] = []
        self.gift_count = 0
        self.gift_value = 0.0
        self.super_chat_count = 0
        self.super_chat_value = 0.0
        self.member_count = 0
        self.user_counter: Counter[str] = Counter()
        self.keyword_counter: Counter[str] = Counter()
        self.positive_hits = 0
        self.negative_hits = 0
        self.pressure_hits = 0

    async def add_text(self, msg: TextMessage) -> None:
        async with self._lock:
            self.text_messages.append(msg)
            if msg.uid:
                self.user_counter[msg.uid] += 1
            else:
                self.user_counter[msg.author_name] += 1

            lowered = msg.content.lower()
            for w in self.POSITIVE_WORDS:
                if w in lowered:
                    self.positive_hits += 1
                    self.keyword_counter[w] += 1
            for w in self.NEGATIVE_WORDS:
                if w in lowered:
                    self.negative_hits += 1
                    self.keyword_counter[w] += 1
            for w in self.PRESSURE_WORDS:
                if w in lowered:
                    self.pressure_hits += 1
                    self.keyword_counter[w] += 1

    async def add_gift(self, total_coin: int) -> None:
        async with self._lock:
            self.gift_count += 1
            self.gift_value += max(total_coin, 0) / 1000.0

    async def add_super_chat(self, price: float) -> None:
        async with self._lock:
            self.super_chat_count += 1
            self.super_chat_value += max(price, 0.0)

    async def add_member(self) -> None:
        async with self._lock:
            self.member_count += 1

    async def roll_window(self) -> Dict[str, Any]:
        async with self._lock:
            elapsed = max(time.time() - self.window_started_at, 1.0)
            message_count = len(self.text_messages)

            content_samples = self._pick_samples(self.text_messages, self.sample_size)
            avg_level = (
                sum(m.author_level for m in self.text_messages) / message_count
                if message_count > 0 else 0.0
            )
            mirror_ratio = (
                sum(1 for m in self.text_messages if m.is_mirror) / message_count
                if message_count > 0 else 0.0
            )

            top_keywords = [k for k, _ in self.keyword_counter.most_common(12)]
            summary = {
                "window_start": int(self.window_started_at),
                "window_end": int(time.time()),
                "window_seconds": int(elapsed),
                "text_count": message_count,
                "text_per_minute": round((message_count / elapsed) * 60.0, 2),
                "unique_user_count": len(self.user_counter),
                "gift_count": self.gift_count,
                "gift_value": round(self.gift_value, 2),
                "super_chat_count": self.super_chat_count,
                "super_chat_value": round(self.super_chat_value, 2),
                "member_count": self.member_count,
                "positive_hits": self.positive_hits,
                "negative_hits": self.negative_hits,
                "pressure_hits": self.pressure_hits,
                "avg_author_level": round(avg_level, 2),
                "mirror_ratio": round(mirror_ratio, 4),
                "top_keywords": top_keywords,
                "sample_messages": content_samples,
            }
            self._reset_state()
            return summary

    @staticmethod
    def _pick_samples(messages: List[TextMessage], sample_size: int) -> List[str]:
        if not messages:
            return []
        cleaned = [m.content.strip() for m in messages if m.content.strip()]
        if len(cleaned) <= sample_size:
            return cleaned
        return random.sample(cleaned, sample_size)


class LlmPsychAnalyzer:
    def __init__(self, endpoint: str, timeout_seconds: int = 25):
        self.endpoint = endpoint
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def analyze(
        self,
        session: aiohttp.ClientSession,
        room_id: int,
        current: Dict[str, Any],
        recent_windows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(room_id, current, recent_windows)
        payload = {"message": prompt, "history": []}
        async with session.post(self.endpoint, json=payload, timeout=self.timeout) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"LLM endpoint HTTP {resp.status}: {text[:300]}")
            data = json.loads(text)
            if not data.get("success"):
                raise RuntimeError(f"LLM endpoint failed: {data.get('error', 'unknown error')}")
            raw = str(data.get("response", "")).strip()
            parsed = self._extract_json(raw)
            if parsed is None:
                raise RuntimeError(f"LLM 返回无法解析为JSON: {raw[:300]}")

        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
        return {
            "ts": now_iso,
            "room_id": room_id,
            "window_start": current["window_start"],
            "window_end": current["window_end"],
            "metrics": current,
            "analysis": self._normalize_output(parsed),
        }

    def _build_prompt(
        self,
        room_id: int,
        current: Dict[str, Any],
        recent_windows: List[Dict[str, Any]],
    ) -> str:
        schema = {
            "stress": "0-1 浮点数，越高表示主播承压越高",
            "valence": "0-1 浮点数，越高表示主播情绪更积极",
            "fatigue": "0-1 浮点数，越高表示疲劳迹象更明显",
            "engagement": "0-1 浮点数，越高表示互动意愿更高",
            "confidence": "0-1 浮点数，你对判断的置信度",
            "risk_flags": ["字符串数组，最多3个风险标签"],
            "evidence": ["字符串数组，至少2条依据"],
            "summary": "一句中文结论，不超过40字",
        }
        return (
            "你是直播心理状态观察助手。目标是根据弹幕行为给出“状态指数”，"
            "不是医学诊断。\n"
            "请严格输出 JSON，不要包含 markdown 代码块。\n"
            f"输出字段结构: {json.dumps(schema, ensure_ascii=False)}\n"
            "评分要求:\n"
            "- 数值必须在 0 到 1 之间\n"
            "- 不确定时降低 confidence，并在evidence说明原因\n"
            "- evidence 必须引用输入中的统计特征或样例\n"
            f"room_id={room_id}\n"
            f"current_window={json.dumps(current, ensure_ascii=False)}\n"
            f"recent_windows={json.dumps(recent_windows, ensure_ascii=False)}\n"
        )

    @staticmethod
    def _extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _normalize_output(obj: Dict[str, Any]) -> Dict[str, Any]:
        def clamp_float(val: Any, default: float = 0.5) -> float:
            try:
                v = float(val)
            except (TypeError, ValueError):
                v = default
            return max(0.0, min(1.0, v))

        risk_flags = obj.get("risk_flags", [])
        if not isinstance(risk_flags, list):
            risk_flags = [str(risk_flags)]
        evidence = obj.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]

        return {
            "stress": clamp_float(obj.get("stress"), 0.5),
            "valence": clamp_float(obj.get("valence"), 0.5),
            "fatigue": clamp_float(obj.get("fatigue"), 0.5),
            "engagement": clamp_float(obj.get("engagement"), 0.5),
            "confidence": clamp_float(obj.get("confidence"), 0.3),
            "risk_flags": [str(x) for x in risk_flags][:3],
            "evidence": [str(x) for x in evidence][:6],
            "summary": str(obj.get("summary", "")).strip(),
        }


class DanmakuPipeline:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.aggregator = WindowAggregator(sample_size=args.sample_size)
        self.analyzer = LlmPsychAnalyzer(endpoint=args.qwen_endpoint, timeout_seconds=args.llm_timeout)
        self.recent_windows: Deque[Dict[str, Any]] = deque(maxlen=args.trend_windows)

    async def run(self) -> None:
        out_path = Path(self.args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            ingest_task = asyncio.create_task(self._run_ingest_loop(session))
            analyze_task = asyncio.create_task(self._run_analysis_loop(session, out_path))
            try:
                await asyncio.gather(ingest_task, analyze_task)
            except asyncio.CancelledError:
                pass

    async def _run_ingest_loop(self, session: aiohttp.ClientSession) -> None:
        ws_url = f"ws://{self.args.host}:{self.args.port}/api/chat"
        reconnect_delay = 1.0
        while True:
            try:
                print(f"[ingest] connecting: {ws_url}")
                async with session.ws_connect(ws_url, heartbeat=None, autoping=False) as ws:
                    reconnect_delay = 1.0
                    join_payload = {
                        "cmd": CMD_JOIN_ROOM,
                        "data": {
                            "roomKey": {"type": 1, "value": self.args.room_id},
                            "config": {"autoTranslate": False},
                        },
                    }
                    await ws.send_json(join_payload)
                    print(f"[ingest] joined room_id={self.args.room_id}")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_message(ws, msg.data)
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                            break
            except Exception as exc:  # noqa
                print(f"[ingest] disconnected: {exc}")

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 1.8, 15.0)
            reconnect_delay += random.random() * 0.8

    async def _handle_ws_message(self, ws: aiohttp.ClientWebSocketResponse, raw_text: str) -> None:
        body = json.loads(raw_text)
        cmd = int(body.get("cmd", -1))
        data = body.get("data")

        if cmd == CMD_HEARTBEAT:
            await ws.send_json({"cmd": CMD_HEARTBEAT})
            return
        if cmd == CMD_ADD_TEXT and isinstance(data, list) and len(data) >= 19:
            message = TextMessage(
                timestamp=int(data[1]),
                author_name=str(data[2]),
                content=str(data[4]),
                author_level=int(data[7]),
                is_gift_danmaku=bool(data[6]),
                is_mirror=bool(data[18]),
                translation=str(data[12]),
                uid=str(data[16]),
            )
            await self.aggregator.add_text(message)
            return
        if cmd == CMD_ADD_GIFT and isinstance(data, dict):
            await self.aggregator.add_gift(int(data.get("totalCoin", 0)))
            return
        if cmd == CMD_ADD_SUPER_CHAT and isinstance(data, dict):
            await self.aggregator.add_super_chat(float(data.get("price", 0)))
            return
        if cmd == CMD_ADD_MEMBER:
            await self.aggregator.add_member()
            return
        if cmd == CMD_FATAL_ERROR:
            print(f"[ingest] fatal error from server: {data}")

    async def _run_analysis_loop(self, session: aiohttp.ClientSession, out_path: Path) -> None:
        while True:
            await asyncio.sleep(self.args.window_seconds)
            current = await self.aggregator.roll_window()
            self.recent_windows.append(current)
            if current["text_count"] == 0 and current["gift_count"] == 0 and current["super_chat_count"] == 0:
                print("[analysis] empty window, skipped.")
                continue

            trend_input = list(self.recent_windows)[:-1]
            try:
                result = await self.analyzer.analyze(
                    session=session,
                    room_id=self.args.room_id,
                    current=current,
                    recent_windows=trend_input,
                )
            except Exception as exc:  # noqa
                print(f"[analysis] LLM failed: {exc}")
                result = self._fallback_result(current)

            self._print_result(result)
            self._append_jsonl(out_path, result)

    @staticmethod
    def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    @staticmethod
    def _print_result(result: Dict[str, Any]) -> None:
        analysis = result["analysis"]
        print(
            "[analysis]",
            f"time={result['ts']}",
            f"stress={analysis['stress']:.2f}",
            f"valence={analysis['valence']:.2f}",
            f"fatigue={analysis['fatigue']:.2f}",
            f"engagement={analysis['engagement']:.2f}",
            f"confidence={analysis['confidence']:.2f}",
            f"flags={analysis['risk_flags']}",
            f"summary={analysis['summary']}",
            sep=" | ",
        )

    def _fallback_result(self, current: Dict[str, Any]) -> Dict[str, Any]:
        text_count = max(current["text_count"], 1)
        neg_ratio = min(current["negative_hits"] / text_count, 1.0)
        pos_ratio = min(current["positive_hits"] / text_count, 1.0)
        pressure_ratio = min(current["pressure_hits"] / text_count, 1.0)
        stress = min(0.25 + neg_ratio * 0.35 + pressure_ratio * 0.45, 1.0)
        valence = max(0.15, min(0.85, 0.55 + pos_ratio * 0.25 - neg_ratio * 0.3))
        fatigue = min(0.2 + pressure_ratio * 0.35 + (current["text_per_minute"] / 300.0), 1.0)
        engagement = min(0.2 + (current["text_per_minute"] / 180.0) + (current["gift_count"] / 80.0), 1.0)
        flags = []
        if pressure_ratio > 0.22:
            flags.append("催播压力上升")
        if neg_ratio > 0.25:
            flags.append("负向弹幕偏多")
        if current["text_per_minute"] < 8:
            flags.append("互动热度偏低")

        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
        return {
            "ts": now_iso,
            "room_id": self.args.room_id,
            "window_start": current["window_start"],
            "window_end": current["window_end"],
            "metrics": current,
            "analysis": {
                "stress": round(stress, 4),
                "valence": round(valence, 4),
                "fatigue": round(fatigue, 4),
                "engagement": round(engagement, 4),
                "confidence": 0.2,
                "risk_flags": flags[:3],
                "evidence": [
                    f"negative_hits={current['negative_hits']}, positive_hits={current['positive_hits']}",
                    f"pressure_hits={current['pressure_hits']}, text_per_minute={current['text_per_minute']}",
                ],
                "summary": "使用规则回退分析（LLM调用失败）",
            },
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="基于弹幕流的主播状态分析 Agent Pipeline")
    parser.add_argument("--host", default="127.0.0.1", help="blivechat 服务地址")
    parser.add_argument("--port", type=int, default=12450, help="blivechat 服务端口")
    parser.add_argument("--room-id", type=int, required=True, help="房间ID")
    parser.add_argument("--window-seconds", type=int, default=60, help="分析窗口秒数")
    parser.add_argument("--trend-windows", type=int, default=5, help="带入模型的历史窗口数量")
    parser.add_argument("--sample-size", type=int, default=15, help="每窗口抽样弹幕数")
    parser.add_argument(
        "--qwen-endpoint",
        default="http://127.0.0.1:12450/api/qwen/chat",
        help="LLM分析接口地址",
    )
    parser.add_argument("--llm-timeout", type=int, default=25, help="LLM请求超时（秒）")
    parser.add_argument("--output", default="data/psy_state.jsonl", help="输出JSONL文件路径")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    pipeline = DanmakuPipeline(args)
    await pipeline.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
