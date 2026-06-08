# -*- coding: utf-8 -*-
import asyncio
import base64
import io
import json
import logging
import mimetypes
import os
import re
import time
from typing import *

import api.base
import config
import services.obs_bridge

logger = logging.getLogger(__name__)


class QwenMultimodalBaseHandler(api.base.ApiHandler):
    def _get_config_or_error(self):
        cfg = config.get_config()
        if not cfg.qwen_api_key:
            self.write({
                'success': False,
                'error': '未配置Qwen API密钥。请在config.ini中配置[qwen]部分的api_key'
            })
            return None
        return cfg

    @staticmethod
    def _get_usage(completion):
        usage = getattr(completion, 'usage', None)
        input_tokens = getattr(usage, 'prompt_tokens', 0) if usage is not None else 0
        output_tokens = getattr(usage, 'completion_tokens', 0) if usage is not None else 0
        total_tokens = getattr(usage, 'total_tokens', input_tokens + output_tokens) if usage is not None else 0
        return {
            'inputTokens': input_tokens,
            'outputTokens': output_tokens,
            'totalTokens': total_tokens,
        }

    @staticmethod
    def _extract_json_object(text: str):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match is None:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _as_text(value, default=''):
        value = str(value or '').strip()
        return value if value != '' else default

    @staticmethod
    def _compress_image_data_url(data_url: str, max_side: int = 1280, quality: int = 70) -> str:
        """
        把任意 data:image/...;base64,... 图片压成 JPEG。
        - 长边超过 max_side 时按比例缩小
        - 强制转 JPEG quality=70
        - 失败时原样返回，不影响上层逻辑
        """
        if not data_url or not data_url.startswith('data:image/'):
            return data_url
        try:
            from PIL import Image
        except ImportError:
            logger.warning('Pillow not installed, skipping image compression')
            return data_url
        try:
            _, b64 = data_url.split(',', 1)
        except ValueError:
            return data_url
        try:
            raw = base64.b64decode(b64)
        except Exception:
            return data_url
        before_kb = len(raw) / 1024
        try:
            with io.BytesIO(raw) as in_buf:
                img = Image.open(in_buf)
                img.load()
            orig_w, orig_h = img.size
            scale = min(1.0, max_side / max(orig_w, orig_h))
            if scale < 1.0:
                new_w = max(1, int(orig_w * scale))
                new_h = max(1, int(orig_h * scale))
                img = img.resize((new_w, new_h), Image.LANCZOS)
            else:
                new_w, new_h = orig_w, orig_h
            if img.mode != 'RGB':
                img = img.convert('RGB')
            out_buf = io.BytesIO()
            img.save(out_buf, format='JPEG', quality=quality, optimize=True)
            jpeg_bytes = out_buf.getvalue()
            after_kb = len(jpeg_bytes) / 1024
            saved_pct = (1 - after_kb / max(before_kb, 1)) * 100
            logger.info(
                'Image compressed: %.1fKB -> %.1fKB (saved %.1f%%), %dx%d -> %dx%d',
                before_kb, after_kb, saved_pct, orig_w, orig_h, new_w, new_h,
            )
            encoded = base64.b64encode(jpeg_bytes).decode('ascii')
            return f'data:image/jpeg;base64,{encoded}'
        except Exception as e:
            logger.warning('Image compression failed, sending original: %s', e)
            return data_url


