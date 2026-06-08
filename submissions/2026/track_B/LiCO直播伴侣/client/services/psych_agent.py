# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import random
import re
import time
from collections import Counter, deque
from datetime import datetime, timezone
from typing import *

import config
import utils.async_io

logger = logging.getLogger(__name__)

_service: Optional['PsychStateService'] = None


def init():
    global _service
    _service = PsychStateService()
    _service.start()


async def shut_down():
    if _service is not None:
        await _service.stop()


def on_text(room_id: int, content: str, author_level: int, is_mirror: bool, uid: str = ''):
    if _service is not None:
        _service.on_text(room_id, content, author_level, is_mirror, uid)


def on_gift(room_id: int, total_coin: int):
    if _service is not None:
        _service.on_gift(room_id, total_coin)


def on_super_chat(room_id: int, price: float, content: str):
    if _service is not None:
        _service.on_super_chat(room_id, price, content)


def on_member(room_id: int):
    if _service is not None:
        _service.on_member(room_id)


def get_latest_result():
    if _service is None:
        return None
    return _service.get_latest_result()


def get_history(limit: int = 100):
    if _service is None:
        return []
    return _service.get_history(limit)


def get_runtime_config():
    if _service is None:
        return {}
    return _service.get_runtime_config()


def update_runtime_config(
    enabled: Optional[bool] = None,
    room_id: Optional[int] = None,
    window_seconds: Optional[int] = None,
):
    if _service is None:
        return get_runtime_config()
    return _service.update_config(enabled=enabled, room_id=room_id, window_seconds=window_seconds)