class QwenAsrReportHandler(QwenMultimodalBaseHandler):
    MIC_PROMPT = [
        '你是直播语音观察助手。这段音频来自主播麦克风，代表主播的真实人声。',
        '请转写主播说了什么，并判断主播正在做什么，以及可从语音观察到的外显心理状态。',
        '这不是医学诊断。',
        '严格输出JSON，不要markdown。',
        '字段: transcript,activity,psychologicalState,confidence,evidence,summary。',
        'confidence为0-1，evidence数组最多3条，summary不超过40字。',
    ]
    DESKTOP_PROMPT = [
        '你是直播语音观察助手。这段音频来自桌面音频（游戏音效、视频声、BGM、其他玩家语音等），不包含主播麦克风直接拾音。',
        '请判断主导声音类别（游戏声音/视频声音/BGM/其他玩家声音/混合），并简要描述画面外信息。',
        '严格输出JSON，不要markdown。',
        '字段: transcript,soundType,activity,confidence,evidence,summary。',
        'confidence为0-1，evidence数组最多3条，summary不超过40字。',
    ]
    MIXED_PROMPT = [
        '你是直播语音观察助手。请根据这段OBS直播混音音频判断主导时声音类别是什么（主播的声音，BGM，视频声音，游戏声音）。然后根据声音类别判断主播正在做什么，以及主播外显心理状态。',
        '这不是医学诊断，只描述可从语音中观察到的状态。',
        '严格输出JSON，不要markdown。',
        '字段: transcript,soundType,activity,psychologicalState,confidence,evidence,summary。',
        'confidence为0-1，evidence数组最多3条，summary不超过40字。',
    ]

    async def post(self):
        cfg = self._get_config_or_error()
        if cfg is None:
            return

        state = services.obs_bridge.get_state()
        split_audio = bool(state.get('splitAudioTracks'))
        if split_audio:
            await self._post_split_asr_report(cfg, state)
            return

        audio = state.get('latestAudio') or {}
        audio_data = str(audio.get('audioData', '') or '').strip()
        if audio_data == '':
            self.write({
                'success': False,
                'error': 'OBS尚未上报可识别的音频片段',
            })
            return

        try:
            response, usage = await self._analyze_audio_clip(cfg, audio, self.MIXED_PROMPT)
            report = self._normalize_asr_report(response)
            report['audioAt'] = audio.get('ts', '')
            report['durationSeconds'] = audio.get('durationSeconds', 0)
            report['splitAudioTracks'] = False
            self.write({
                'success': True,
                'response': response,
                'report': report,
                'usage': usage,
            })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception('Qwen ASR report failed:')
            self.write({'success': False, 'error': str(e)})

    async def _post_split_asr_report(self, cfg, state: dict):
        mic_audio = state.get('latestMicAudio') or {}
        desktop_audio = state.get('latestDesktopAudio') or {}
        if str(mic_audio.get('audioData', '') or '').strip() == '':
            self.write({
                'success': False,
                'error': 'OBS尚未上报麦克风轨音频片段。请确认已在OBS高级音频属性中将麦克风分配到轨道2。',
            })
            return
        if str(desktop_audio.get('audioData', '') or '').strip() == '':
            self.write({
                'success': False,
                'error': 'OBS尚未上报桌面音频轨片段。请确认已在OBS高级音频属性中将桌面音频分配到轨道3。',
            })
            return

        try:
            mic_response, mic_usage = await self._analyze_audio_clip(cfg, mic_audio, self.MIC_PROMPT)
            desktop_response, desktop_usage = await self._analyze_audio_clip(cfg, desktop_audio, self.DESKTOP_PROMPT)
            report = self._merge_split_asr_report(
                self._normalize_mic_asr_report(mic_response),
                self._normalize_desktop_asr_report(desktop_response),
                mic_audio,
                desktop_audio,
            )
            self.write({
                'success': True,
                'response': {
                    'mic': mic_response,
                    'desktop': desktop_response,
                },
                'report': report,
                'usage': self._merge_usage(mic_usage, desktop_usage),
            })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception('Qwen split ASR report failed:')
            self.write({'success': False, 'error': str(e)})

    async def _analyze_audio_clip(self, cfg, audio: dict, prompt_lines: List[str]):
        audio_data = str(audio.get('audioData', '') or '').strip()
        audio_format = str(audio.get('audioFormat', '') or 'wav').strip().lower()
        audio_input = self._build_audio_input(audio_data, audio_format)
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=cfg.qwen_api_key, base_url=cfg.qwen_base_url)
        stream = await self.run_cancel_safe(client.chat.completions.create(
            model=cfg.qwen_asr_model,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'input_audio',
                        'input_audio': {
                            'data': audio_input,
                            'format': audio_format,
                        }
                    },
                    {'type': 'text', 'text': '\n'.join(prompt_lines)},
                ],
            }],
            modalities=['text'],
            stream=True,
            stream_options={'include_usage': True},
        ))
        return await self.run_cancel_safe(self._collect_stream_response(stream))

    @staticmethod
    def _build_audio_input(audio_data: str, audio_format: str):
        if audio_data.startswith('data:audio/'):
            return audio_data
        if audio_data.startswith('data:') and ',' in audio_data:
            return f'data:audio/{audio_format};base64,{audio_data.split(",", 1)[1]}'
        return f'data:audio/{audio_format};base64,{audio_data}'

    @staticmethod
    def _merge_usage(first_usage: dict, second_usage: dict):
        return {
            'inputTokens': int(first_usage.get('inputTokens', 0)) + int(second_usage.get('inputTokens', 0)),
            'outputTokens': int(first_usage.get('outputTokens', 0)) + int(second_usage.get('outputTokens', 0)),
            'totalTokens': int(first_usage.get('totalTokens', 0)) + int(second_usage.get('totalTokens', 0)),
        }

    def _normalize_mic_asr_report(self, response: str):
        obj = self._extract_json_object(response) or {}
        evidence = obj.get('evidence', [])
        if not isinstance(evidence, list):
            evidence = [evidence]
        try:
            confidence = float(obj.get('confidence', 0.3))
        except (TypeError, ValueError):
            confidence = 0.3
        return {
            'transcript': self._as_text(obj.get('transcript')),
            'activity': self._as_text(obj.get('activity'), '无法判断主播正在做什么'),
            'psychologicalState': self._as_text(obj.get('psychologicalState'), '无法判断心理状态'),
            'confidence': max(0.0, min(1.0, confidence)),
            'evidence': [str(item).strip() for item in evidence if str(item).strip() != ''][:3],
            'summary': self._as_text(obj.get('summary'), response.strip()[:80]),
        }

    def _normalize_desktop_asr_report(self, response: str):
        obj = self._extract_json_object(response) or {}
        evidence = obj.get('evidence', [])
        if not isinstance(evidence, list):
            evidence = [evidence]
        try:
            confidence = float(obj.get('confidence', 0.3))
        except (TypeError, ValueError):
            confidence = 0.3
        return {
            'transcript': self._as_text(obj.get('transcript')),
            'soundType': self._as_text(obj.get('soundType'), '无法判断桌面主导声音类别'),
            'activity': self._as_text(obj.get('activity'), '无法判断桌面音频场景'),
            'confidence': max(0.0, min(1.0, confidence)),
            'evidence': [str(item).strip() for item in evidence if str(item).strip() != ''][:3],
            'summary': self._as_text(obj.get('summary'), response.strip()[:80]),
        }

    def _merge_split_asr_report(self, mic_report: dict, desktop_report: dict, mic_audio: dict, desktop_audio: dict):
        evidence = []
        for item in mic_report.get('evidence', []):
            evidence.append(f'[麦克风] {item}')
        for item in desktop_report.get('evidence', []):
            evidence.append(f'[桌面] {item}')
        confidence_values = [
            float(mic_report.get('confidence', 0.3)),
            float(desktop_report.get('confidence', 0.3)),
        ]
        summary_parts = []
        if mic_report.get('summary'):
            summary_parts.append(f'主播：{mic_report["summary"]}')
        if desktop_report.get('summary'):
            summary_parts.append(f'桌面：{desktop_report["summary"]}')
        return {
            'transcript': mic_report.get('transcript', ''),
            'soundType': desktop_report.get('soundType', '无法判断桌面主导声音类别'),
            'activity': mic_report.get('activity', '无法判断主播正在做什么'),
            'psychologicalState': mic_report.get('psychologicalState', '无法判断心理状态'),
            'desktopTranscript': desktop_report.get('transcript', ''),
            'desktopSoundType': desktop_report.get('soundType', ''),
            'desktopActivity': desktop_report.get('activity', ''),
            'confidence': round(sum(confidence_values) / len(confidence_values), 4),
            'evidence': evidence[:6],
            'summary': '；'.join(summary_parts)[:80] if summary_parts else '分轨语音分析完成',
            'splitAudioTracks': True,
            'micAudioAt': mic_audio.get('ts', ''),
            'desktopAudioAt': desktop_audio.get('ts', ''),
            'durationSeconds': max(
                self._to_float(mic_audio.get('durationSeconds', 0)),
                self._to_float(desktop_audio.get('durationSeconds', 0)),
            ),
        }

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    async def _collect_stream_response(stream):
        content_parts = []
        usage = {
            'inputTokens': 0,
            'outputTokens': 0,
            'totalTokens': 0,
        }
        async for chunk in stream:
            if getattr(chunk, 'usage', None) is not None:
                usage = QwenMultimodalBaseHandler._get_usage(chunk)
            choices = getattr(chunk, 'choices', None) or []
            if len(choices) == 0:
                continue
            delta = getattr(choices[0], 'delta', None)
            text = getattr(delta, 'content', '') if delta is not None else ''
            if text:
                content_parts.append(text)
        return ''.join(content_parts), usage

    def _normalize_asr_report(self, response: str):
        obj = self._extract_json_object(response) or {}
        evidence = obj.get('evidence', [])
        if not isinstance(evidence, list):
            evidence = [evidence]
        try:
            confidence = float(obj.get('confidence', 0.3))
        except (TypeError, ValueError):
            confidence = 0.3
        return {
            'transcript': self._as_text(obj.get('transcript')),
            'soundType': self._as_text(obj.get('soundType'), '无法判断主导声音类别'),
            'activity': self._as_text(obj.get('activity'), '无法判断主播正在做什么'),
            'psychologicalState': self._as_text(obj.get('psychologicalState'), '无法判断心理状态'),
            'confidence': max(0.0, min(1.0, confidence)),
            'evidence': [str(item).strip() for item in evidence if str(item).strip() != ''][:3],
            'summary': self._as_text(obj.get('summary'), response.strip()[:80]),
        }


class QwenVisionReportHandler(QwenMultimodalBaseHandler):
    async def post(self):
        cfg = self._get_config_or_error()
        if cfg is None:
            return

        state = services.obs_bridge.get_state()
        frame = state.get('latestFrame') or {}
        image_url = self._compress_image_data_url(self._build_image_url(frame))
        if image_url == '':
            self.write({
                'success': False,
                'error': 'OBS尚未上报可分析的截图',
            })
            return

        prompt = [
            '你是直播画面场景识别助手。请根据OBS截图判断当前直播场景。',
            '只能在这三类中选择一个: 游戏中、唱歌中、观看视频中。',
            '如果画面信息不足，也必须选择最可能的一类，并降低confidence。',
            '严格输出JSON，不要markdown。',
            '字段: category,confidence,evidence,summary。',
            'category只能是: 游戏中 / 唱歌中 / 观看视频中；confidence为0-1；evidence数组最多3条；summary不超过40字。'
        ]

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=cfg.qwen_api_key, base_url=cfg.qwen_base_url)
            completion = await self.run_cancel_safe(client.chat.completions.create(
                model=cfg.qwen_vision_model,
                messages=[{
                    'role': 'user',
                    'content': [
                        {'type': 'image_url', 'image_url': {'url': image_url}},
                        {'type': 'text', 'text': '\n'.join(prompt)},
                    ],
                }],
            ))
            response = completion.choices[0].message.content or ''
            report = self._normalize_vision_report(response)
            report['frameAt'] = frame.get('ts', '')
            self.write({
                'success': True,
                'response': response,
                'report': report,
                'usage': self._get_usage(completion),
            })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception('Qwen vision report failed:')
            self.write({'success': False, 'error': str(e)})

    def _build_image_url(self, frame: dict):
        image_data = str(frame.get('imageData', '') or '').strip()
        if image_data.startswith('data:image/'):
            return image_data
        if image_data != '':
            image_format = str(frame.get('imageFormat', '') or 'jpeg').strip().lower()
            if image_format == 'jpg':
                image_format = 'jpeg'
            return f'data:image/{image_format};base64,{image_data}'

        image_path = str(frame.get('imageFilePath', '') or '').strip()
        if image_path == '' or not os.path.isfile(image_path):
            return ''
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
        with open(image_path, 'rb') as image_file:
            encoded = base64.b64encode(image_file.read()).decode('ascii')
        return f'data:{mime_type};base64,{encoded}'

    def _normalize_vision_report(self, response: str):
        obj = self._extract_json_object(response) or {}
        allowed_categories = {'游戏中', '唱歌中', '观看视频中'}
        category = str(obj.get('category', '') or '').strip()
        if category not in allowed_categories:
            category = self._pick_category(response)
        evidence = obj.get('evidence', [])
        if not isinstance(evidence, list):
            evidence = [evidence]
        try:
            confidence = float(obj.get('confidence', 0.3))
        except (TypeError, ValueError):
            confidence = 0.3
        return {
            'category': category,
            'confidence': max(0.0, min(1.0, confidence)),
            'evidence': [str(item).strip() for item in evidence if str(item).strip() != ''][:3],
            'summary': self._as_text(obj.get('summary'), response.strip()[:80]),
        }

    @staticmethod
    def _pick_category(text: str):
        if '唱歌' in text or '演唱' in text:
            return '唱歌中'
        if '视频' in text or '观看' in text or '播放' in text:
            return '观看视频中'
        return '游戏中'