class PsychStateService:
    POSITIVE_WORDS = {
        '哈哈', '好', '喜欢', '牛', '厉害', '可爱', '爱了', '支持', '加油', '稳', '棒', '赞',
    }
    NEGATIVE_WORDS = {
        'fw', 'fvv', '菜', '拉', '自裁', '崩', '生气', '失望', '恶心', '别播', '滚', '牛魔', '区',
    }
    PRESSURE_WORDS = {
        '快点', '快播', '别停', '怎么还不', '催', '播啊', '上强度', 'PK', '速度',
    }

    def __init__(self):
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        self.enabled = True
        self.room_id: Optional[int] = None
        self.window_seconds = 10
        self.sample_size = 15
        self.history_maxlen = 300
        self.push_to_room = True

        self._history: Deque[dict] = deque(maxlen=self.history_maxlen)
        self._latest_result: Optional[dict] = None
        self._last_event_room_id: Optional[int] = None
        self._reset_window()

    def start(self):
        self._task = utils.async_io.create_task_with_ref(self._run())

    async def stop(self):
        self._stop_event.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_runtime_config(self):
        return {
            'enabled': self.enabled,
            'roomId': self.room_id,
            'windowSeconds': self.window_seconds,
            'sampleSize': self.sample_size,
            'historySize': len(self._history),
            'pushToRoom': self.push_to_room,
        }

    def update_config(self, enabled=None, room_id=None, window_seconds=None):
        if enabled is not None:
            self.enabled = bool(enabled)
        if room_id is not None:
            self.room_id = int(room_id) if int(room_id) > 0 else None
        if window_seconds is not None:
            self.window_seconds = max(10, min(300, int(window_seconds)))
        return self.get_runtime_config()

    def get_latest_result(self):
        return self._latest_result

    def get_history(self, limit: int):
        if limit <= 0:
            return []
        return list(self._history)[-limit:]

    def _should_accept_room(self, room_id: int) -> bool:
        if not self.enabled:
            return False
        if self.room_id is None:
            return True
        return self.room_id == room_id

    def on_text(self, room_id: int, content: str, author_level: int, is_mirror: bool, uid: str):
        if not self._should_accept_room(room_id):
            return
        self._last_event_room_id = room_id
        self.text_count += 1
        self.user_counter[uid or 'anonymous'] += 1
        self.avg_author_level_sum += max(author_level, 0)
        self.mirror_count += 1 if is_mirror else 0
        text = (content or '').strip()
        if text != '':
            self.sample_messages.append(text)
            lowered = text.lower()
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

    def on_gift(self, room_id: int, total_coin: int):
        if not self._should_accept_room(room_id):
            return
        self._last_event_room_id = room_id
        self.gift_count += 1
        self.gift_value += max(total_coin, 0) / 1000.0

    def on_super_chat(self, room_id: int, price: float, content: str):
        if not self._should_accept_room(room_id):
            return
        self._last_event_room_id = room_id
        self.super_chat_count += 1
        self.super_chat_value += max(price, 0)
        if content:
            self.sample_messages.append(content.strip())

    def on_member(self, room_id: int):
        if not self._should_accept_room(room_id):
            return
        self._last_event_room_id = room_id
        self.member_count += 1

    def _reset_window(self):
        self.window_started_at = time.time()
        self.text_count = 0
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
        self.mirror_count = 0
        self.avg_author_level_sum = 0
        self.sample_messages: List[str] = []

    async def _run(self):
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.window_seconds)
                if self._stop_event.is_set():
                    break
            except asyncio.TimeoutError:
                pass

            result = await self._analyze_window()
            if result is not None:
                self._latest_result = result
                self._history.append(result)
                if self.push_to_room:
                    self._publish_to_room(result)

    async def _analyze_window(self):
        async with self._lock:
            elapsed = max(time.time() - self.window_started_at, 1.0)
            metrics = {
                'windowStart': int(self.window_started_at),
                'windowEnd': int(time.time()),
                'windowSeconds': int(elapsed),
                'textCount': self.text_count,
                'textPerMinute': round(self.text_count / elapsed * 60.0, 2),
                'uniqueUserCount': len(self.user_counter),
                'giftCount': self.gift_count,
                'giftValue': round(self.gift_value, 2),
                'superChatCount': self.super_chat_count,
                'superChatValue': round(self.super_chat_value, 2),
                'memberCount': self.member_count,
                'positiveHits': self.positive_hits,
                'negativeHits': self.negative_hits,
                'pressureHits': self.pressure_hits,
                'mirrorRatio': round((self.mirror_count / self.text_count) if self.text_count > 0 else 0.0, 4),
                'avgAuthorLevel': round((self.avg_author_level_sum / self.text_count) if self.text_count > 0 else 0.0, 2),
                'topKeywords': [k for k, _ in self.keyword_counter.most_common(12)],
                'sampleMessages': self._pick_samples(self.sample_messages),
            }
            self._reset_window()

        if (
            metrics['textCount'] == 0
            and metrics['giftCount'] == 0
            and metrics['superChatCount'] == 0
            and metrics['memberCount'] == 0
            and self._last_event_room_id is None
        ):
            return None

        if metrics['textCount'] == 0:
            analysis = self._fallback_analysis(metrics, summary='最近10秒暂无新弹幕')
        else:
            analysis = await self._analyze_with_qwen(metrics)
        now_iso = datetime.now().astimezone().strftime('%H:%M:%S')
        return {
            'ts': now_iso,
            'roomId': self.room_id if self.room_id is not None else self._last_event_room_id,
            'metrics': metrics,
            'analysis': analysis,
        }

    def _publish_to_room(self, result: dict):
        room_id = result.get('roomId', None)
        if room_id is None:
            return
        try:
            from services import chat as chat_service
        except Exception:
            logger.exception('psych_agent import services.chat failed:')
            return

        room_manager = getattr(chat_service, 'client_room_manager', None)
        if room_manager is None:
            return
        live_client_manager = getattr(chat_service, '_live_client_manager', None)

        target_room = None
        for room in room_manager.iter_rooms():
            room_key = room.room_key
            # 优先按房间键匹配（常见于直接使用房间号）
            if room_key.type == chat_service.RoomKeyType.ROOM_ID and room_key.value == room_id:
                target_room = room
                break

            # 再按 live_client 的真实 room_id 匹配（兼容短号/身份码）
            if live_client_manager is not None:
                live_client = live_client_manager.get_live_client(room_key)
                if live_client is not None and getattr(live_client, 'room_id', None) == room_id:
                    target_room = room
                    break

        if target_room is None and live_client_manager is not None:
            # 最后兜底：拿最近活跃 room_id 和 live_client 对齐
            for room in room_manager.iter_rooms():
                room_key = room.room_key
                live_client = live_client_manager.get_live_client(room_key)
                if live_client is not None and getattr(live_client, 'room_id', None) == self._last_event_room_id:
                    target_room = room
                    break

        if target_room is None:
            logger.debug('psych_agent no room matched for room_id=%s', room_id)
            return

        analysis = result.get('analysis', {})
        risk_flags = analysis.get('riskFlags', []) or []
        risk_text = '、'.join(risk_flags[:2]) if len(risk_flags) > 0 else '无明显风险'
        summary = analysis.get('summary', '').strip() or '状态平稳'
        content = f"【心理分析】风险: {risk_text} | 结论: {summary}"
        # authorType=2 的消息会以系统提示风格显示（与“弹幕获取中请稍后...”一致）
        data = [
            'https://i0.hdslb.com/bfs/face/member/noface.jpg',
            int(time.time()),
            'blivechat',
            2,
            content,
            0,
            0,
            60,
            0,
            1,
            0,
            f"psych_{int(time.time() * 1000)}_{random.randint(100, 999)}",
            '',
            0,
            [],
            [],
            'psych_agent',
            '',
            0,
        ]
        target_room.send_cmd_data(2, data)

    def _pick_samples(self, messages: List[str]) -> List[str]:
        cleaned = [m for m in messages if m]
        if len(cleaned) <= self.sample_size:
            return cleaned
        return random.sample(cleaned, self.sample_size)

    async def _analyze_with_qwen(self, metrics: dict):
        cfg = config.get_config()
        if not cfg.qwen_api_key:
            return self._fallback_analysis(metrics, summary='未配置Qwen API，使用规则分析')
        try:
            import httpx
        except ImportError:
            return self._fallback_analysis(metrics, summary='未安装httpx库，使用规则分析')

        prompt = self._build_prompt(metrics)
        try:
            content = await self._stream_qwen_text(cfg, prompt)
            logger.info('psych_agent qwen raw model output len=%d:\n%s', len(content), content if content else '<EMPTY>')
            if content == '':
                return self._fallback_analysis(metrics, summary='Qwen返回为空，使用规则分析')
            obj = self._extract_json(content)
            if obj is None:
                logger.warning('psych_agent qwen JSON parse failed, raw output:\n%s', content)
                return self._fallback_analysis(metrics, summary='Qwen返回格式错误，使用规则分析')
            return self._normalize_llm_result(obj)
        except Exception:
            logger.exception('psych_agent call qwen failed:')
            return self._fallback_analysis(metrics, summary='Qwen调用失败，使用规则分析')

    @staticmethod
    async def _stream_qwen_text(cfg, prompt: str) -> str:
        import httpx

        payload = {
            'model': cfg.qwen_model,
            'stream': True,
            'max_tokens': 384,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        body_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        body_mb = len(body_bytes) / (1024 * 1024)
        started_at = time.perf_counter()
        first_sse_at = 0.0
        first_text_at = 0.0
        raw_sse_lines = 0
        content_chunks = 0
        reasoning_chunks = 0
        raw_sse_samples: List[str] = []
        parts: List[str] = []

        timeout_cfg = httpx.Timeout(connect=10.0, read=90.0, write=120.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout_cfg) as client:
            async with client.stream(
                'POST',
                f"{cfg.qwen_base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {cfg.qwen_api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                },
                json=payload,
            ) as response:
                logger.info(
                    'psych_agent qwen stream opened: body_size_mb=%.3f, http_status=%s',
                    body_mb, response.status_code,
                )
                if response.status_code != 200:
                    err_body = (await response.aread()).decode('utf-8', errors='ignore')
                    raise RuntimeError(f'Qwen service returned {response.status_code}: {err_body[:300]}')

                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    raw_sse_lines += 1
                    if first_sse_at == 0.0:
                        first_sse_at = time.perf_counter()
                        logger.info(
                            'psych_agent qwen first SSE byte after %.2fs: %r',
                            first_sse_at - started_at, line[:200],
                        )
                    if len(raw_sse_samples) < 5:
                        raw_sse_samples.append(line[:500])
                    if line.startswith(':'):
                        continue
                    if line.startswith('data:'):
                        line = line[5:].strip()
                    if line == '' or line == '[DONE]':
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning('psych_agent qwen bad SSE JSON: %s', line[:500])
                        continue

                    choice = (event.get('choices') or [{}])[0]
                    delta = choice.get('delta') or {}
                    delta_content = delta.get('content')
                    delta_reasoning = delta.get('reasoning')
                    text_piece = ''
                    if isinstance(delta_content, str) and delta_content:
                        text_piece = delta_content
                        content_chunks += 1
                    elif isinstance(delta_content, list):
                        for item in delta_content:
                            if isinstance(item, dict) and isinstance(item.get('text'), str):
                                text_piece += item['text']
                        if text_piece:
                            content_chunks += 1
                    elif isinstance(delta_reasoning, str) and delta_reasoning:
                        text_piece = delta_reasoning
                        reasoning_chunks += 1
                    elif isinstance(delta_reasoning, list):
                        for item in delta_reasoning:
                            if isinstance(item, dict) and isinstance(item.get('text'), str):
                                text_piece += item['text']
                        if text_piece:
                            reasoning_chunks += 1

                    if text_piece:
                        if first_text_at == 0.0:
                            first_text_at = time.perf_counter()
                            logger.info(
                                'psych_agent qwen first text chunk after %.2fs',
                                first_text_at - started_at,
                            )
                        parts.append(text_piece)

        total_elapsed = time.perf_counter() - started_at
        content = ''.join(parts)
        logger.info(
            'psych_agent qwen stream debug: body_size_mb=%.3f, http_status=200, '
            'first_sse_byte=%.2fs, first_text_chunk=%s, total_time=%.2fs, '
            'content_chunks=%d, reasoning_chunks=%d, raw_sse_lines=%d, raw_sse_samples=%s',
            body_mb,
            (first_sse_at - started_at) if first_sse_at else -1,
            f'{first_text_at - started_at:.2f}s' if first_text_at else 'none',
            total_elapsed,
            content_chunks,
            reasoning_chunks,
            raw_sse_lines,
            raw_sse_samples,
        )
        return content

    @staticmethod
    def _build_prompt(metrics: dict):
        return (
            '你是直播心理状态观察助手。请根据输入统计，评估当前的直播间氛围，以及对主播心里可能产生的潜在影响。不是医学诊断。'
            '严格输出JSON，不要markdown。\n'
            'JSON字段: stress,valence,fatigue,engagement,confidence,riskFlags,evidence,summary。\n'
            '所有数值在0-1之间，riskFlags为数组(<=3)，evidence为数组(>=2)。\n'
            f'输入统计={json.dumps(metrics, ensure_ascii=False)}'
        )

    @staticmethod
    def _extract_json(content: str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _normalize_llm_result(obj: dict):
        def clamp(value, default=0.5):
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = default
            return max(0.0, min(1.0, value))

        risk_flags = obj.get('riskFlags', [])
        if not isinstance(risk_flags, list):
            risk_flags = [str(risk_flags)]
        evidence = obj.get('evidence', [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        return {
            'stress': clamp(obj.get('stress')),
            'valence': clamp(obj.get('valence')),
            'fatigue': clamp(obj.get('fatigue')),
            'engagement': clamp(obj.get('engagement')),
            'confidence': clamp(obj.get('confidence'), 0.3),
            'riskFlags': [str(x) for x in risk_flags][:3],
            'evidence': [str(x) for x in evidence][:6],
            'summary': str(obj.get('summary', '')).strip(),
        }

    def _fallback_analysis(self, metrics: dict, summary: str):
        text_count = max(metrics['textCount'], 1)
        neg_ratio = min(metrics['negativeHits'] / text_count, 1.0)
        pos_ratio = min(metrics['positiveHits'] / text_count, 1.0)
        pressure_ratio = min(metrics['pressureHits'] / text_count, 1.0)
        if neg_ratio > 0 and pos_ratio > 0:
            stress = min(0.25 + neg_ratio * 0.35 + pressure_ratio * 0.45, 1.0)
            valence = max(0.15, min(0.85, 0.55 + pos_ratio * 0.25 - neg_ratio * 0.3))
            fatigue = min(0.2 + pressure_ratio * 0.35 + (metrics['textPerMinute'] / 300.0), 1.0)
            engagement = min(0.2 + (metrics['textPerMinute'] / 180.0) + (metrics['giftCount'] / 80.0), 1.0)
        else:
            stress = 0
            valence = 0
            fatigue = 0
            engagement = 0
        flags = []
        if pressure_ratio > 0.22:
            flags.append('催播压力上升')
        if neg_ratio > 0.25:
            flags.append('负向弹幕偏多')
        return {
            'stress': round(stress, 4),
            'valence': round(valence, 4),
            'fatigue': round(fatigue, 4),
            'engagement': round(engagement, 4),
            'confidence': 0.2,
            'riskFlags': flags[:3],
            'evidence': [
                f"negativeHits={metrics['negativeHits']}, positiveHits={metrics['positiveHits']}",
                f"pressureHits={metrics['pressureHits']}, textPerMinute={metrics['textPerMinute']}",
            ],
            'summary': summary,
        }