class QwenJointReportHandler(QwenMultimodalBaseHandler):
    async def post(self):
        cfg = self._get_config_or_error()
        if cfg is None:
            return

        try:
            body = json.loads(self.request.body)
        except Exception:
            body = {}
            
        metrics = body.get('metrics', {})

        state = services.obs_bridge.get_state()
        frame = state.get('latestFrame') or {}
        image_url = self._compress_image_data_url(self._build_image_url(frame))

        split_audio = bool(state.get('splitAudioTracks'))
        mic_audio = state.get('latestMicAudio') or {} if split_audio else state.get('latestAudio') or {}
        mic_data = str(mic_audio.get('audioData', '') or '').strip()
        mic_format = str(mic_audio.get('audioFormat', '') or 'wav').strip().lower()
        
        desktop_audio = state.get('latestDesktopAudio') or {}
        desktop_data = str(desktop_audio.get('audioData', '') or '').strip()
        desktop_format = str(desktop_audio.get('audioFormat', '') or 'wav').strip().lower()

        distill_label = metrics.get('distillFocusLabel', '弹幕蒸馏')
        distill_hint = metrics.get('distillFocusPromptHint', '')

        prompt_text = (
            '任务目标：基于直播画面、主播语音、桌面音频与弹幕统计，做联合多模态分析。你可以通过其他模态的信息联合分析，比如通过弹幕信息来分析语音和画面，反之亦然。在多模态的三种输入里，画面的准确度最高，其次是弹幕文字，最后是语音。要求严格输出短 JSON，不要 markdown，不要长解释。\n'
            '\n'
            'JSON 顶层字段（三套报告 + 氛围统计）:\n'
            '  ## 氛围分析\n'
            '  stress, valence, fatigue, engagement, confidence: 0~1 数值\n'
            '  danmakuDistill: {type, label, text(<=40 字)}\n'
            '  liveEnvironment: {type(game/singing/video/unknown), label, confidence, evidence(<=3条)}\n'
            '  summary: 氛围分析结论，<=30 字\n'
            '  ## voiceReport (基于主播语音/桌面音频)\n'
            '  voiceReport: {\n'
            '    transcript: 主播说了什么的简短转写,\n'
            '    soundType: 主导声音类别（主播声/BGM/视频声/游戏声/混合）,\n'
            '    activity: 主播在做什么,\n'
            '    psychologicalState: 主播外显心理状态,\n'
            '    confidence: 0~1,\n'
            '    evidence: <=3 条,\n'
            '    summary: <=40 字\n'
            '  }\n'
            '  ## sceneReport (基于直播画面)\n'
            '  sceneReport: {\n'
            '    category: 只能是「游戏中」「唱歌中」「观看视频中」三选一,\n'
            '    confidence: 0~1,\n'
            '    evidence: <=3 条,\n'
            '    summary: <=40 字\n'
            '  }\n'
            f'本次 danmakuDistill 主题为「{distill_label}」：{distill_hint}。'
        )

        content_items = [
            {
                "type": "text",
                "text": prompt_text
            },
            {
                "type": "text",
                "text": f"弹幕/统计 JSON：{json.dumps(metrics, ensure_ascii=False)}"
            }
        ]

        if image_url:
            content_items.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url
                }
            })

        if mic_data:
            content_items.append({
                "type": "input_audio",
                "input_audio": {
                    "data": self._build_audio_input(mic_data, mic_format),
                    "format": mic_format
                }
            })

        if split_audio and desktop_data:
            content_items.append({
                "type": "input_audio",
                "input_audio": {
                    "data": self._build_audio_input(desktop_data, desktop_format),
                    "format": desktop_format
                }
            })

        payload = {
            "model": "gemma4-31b-mm",
            "temperature": 0.2,
            "max_tokens": 384,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [
                {
                    "role": "user",
                    "content": content_items
                }
            ]
        }

        try:
            import httpx
        except ImportError:
            self.write({'success': False, 'error': '服务端未安装 httpx 库'})
            return

        body_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        body_mb = len(body_bytes) / (1024 * 1024)
        image_kb = 0
        for item in content_items:
            if item.get('type') == 'image_url':
                image_kb = len(item.get('image_url', {}).get('url', '')) / 1024
                break
        audio_kb_list = [
            len(item.get('input_audio', {}).get('data', '')) / 1024
            for item in content_items if item.get('type') == 'input_audio'
        ]
        logger.info(
            'Qwen joint report sending: body=%.2fMB, image=%.1fKB, audio=%s',
            body_mb, image_kb,
            ','.join(f'{kb:.1f}KB' for kb in audio_kb_list) if audio_kb_list else 'none',
        )

        timing = {
            'started_at': time.perf_counter(),
            'request_sent_at': 0.0,
            'response_received_at': 0.0,
            'first_sse_at': 0.0,
            'first_token_at': 0.0,
            'response_received': False,
        }

        async def _on_request(_request):
            timing['request_sent_at'] = time.perf_counter()

        async def _on_response(_response):
            timing['response_received_at'] = time.perf_counter()
            timing['response_received'] = True
            upload_plus_first_byte = timing['response_received_at'] - timing['started_at']
            if upload_plus_first_byte > 20.0:
                logger.warning(
                    'Qwen joint report: upload + server-first-byte took %.2fs (body=%.2fMB) '
                    '— likely upload bottleneck via gateway',
                    upload_plus_first_byte, body_mb,
                )
            else:
                logger.info(
                    'Qwen joint report: response headers received in %.2fs (body=%.2fMB)',
                    upload_plus_first_byte, body_mb,
                )

        # 上传放宽到 120s（每次写阻塞），读放宽到 90s（首响应/token 间隔）。
        # 服务端有 keepalive 心跳，read 时钟会被持续刷新，不会变成端到端 90s 上限。
        timeout_cfg = httpx.Timeout(connect=10.0, read=90.0, write=120.0, pool=10.0)

        content_parts: List[str] = []
        usage_info: dict = {}
        raw_sse_lines = 0
        content_chunks = 0
        reasoning_chunks = 0
        raw_sse_samples: List[str] = []

        try:
            async with httpx.AsyncClient(
                timeout=timeout_cfg,
                event_hooks={'request': [_on_request], 'response': [_on_response]},
            ) as client:
                async with client.stream(
                    'POST',
                    f"{cfg.qwen_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {cfg.qwen_api_key}",
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream"
                    },
                    json=payload,
                ) as response:
                    if response.status_code == 413:
                        await response.aclose()
                        logger.warning(
                            'Qwen joint report: server returned 413 (body=%.2fMB exceeds budget)',
                            body_mb,
                        )
                        self.write({
                            'success': False,
                            'error': f'服务端返回 413：请求体 {body_mb:.2f}MB 超过预算，请缩短音频或降低截图分辨率。',
                            'errorCode': 'SERVER_413_PAYLOAD_TOO_LARGE',
                        })
                        return
                    if response.status_code != 200:
                        err_body = (await response.aread()).decode('utf-8', errors='ignore')
                        self.write({'success': False, 'error': f'服务端返回 {response.status_code}: {err_body[:300]}'})
                        return
                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line:
                            continue
                        raw_sse_lines += 1
                        if timing['first_sse_at'] == 0.0:
                            timing['first_sse_at'] = time.perf_counter()
                            logger.info(
                                'Qwen joint report: first SSE byte after %.2fs: %r',
                                timing['first_sse_at'] - timing['started_at'], line[:200],
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
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        chunk_usage = chunk.get('usage')
                        if chunk_usage:
                            usage_info = chunk_usage
                        choices = chunk.get('choices') or []
                        if not choices:
                            continue
                        delta = choices[0].get('delta') or {}
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
                        if isinstance(delta_reasoning, str) and delta_reasoning:
                            reasoning_chunks += 1
                        elif isinstance(delta_reasoning, list):
                            reasoning_text = ''
                            for item in delta_reasoning:
                                if isinstance(item, dict) and isinstance(item.get('text'), str):
                                    reasoning_text += item['text']
                            if reasoning_text:
                                reasoning_chunks += 1
                        if text_piece:
                            if timing['first_token_at'] == 0.0:
                                timing['first_token_at'] = time.perf_counter()
                                first_token_delay = timing['first_token_at'] - timing['response_received_at']
                                logger.info(
                                    'Qwen joint report: first token after %.2fs since headers',
                                    first_token_delay,
                                )
                            content_parts.append(text_piece)

            total_elapsed = time.perf_counter() - timing['started_at']
            logger.info(
                'Qwen joint report done: total=%.2fs, upload+first_byte=%.2fs, first_token_delay=%.2fs',
                total_elapsed,
                (timing['response_received_at'] - timing['started_at']) if timing['response_received'] else -1,
                (timing['first_token_at'] - timing['response_received_at']) if timing['first_token_at'] else -1,
            )

            content = ''.join(content_parts)
            report = self._extract_json_object(content) or {}
            logger.info(
                'Qwen joint report stream debug: body_size_mb=%.2f, http_status=200, '
                'first_sse_byte=%.2fs, first_text_chunk=%s, content_chunks=%d, '
                'reasoning_chunks=%d, raw_sse_lines=%d, raw_sse_samples=%s',
                body_mb,
                (timing['first_sse_at'] - timing['started_at']) if timing['first_sse_at'] else -1,
                (
                    f"{timing['first_token_at'] - timing['started_at']:.2f}s"
                    if timing['first_token_at'] else 'none'
                ),
                content_chunks,
                reasoning_chunks,
                raw_sse_lines,
                raw_sse_samples,
            )
            logger.info(
                'Qwen joint report raw model output len=%d:\n%s',
                len(content), content if content else '<EMPTY>',
            )
            if content == '':
                self.write({
                    'success': False,
                    'error': 'Qwen返回为空：HTTP 200 但未收到 delta.content 或 delta.reasoning 文本，请查看后端日志中的 raw_sse_samples。',
                    'errorCode': 'QWEN_EMPTY_RESPONSE',
                    'timing': {
                        'totalSeconds': round(total_elapsed, 2),
                        'uploadAndFirstByteSeconds': round(timing['response_received_at'] - timing['started_at'], 2) if timing['response_received'] else None,
                        'firstSseByteSeconds': round(timing['first_sse_at'] - timing['started_at'], 2) if timing['first_sse_at'] else None,
                        'bodyMB': round(body_mb, 2),
                        'contentChunks': content_chunks,
                        'reasoningChunks': reasoning_chunks,
                        'rawSseLines': raw_sse_lines,
                    },
                })
                return
            self.write({
                'success': True,
                'response': content,
                'report': report,
                'usage': usage_info,
                'timing': {
                    'totalSeconds': round(total_elapsed, 2),
                    'uploadAndFirstByteSeconds': round(timing['response_received_at'] - timing['started_at'], 2) if timing['response_received'] else None,
                    'firstSseByteSeconds': round(timing['first_sse_at'] - timing['started_at'], 2) if timing['first_sse_at'] else None,
                    'firstTokenDelaySeconds': round(timing['first_token_at'] - timing['response_received_at'], 2) if timing['first_token_at'] else None,
                    'bodyMB': round(body_mb, 2),
                    'contentChunks': content_chunks,
                    'reasoningChunks': reasoning_chunks,
                    'rawSseLines': raw_sse_lines,
                },
            })
        except asyncio.CancelledError:
            raise
        except (httpx.WriteTimeout, httpx.WriteError) as e:
            # 写超时/写错误 = 明确的客户端上传问题（请求体尚未发送完成）。
            elapsed = time.perf_counter() - timing['started_at']
            speed_mbs, speed_mbps = self._upload_speed(body_mb, elapsed)
            logger.warning(
                'Qwen joint report CLIENT-SIDE UPLOAD timeout/error (%s) after %.2fs: '
                'body=%.2fMB, avg upload speed≈%.2f MB/s (%.2f Mbps). '
                '问题定位：客户端上传链路（请求体未发送完成）。',
                type(e).__name__, elapsed, body_mb, speed_mbs, speed_mbps,
            )
            self.write({
                'success': False,
                'error': (
                    f'上传超时（客户端侧，body={body_mb:.2f}MB，已耗时 {elapsed:.1f}s，'
                    f'平均上传速度约 {speed_mbs:.2f} MB/s / {speed_mbps:.1f} Mbps）。请减小截图分辨率或改为 JPEG。'
                ),
                'errorCode': 'CLIENT_UPLOAD_TIMEOUT',
                'timing': {
                    'elapsedSeconds': round(elapsed, 2),
                    'bodyMB': round(body_mb, 2),
                    'uploadSpeedMBps': round(speed_mbs, 2),
                    'uploadSpeedMbps': round(speed_mbps, 2),
                    'responseHeadersReceived': False,
                },
            })
        except httpx.ReadTimeout:
            elapsed = time.perf_counter() - timing['started_at']
            timing_payload = {
                'elapsedSeconds': round(elapsed, 2),
                'bodyMB': round(body_mb, 2),
                'responseHeadersReceived': timing['response_received'],
            }
            if not timing['response_received']:
                # 还没收到响应头：上传 + 等首字节阶段超时。归类为客户端上传链路问题。
                phase = 'UPLOAD_OR_FIRST_BYTE'
                speed_mbs, speed_mbps = self._upload_speed(body_mb, elapsed)
                timing_payload['uploadSpeedMBps'] = round(speed_mbs, 2)
                timing_payload['uploadSpeedMbps'] = round(speed_mbps, 2)
                hint = (
                    f'上传请求体或等待服务端首字节超时（客户端侧，body={body_mb:.2f}MB，已耗时 {elapsed:.1f}s，'
                    f'平均上传速度约 {speed_mbs:.2f} MB/s / {speed_mbps:.1f} Mbps）。'
                    f'未收到任何响应头，大概率是上传链路慢/AutoDL 网关拥塞。建议减小截图/音频体积。'
                )
                logger.warning(
                    'Qwen joint report CLIENT-SIDE timeout in UPLOAD/wait-headers phase: '
                    'elapsed=%.2fs, body=%.2fMB, avg upload speed≈%.2f MB/s (%.2f Mbps), '
                    'response_headers_received=False. 问题定位：客户端上传链路。',
                    elapsed, body_mb, speed_mbs, speed_mbps,
                )
            else:
                # 响应头已到达：明确是服务端推理慢/token 间隔太长
                phase = 'SERVER_INFERENCE'
                upload_t = timing['response_received_at'] - timing['started_at']
                timing_payload['uploadAndFirstByteSeconds'] = round(upload_t, 2)
                hint = (
                    f'服务端响应头已到达（{upload_t:.1f}s），但后续 90s 内无新 token。'
                    f'这是服务端推理或 keepalive 中断的问题（问题定位：服务端），请联系服务端。'
                )
                logger.warning(
                    'Qwen joint report SERVER-SIDE timeout in inference phase: '
                    'upload+headers=%.2fs, total=%.2fs, body=%.2fMB. 问题定位：服务端。',
                    upload_t, elapsed, body_mb,
                )
            self.write({
                'success': False,
                'error': hint,
                'errorCode': f'TIMEOUT_{phase}',
                'timing': timing_payload,
            })
        except httpx.ConnectTimeout:
            logger.warning('Qwen joint report connect timeout')
            self.write({
                'success': False,
                'error': '与服务端建立连接超时，请检查 AutoDL 网关是否可达。',
                'errorCode': 'SERVER_CONNECT_TIMEOUT',
            })
        except httpx.ConnectError as e:
            # 连接都没建立起来：客户端到网关链路问题。
            elapsed = time.perf_counter() - timing['started_at']
            logger.warning(
                'Qwen joint report CLIENT-SIDE connect error (%s) after %.2fs: %s. '
                '问题定位：客户端→网关链路（连接未建立）。',
                type(e).__name__, elapsed, e,
            )
            self.write({
                'success': False,
                'error': '与服务端建立连接失败（客户端侧），请检查本地网络与 AutoDL 网关是否可达。',
                'errorCode': 'CLIENT_CONNECT_ERROR',
            })
        except (httpx.NetworkError, httpx.RemoteProtocolError) as e:
            # 连接在传输途中被断开（如 ReadError / RemoteProtocolError）。
            # 用「是否已收到响应头」来定位问题方向：
            #   - 未收到响应头 → 上传/等首字节阶段断开 → 客户端上传链路问题（附上传网速）
            #   - 已收到响应头 → 读取流式响应时断开 → 服务端/网关问题
            elapsed = time.perf_counter() - timing['started_at']
            if not timing['response_received']:
                speed_mbs, speed_mbps = self._upload_speed(body_mb, elapsed)
                logger.warning(
                    'Qwen joint report CLIENT-SIDE upload failure (%s): connection dropped '
                    'before response headers. body=%.2fMB, elapsed=%.2fs, '
                    'avg upload speed≈%.2f MB/s (%.2f Mbps). 问题定位：客户端上传链路被中断。',
                    type(e).__name__, body_mb, elapsed, speed_mbs, speed_mbps,
                )
                self.write({
                    'success': False,
                    'error': (
                        f'上传链路中断（客户端侧）：请求体 {body_mb:.2f}MB 在收到服务端响应前连接被断开，'
                        f'已耗时 {elapsed:.1f}s，平均上传速度约 {speed_mbs:.2f} MB/s / {speed_mbps:.1f} Mbps。'
                        f'大概率是客户端→AutoDL 网关上传慢/不稳定，建议减小截图分辨率或缩短音频。'
                    ),
                    'errorCode': 'CLIENT_UPLOAD_CONNECTION_DROPPED',
                    'timing': {
                        'elapsedSeconds': round(elapsed, 2),
                        'bodyMB': round(body_mb, 2),
                        'uploadSpeedMBps': round(speed_mbs, 2),
                        'uploadSpeedMbps': round(speed_mbps, 2),
                        'responseHeadersReceived': False,
                    },
                })
            else:
                upload_t = timing['response_received_at'] - timing['started_at']
                speed_mbs, speed_mbps = self._upload_speed(body_mb, upload_t)
                logger.warning(
                    'Qwen joint report SERVER-SIDE failure (%s): connection dropped while '
                    'reading stream. upload+headers=%.2fs (upload speed≈%.2f MB/s, %.2f Mbps), '
                    'total=%.2fs, body=%.2fMB. 问题定位：服务端/网关（响应途中断流）。',
                    type(e).__name__, upload_t, speed_mbs, speed_mbps, elapsed, body_mb,
                )
                self.write({
                    'success': False,
                    'error': (
                        f'服务端连接中断（服务端侧）：上传已完成（{upload_t:.1f}s）并已开始接收响应，'
                        f'但在读取过程中连接被断开。多为服务端推理崩溃 / worker 被杀 / 网关掐断长连接，请检查或重启服务端。'
                    ),
                    'errorCode': 'SERVER_CONNECTION_DROPPED',
                    'timing': {
                        'elapsedSeconds': round(elapsed, 2),
                        'uploadAndFirstByteSeconds': round(upload_t, 2),
                        'uploadSpeedMBps': round(speed_mbs, 2),
                        'uploadSpeedMbps': round(speed_mbps, 2),
                        'bodyMB': round(body_mb, 2),
                        'responseHeadersReceived': True,
                    },
                })
        except Exception as e:
            logger.exception('Qwen joint report failed:')
            self.write({'success': False, 'error': str(e)})

    @staticmethod
    def _upload_speed(body_mb: float, seconds: float):
        """根据请求体大小与耗时估算上传速度，返回 (MB/s, Mbps)。

        注意：当未收到响应头时，seconds 包含「上传 + 等首字节」，得到的是平均速度下限；
        当已收到响应头时，传入 upload+headers 时长，更接近真实上传速度。
        """
        if seconds <= 0:
            return 0.0, 0.0
        mbs = body_mb / seconds
        return mbs, mbs * 8

    def _build_image_url(self, frame: dict):
        image_data = str(frame.get('imageData', '') or '').strip()
        if image_data.startswith('data:image/'):
            return image_data
        if image_data != '':
            image_format = str(frame.get('imageFormat', '') or 'jpeg').strip().lower()
            if image_format == 'jpg':
                image_format = 'jpeg'
            return f'data:image/{image_format};base64,{image_data}'
        image_path = str(frame.get('imageFilePath', '') or '').strip()
        if image_path == '' or not os.path.isfile(image_path):
            return ''
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type is None or not mime_type.startswith('image/'):
            mime_type = 'image/jpeg'
        with open(image_path, 'rb') as image_file:
            encoded = base64.b64encode(image_file.read()).decode('ascii')
        return f'data:{mime_type};base64,{encoded}'

    @staticmethod
    def _build_audio_input(audio_data: str, audio_format: str):
        if audio_data.startswith('data:audio/'):
            return audio_data
        if audio_data.startswith('data:') and ',' in audio_data:
            return f'data:audio/{audio_format};base64,{audio_data.split(",", 1)[1]}'
        return f'data:audio/{audio_format};base64,{audio_data}'

ROUTES = [
    (r'/api/qwen/asr-report', QwenAsrReportHandler),
    (r'/api/qwen/vision-report', QwenVisionReportHandler),
    (r'/api/qwen/joint-report', QwenJointReportHandler),
]
