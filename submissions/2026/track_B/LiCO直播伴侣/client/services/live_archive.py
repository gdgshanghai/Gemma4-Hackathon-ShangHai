# -*- coding: utf-8 -*-
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from typing import *

import config

logger = logging.getLogger(__name__)

_service: Optional['LiveArchiveService'] = None
_ffmpeg_tool_cache: Dict[str, Optional[str]] = {}

CATEGORY_FILES = {
    'mental': 'mental.txt',
    'voice': 'voice.txt',
    'picture': 'picture.txt',
    'gift': 'gift.txt',
    'live_info': 'live_info.txt',
}

COVER_FILENAME = 'cover.jpg'
SUMMARY_FILENAME = 'summary.txt'
SEGMENT_SUMMARY_VERSION = 2
CLIP_DURATION_DEFAULT = 120
CLIP_DURATION_MIN = 15
CLIP_DURATION_MAX = 1800
CLIP_TYPE_DANMAKU = 'danmaku'
CLIP_TYPE_GIFT = 'gift'
STREAM_FOLDER_PATTERN = re.compile(r'^\d{8}_\d{6}$')
LIVE_INFO_START_RE = re.compile(r'【开始直播】(.+)')
LIVE_INFO_STOP_RE = re.compile(r'【停止直播】(.+)')
LIVE_INFO_SUMMARY_RE = re.compile(
    r'您已直播(.+?)，收到礼物价值([\d.]+)\s*元，录播文件保存到了(.+?)，辛苦了'
)
MENTAL_DANMAKU_RE = re.compile(r'弹幕:\s*(\d+)条')
MENTAL_TIMELINE_RE = re.compile(r'直播时长:\s*(.+?)\s*\|\s*弹幕:\s*(\d+)条')
ARCHIVE_LINE_DURATION_RE = re.compile(r'直播时长:\s*(.+?)\s*\|')
MENTAL_LINE_MARKER = '【心理分析】'
VOICE_LINE_MARKER = '【语音观察】'
PICTURE_LINE_MARKER = '【画面场景】'
PICTURE_CONCLUSION_RE = re.compile(r'结论:\s*(.+?)\s*$')
ARCHIVE_CONCLUSION_RE = re.compile(r'结论:\s*(.+?)\s*$')
SEGMENT_EXCERPT_LIMIT = 12
GIFT_LIVE_DURATION_RE = re.compile(r'直播时长:\s*(.+?)(?:\s*\||\s*$)')
GIFT_AMOUNT_RE = re.compile(r'金额:\s*([\d.]+)\s*元')
CHINESE_DURATION_RE = re.compile(r'(?:(\d+)小时)?(?:(\d+)分)?(?:(\d+)秒)?')
PICTURE_SCENE_LINE_RE = re.compile(
    r'【画面场景】(?:直播时长:\s*(.+?)\s*\|\s*)?场景:\s*(.+?)\s*\|'
)
SCENE_VOTE_WINDOW_SIZE = 3
SCENE_DEFINITIONS = {
    'gaming': {
        'sceneText': '游戏中',
        'color': '#ef4444',
    },
    'singing': {
        'sceneText': '唱歌中',
        'color': '#3b82f6',
    },
    'watching': {
        'sceneText': '观看视频中',
        'color': '#eab308',
    },
}
SCENE_TEXT_TO_KEY = {
    definition['sceneText']: scene_key
    for scene_key, definition in SCENE_DEFINITIONS.items()
}
VALID_LIVE_CONTENT_TYPES = frozenset(SCENE_DEFINITIONS.keys())


def _windows_path_from_registry() -> str:
    if sys.platform != 'win32':
        return ''
    try:
        import winreg
        parts = []
        for root, subkey in (
            (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
            (winreg.HKEY_CURRENT_USER, 'Environment'),
        ):
            with winreg.OpenKey(root, subkey) as key:
                parts.append(str(winreg.QueryValueEx(key, 'Path')[0]))
        return os.pathsep.join(parts)
    except OSError:
        return ''


def _resolve_ffmpeg_tool(tool_name: str) -> Optional[str]:
    cached = _ffmpeg_tool_cache.get(tool_name)
    if cached is not None:
        return cached or None

    executable = f'{tool_name}.exe' if sys.platform == 'win32' else tool_name
    search_dirs = []
    for path_text in (
        os.environ.get('PATH', ''),
        _windows_path_from_registry(),
    ):
        for directory in str(path_text or '').split(os.pathsep):
            directory = directory.strip()
            if directory != '':
                search_dirs.append(directory)

    local_app_data = os.environ.get('LOCALAPPDATA', '')
    if local_app_data != '':
        search_dirs.append(os.path.join(local_app_data, 'Microsoft', 'WinGet', 'Links'))

    resolved = None
    for directory in search_dirs:
        candidate = os.path.join(directory, executable)
        if os.path.isfile(candidate):
            resolved = candidate
            break

    if resolved is None:
        resolved = shutil.which(tool_name)

    _ffmpeg_tool_cache[tool_name] = resolved or ''
    if resolved:
        logger.info('resolved ffmpeg tool %s=%s', tool_name, resolved)
    else:
        logger.warning('ffmpeg tool not found: %s', tool_name)
    return resolved


def _decode_process_output(raw: Optional[bytes]) -> str:
    if not raw:
        return ''
    return raw.decode('utf-8', errors='replace').strip()


def _run_media_command(command: List[str]) -> Tuple[int, str, str]:
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
    )
    stdout = _decode_process_output(result.stdout)
    stderr = _decode_process_output(result.stderr)
    return result.returncode, stdout, stderr


def init():
    global _service
    _service = LiveArchiveService()


def ensure_session(room_id: str, stream_started_at: int):
    if _service is None:
        return {}
    return _service.ensure_session(room_id, stream_started_at)


def append_record(room_id: str, stream_started_at: int, category: str, content: str):
    if _service is None:
        return {}
    return _service.append_record(room_id, stream_started_at, category, content)


def list_sessions(room_id: str, limit: int = 10, generate_covers: bool = True):
    if _service is None:
        return []
    return _service.list_sessions(room_id, limit, generate_covers)


def ensure_cover(room_id: str, stream_folder: str):
    if _service is None:
        return None
    return _service.ensure_cover(room_id, stream_folder)


def get_cover_path(room_id: str, stream_folder: str):
    if _service is None:
        return None
    return _service.get_cover_path(room_id, stream_folder)


def get_session(room_id: str, stream_folder: str, generate_cover: bool = False):
    if _service is None:
        return None
    return _service.get_session(room_id, stream_folder, generate_cover)


def get_clip_timeline(room_id: str, stream_folder: str):
    if _service is None:
        return None
    return _service.get_clip_timeline(room_id, stream_folder)


def get_scene_timeline(room_id: str, stream_folder: str):
    if _service is None:
        return None
    return _service.get_scene_timeline(room_id, stream_folder)


def save_segment_summaries(room_id: str, stream_folder: str, segments):
    if _service is None:
        return {}
    return _service.save_segment_summaries(room_id, stream_folder, segments)


def suggest_clip(room_id: str, stream_folder: str, clip_type: str, clip_duration_seconds: int):
    if _service is None:
        return None
    return _service.suggest_clip(room_id, stream_folder, clip_type, clip_duration_seconds)


def export_clip(room_id: str, stream_folder: str, clip_type: str, start_seconds: int, end_seconds: int):
    if _service is None:
        return None
    return _service.export_clip(room_id, stream_folder, clip_type, start_seconds, end_seconds)


class LiveArchiveService:
    def __init__(self):
        self._base_path = config.DATA_PATH

    @staticmethod
    def _sanitize_segment(value: str) -> str:
        text = str(value or '').strip()
        if text == '':
            return 'unknown'
        return re.sub(r'[^\w.-]', '_', text)

    @staticmethod
    def _stream_start_folder(stream_started_at: int) -> str:
        started_at = int(stream_started_at or 0)
        if started_at <= 0:
            return 'unknown_stream'
        return datetime.fromtimestamp(started_at).strftime('%Y%m%d_%H%M%S')

    def get_session_dir(self, room_id: str, stream_started_at: int) -> str:
        room_segment = self._sanitize_segment(room_id)
        stream_segment = self._stream_start_folder(stream_started_at)
        return os.path.join(self._base_path, room_segment, stream_segment)

    def ensure_session(self, room_id: str, stream_started_at: int):
        started_at = int(stream_started_at or 0)
        if started_at <= 0:
            raise ValueError('streamStartedAt is required')

        session_dir = self.get_session_dir(room_id, started_at)
        os.makedirs(session_dir, exist_ok=True)
        created_files = []
        for filename in CATEGORY_FILES.values():
            file_path = os.path.join(session_dir, filename)
            if not os.path.exists(file_path):
                with open(file_path, 'a', encoding='utf-8'):
                    pass
                created_files.append(filename)
        logger.info(
            'live archive session ready room_id=%s stream_started_at=%s dir=%s',
            room_id,
            started_at,
            session_dir,
        )
        return {
            'roomId': self._sanitize_segment(room_id),
            'streamStartedAt': started_at,
            'streamStartFolder': self._stream_start_folder(started_at),
            'sessionDir': session_dir,
            'createdFiles': created_files,
        }

    def append_record(self, room_id: str, stream_started_at: int, category: str, content: str):
        category_key = str(category or '').strip().lower()
        if category_key not in CATEGORY_FILES:
            raise ValueError(f'unsupported category: {category}')

        text = str(content or '').strip()
        if text == '':
            raise ValueError('content is empty')

        session_info = self.ensure_session(room_id, stream_started_at)
        file_path = os.path.join(session_info['sessionDir'], CATEGORY_FILES[category_key])
        with open(file_path, 'a', encoding='utf-8') as file:
            file.write(text)
            if not text.endswith('\n'):
                file.write('\n')

        return {
            **session_info,
            'category': category_key,
            'fileName': CATEGORY_FILES[category_key],
            'filePath': file_path,
        }

    def get_room_dir(self, room_id: str) -> str:
        return os.path.join(self._base_path, self._sanitize_segment(room_id))

    def get_session_dir_by_folder(self, room_id: str, stream_folder: str) -> str:
        folder = str(stream_folder or '').strip()
        if not STREAM_FOLDER_PATTERN.match(folder):
            raise ValueError('invalid stream folder')
        return os.path.join(self.get_room_dir(room_id), folder)

    @staticmethod
    def _read_text_file(file_path: str) -> str:
        if not os.path.isfile(file_path):
            return ''
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()

    @staticmethod
    def _parse_live_info(content: str):
        start_time = ''
        end_time = ''
        duration_text = ''
        gift_value = 0.0
        recording_file_path = ''
        for line in str(content or '').splitlines():
            text = line.strip()
            if text == '':
                continue
            start_match = LIVE_INFO_START_RE.search(text)
            if start_match:
                start_time = start_match.group(1).strip()
                continue
            stop_match = LIVE_INFO_STOP_RE.search(text)
            if stop_match:
                end_time = stop_match.group(1).strip()
                continue
            summary_match = LIVE_INFO_SUMMARY_RE.search(text)
            if summary_match:
                duration_text = summary_match.group(1).strip()
                try:
                    gift_value = float(summary_match.group(2))
                except ValueError:
                    gift_value = 0.0
                recording_file_path = summary_match.group(3).strip()
        return {
            'startTime': start_time,
            'endTime': end_time,
            'durationText': duration_text,
            'giftValue': gift_value,
            'recordingFilePath': recording_file_path,
        }

    @staticmethod
    def _count_danmaku_from_mental(content: str) -> int:
        max_count = 0
        for match in MENTAL_DANMAKU_RE.finditer(str(content or '')):
            try:
                max_count = max(max_count, int(match.group(1)))
            except ValueError:
                continue
        return max_count

    @staticmethod
    def _parse_chinese_duration(text: str) -> int:
        match = CHINESE_DURATION_RE.fullmatch(str(text or '').strip())
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _parse_timed_archive_lines(content: str, marker: str):
        records = []
        marker_text = str(marker or '').strip()
        for line in str(content or '').splitlines():
            text = line.strip()
            if text == '' or marker_text not in text:
                continue
            match = ARCHIVE_LINE_DURATION_RE.search(text)
            if not match:
                continue
            time_seconds = LiveArchiveService._parse_chinese_duration(match.group(1))
            records.append({
                'timeSeconds': time_seconds,
                'text': text,
            })
        records.sort(key=lambda item: item['timeSeconds'])
        return records

    @staticmethod
    def _filter_timed_records_for_segment(records, start_seconds: int, end_seconds: int):
        start = int(start_seconds or 0)
        end = int(end_seconds or 0)
        if end <= start:
            return []
        return [
            str(item.get('text') or '').strip()
            for item in (records or [])
            if start <= int(item.get('timeSeconds') or 0) < end
        ]

    @staticmethod
    def _parse_picture_conclusion_records(content: str):
        records = []
        for line in str(content or '').splitlines():
            text = line.strip()
            if PICTURE_LINE_MARKER not in text:
                continue
            duration_match = ARCHIVE_LINE_DURATION_RE.search(text)
            conclusion_match = PICTURE_CONCLUSION_RE.search(text)
            if not duration_match or not conclusion_match:
                continue
            conclusion = str(conclusion_match.group(1) or '').strip()
            if conclusion == '':
                continue
            records.append({
                'timeSeconds': LiveArchiveService._parse_chinese_duration(duration_match.group(1)),
                'text': conclusion,
                'conclusion': conclusion,
            })
        records.sort(key=lambda item: item['timeSeconds'])
        return records

    @staticmethod
    def _distill_archive_excerpt(text: str) -> str:
        line = str(text or '').strip()
        if line == '':
            return ''
        conclusion_match = ARCHIVE_CONCLUSION_RE.search(line)
        if conclusion_match:
            return str(conclusion_match.group(1) or '').strip()
        return line

    @staticmethod
    def _limit_segment_excerpts(items, max_items: int = SEGMENT_EXCERPT_LIMIT):
        excerpts = [str(item or '').strip() for item in (items or []) if str(item or '').strip() != '']
        if len(excerpts) <= max_items:
            return excerpts
        if max_items <= 1:
            return excerpts[-max_items:]
        last_index = len(excerpts) - 1
        picked = []
        for index in range(max_items):
            sample_index = int(round(index * last_index / (max_items - 1)))
            excerpt = excerpts[sample_index]
            if excerpt not in picked:
                picked.append(excerpt)
        return picked

    @staticmethod
    def _prepare_segment_excerpts(items):
        distilled = [
            LiveArchiveService._distill_archive_excerpt(item)
            for item in (items or [])
        ]
        distilled = [item for item in distilled if item != '']
        return LiveArchiveService._limit_segment_excerpts(distilled)

    @staticmethod
    def _filter_picture_conclusions_for_segment(records, start_seconds: int, end_seconds: int):
        start = int(start_seconds or 0)
        end = int(end_seconds or 0)
        if end <= start:
            return []
        conclusions = []
        for item in (records or []):
            time_seconds = int(item.get('timeSeconds') or 0)
            if start <= time_seconds < end:
                conclusion = str(item.get('conclusion') or item.get('text') or '').strip()
                if conclusion != '':
                    conclusions.append(conclusion)
        return conclusions

    @staticmethod
    def _parse_mental_timeline(content: str):
        points = []
        for line in str(content or '').splitlines():
            match = MENTAL_TIMELINE_RE.search(line)
            if not match:
                continue
            time_seconds = LiveArchiveService._parse_chinese_duration(match.group(1))
            try:
                count = int(match.group(2))
            except ValueError:
                continue
            points.append({'timeSeconds': time_seconds, 'count': count})
        points.sort(key=lambda item: item['timeSeconds'])
        return points

    @staticmethod
    def _parse_gift_timeline(content: str):
        amount_by_time = {}
        for line in str(content or '').splitlines():
            text = line.strip()
            if text == '':
                continue
            duration_match = GIFT_LIVE_DURATION_RE.search(text)
            amount_match = GIFT_AMOUNT_RE.search(text)
            if not duration_match or not amount_match:
                continue
            time_seconds = LiveArchiveService._parse_chinese_duration(duration_match.group(1))
            try:
                amount = float(amount_match.group(1))
            except ValueError:
                continue
            amount_by_time[time_seconds] = amount_by_time.get(time_seconds, 0.0) + amount
        points = [
            {'timeSeconds': time_seconds, 'amount': round(amount, 2)}
            for time_seconds, amount in sorted(amount_by_time.items())
        ]
        return points

    @staticmethod
    def _folder_started_at(stream_folder: str) -> int:
        try:
            return int(datetime.strptime(stream_folder, '%Y%m%d_%H%M%S').timestamp())
        except ValueError:
            return 0

    def _build_session_summary(self, room_id: str, stream_folder: str):
        session_dir = self.get_session_dir_by_folder(room_id, stream_folder)
        live_info_path = os.path.join(session_dir, CATEGORY_FILES['live_info'])
        if not os.path.isfile(live_info_path):
            return None

        live_info = self._parse_live_info(self._read_text_file(live_info_path))
        mental_path = os.path.join(session_dir, CATEGORY_FILES['mental'])
        danmaku_count = self._count_danmaku_from_mental(self._read_text_file(mental_path))
        cover_path = os.path.join(session_dir, COVER_FILENAME)
        room_segment = self._sanitize_segment(room_id)

        return {
            'roomId': room_segment,
            'streamStartFolder': stream_folder,
            'streamStartedAt': self._folder_started_at(stream_folder),
            'startTime': live_info['startTime'],
            'endTime': live_info['endTime'],
            'durationText': live_info['durationText'],
            'giftValue': live_info['giftValue'],
            'giftValueText': f"{live_info['giftValue']:.2f} 元",
            'danmakuCount': danmaku_count,
            'recordingFilePath': live_info['recordingFilePath'],
            'hasCover': os.path.isfile(cover_path),
            'canGenerateCover': bool(str(live_info.get('recordingFilePath') or '').strip()),
            'coverUrl': f'/api/live/archive/cover/{room_segment}/{stream_folder}',
        }

    def list_sessions(self, room_id: str, limit: int = 10, generate_covers: bool = True):
        room_dir = self.get_room_dir(room_id)
        if not os.path.isdir(room_dir):
            return []

        folders = []
        for name in os.listdir(room_dir):
            full_path = os.path.join(room_dir, name)
            if not os.path.isdir(full_path):
                continue
            if not STREAM_FOLDER_PATTERN.match(name):
                continue
            folders.append(name)
        folders.sort(reverse=True)

        sessions = []
        for stream_folder in folders:
            summary = self._build_session_summary(room_id, stream_folder)
            if summary is None:
                continue
            if generate_covers and not summary['hasCover']:
                self.ensure_cover(room_id, stream_folder)
                summary['hasCover'] = os.path.isfile(
                    os.path.join(self.get_session_dir_by_folder(room_id, stream_folder), COVER_FILENAME)
                )
            sessions.append(summary)
            if len(sessions) >= max(1, int(limit or 10)):
                break
        return sessions

    def get_session(self, room_id: str, stream_folder: str, generate_cover: bool = False):
        summary = self._build_session_summary(room_id, stream_folder)
        if summary is None:
            return None
        if generate_cover and not summary['hasCover']:
            self.ensure_cover(room_id, stream_folder)
            summary['hasCover'] = os.path.isfile(
                os.path.join(self.get_session_dir_by_folder(room_id, stream_folder), COVER_FILENAME)
            )
        return summary

    def get_clip_timeline(self, room_id: str, stream_folder: str):
        session_dir = self.get_session_dir_by_folder(room_id, stream_folder)
        live_info_path = os.path.join(session_dir, CATEGORY_FILES['live_info'])
        if not os.path.isfile(live_info_path):
            return None

        live_info = self._parse_live_info(self._read_text_file(live_info_path))
        duration_seconds = self._parse_chinese_duration(live_info.get('durationText') or '')
        mental_path = os.path.join(session_dir, CATEGORY_FILES['mental'])
        gift_path = os.path.join(session_dir, CATEGORY_FILES['gift'])
        danmaku_timeline = self._parse_mental_timeline(self._read_text_file(mental_path))
        gift_timeline = self._parse_gift_timeline(self._read_text_file(gift_path))

        if duration_seconds <= 0:
            max_time = 0
            for point in danmaku_timeline + gift_timeline:
                max_time = max(max_time, int(point.get('timeSeconds') or 0))
            duration_seconds = max_time

        return {
            'durationSeconds': duration_seconds,
            'durationText': live_info.get('durationText') or '',
            'recordingFilePath': str(live_info.get('recordingFilePath') or '').strip(),
            'hasRecording': os.path.isfile(str(live_info.get('recordingFilePath') or '').strip()),
            'danmakuTimeline': danmaku_timeline,
            'giftTimeline': gift_timeline,
        }

    @staticmethod
    def _normalize_scene_key(scene_text: str) -> str:
        text = str(scene_text or '').strip()
        if text in SCENE_TEXT_TO_KEY:
            return SCENE_TEXT_TO_KEY[text]
        for scene_text_key, scene_key in SCENE_TEXT_TO_KEY.items():
            if scene_text_key in text:
                return scene_key
        return ''

    @staticmethod
    def _parse_picture_samples(content: str, total_duration: int):
        samples = []
        for line in str(content or '').splitlines():
            match = PICTURE_SCENE_LINE_RE.search(line.strip())
            if not match:
                continue
            duration_text = str(match.group(1) or '').strip()
            scene_text = str(match.group(2) or '').strip()
            scene_key = LiveArchiveService._normalize_scene_key(scene_text)
            if scene_key == '':
                continue
            time_seconds = LiveArchiveService._parse_chinese_duration(duration_text) if duration_text else None
            samples.append({
                'timeSeconds': time_seconds,
                'sceneKey': scene_key,
                'sceneText': scene_text,
            })

        if not samples:
            return []

        if all(sample.get('timeSeconds') is None for sample in samples):
            last_index = max(len(samples) - 1, 1)
            safe_duration = max(total_duration, 1)
            for index, sample in enumerate(samples):
                sample['timeSeconds'] = int(safe_duration * index / last_index)
        else:
            last_known_time = 0
            for sample in samples:
                if sample.get('timeSeconds') is None:
                    sample['timeSeconds'] = last_known_time
                else:
                    last_known_time = int(sample['timeSeconds'])

        samples.sort(key=lambda item: int(item.get('timeSeconds') or 0))
        return samples

    @staticmethod
    def _majority_scene_key(window):
        counts = Counter()
        ordered_keys = []
        for sample in window or []:
            scene_key = str(sample.get('sceneKey') or '').strip()
            if scene_key == '':
                continue
            counts[scene_key] += 1
            if scene_key not in ordered_keys:
                ordered_keys.append(scene_key)
        if not counts:
            return ''
        max_count = max(counts.values())
        candidates = [scene_key for scene_key in ordered_keys if counts[scene_key] == max_count]
        return candidates[0]

    @staticmethod
    def _build_scene_segments(samples, total_duration: int):
        if not samples:
            return []

        voted_points = []
        for index in range(len(samples)):
            window = samples[index:index + SCENE_VOTE_WINDOW_SIZE]
            scene_key = LiveArchiveService._majority_scene_key(window)
            if scene_key == '':
                continue
            voted_points.append({
                'timeSeconds': int(samples[index].get('timeSeconds') or 0),
                'sceneKey': scene_key,
                'sceneText': SCENE_DEFINITIONS[scene_key]['sceneText'],
            })

        if not voted_points:
            return []

        merged = []
        for point in voted_points:
            if merged and merged[-1]['sceneKey'] == point['sceneKey']:
                merged[-1]['endSeconds'] = point['timeSeconds']
                continue
            merged.append({
                'sceneKey': point['sceneKey'],
                'sceneText': point['sceneText'],
                'startSeconds': point['timeSeconds'],
                'endSeconds': point['timeSeconds'],
            })

        safe_duration = max(int(total_duration or 0), merged[-1]['endSeconds'], 1)
        merged[0]['startSeconds'] = 0
        for index in range(len(merged) - 1):
            current = merged[index]
            next_item = merged[index + 1]
            boundary = int((current['endSeconds'] + next_item['startSeconds']) / 2)
            boundary = max(current['startSeconds'], min(boundary, next_item['startSeconds']))
            current['endSeconds'] = boundary
            next_item['startSeconds'] = boundary
        merged[-1]['endSeconds'] = safe_duration

        segments = []
        for item in merged:
            scene_key = item['sceneKey']
            definition = SCENE_DEFINITIONS.get(scene_key, {})
            start_seconds = int(item['startSeconds'])
            end_seconds = int(item['endSeconds'])
            if end_seconds <= start_seconds:
                continue
            segments.append({
                'sceneKey': scene_key,
                'sceneText': definition.get('sceneText') or item['sceneText'],
                'color': definition.get('color') or '#94a3b8',
                'startSeconds': start_seconds,
                'endSeconds': end_seconds,
                'startText': LiveArchiveService._format_chinese_duration(start_seconds),
                'endText': LiveArchiveService._format_chinese_duration(end_seconds),
                'durationSeconds': end_seconds - start_seconds,
                'durationText': LiveArchiveService._format_chinese_duration(end_seconds - start_seconds),
            })
        return segments

    @staticmethod
    def _segment_signature(segment: dict) -> str:
        return '|'.join([
            str(segment.get('sceneKey') or '').strip(),
            str(int(segment.get('startSeconds') or 0)),
            str(int(segment.get('endSeconds') or 0)),
        ])

    @staticmethod
    def _build_segment_signatures(segments) -> List[str]:
        return [LiveArchiveService._segment_signature(segment) for segment in (segments or [])]

    def _summary_file_path(self, session_dir: str) -> str:
        return os.path.join(session_dir, SUMMARY_FILENAME)

    @staticmethod
    def _resolve_scene_text(segment: dict) -> str:
        scene_text = str(segment.get('sceneText') or '').strip()
        if scene_text != '':
            return scene_text
        scene_key = str(segment.get('sceneKey') or '').strip()
        definition = SCENE_DEFINITIONS.get(scene_key, {})
        return str(definition.get('sceneText') or '').strip()

    @staticmethod
    def _normalize_live_content_type(segment: dict) -> str:
        scene_key = str(segment.get('sceneKey') or segment.get('liveContentType') or '').strip()
        if scene_key in VALID_LIVE_CONTENT_TYPES:
            return scene_key
        scene_text = LiveArchiveService._resolve_scene_text(segment)
        for key, definition in SCENE_DEFINITIONS.items():
            if definition.get('sceneText') == scene_text:
                return key
        return ''

    def _load_segment_summaries_map(self, session_dir: str, segments) -> Dict[int, dict]:
        summary_path = self._summary_file_path(session_dir)
        if not os.path.isfile(summary_path):
            return {}

        try:
            with open(summary_path, 'r', encoding='utf-8') as file:
                payload = json.load(file)
        except (OSError, ValueError, TypeError) as e:
            logger.warning('failed to read segment summaries %s: %s', summary_path, e)
            return {}

        if not isinstance(payload, dict):
            return {}
        if int(payload.get('version') or 0) != SEGMENT_SUMMARY_VERSION:
            return {}

        current_signatures = self._build_segment_signatures(segments)
        stored_signatures = payload.get('segmentSignatures') or []
        if stored_signatures != current_signatures:
            return {}

        summaries_map = {}
        for item in payload.get('segments') or []:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get('segmentIndex'))
            except (TypeError, ValueError):
                continue
            scene_key = self._normalize_live_content_type(item)
            scene_text = self._resolve_scene_text(item)
            audience_interest = str(item.get('audienceInterest') or '').strip()
            streamer_summary = str(item.get('streamerSummary') or '').strip()
            if scene_key == '' or (audience_interest == '' and streamer_summary == ''):
                continue
            summaries_map[index] = {
                'liveContentType': scene_key,
                'sceneKey': scene_key,
                'sceneText': scene_text,
                'audienceInterest': audience_interest,
                'streamerSummary': streamer_summary,
            }
        return summaries_map

    def save_segment_summaries(self, room_id: str, stream_folder: str, segments):
        session_dir = self.get_session_dir_by_folder(room_id, stream_folder)
        if not os.path.isdir(session_dir):
            raise ValueError('session not found')

        normalized_segments = []
        for index, segment in enumerate(segments or []):
            if not isinstance(segment, dict):
                continue
            scene_key = self._normalize_live_content_type(segment)
            scene_text = self._resolve_scene_text(segment)
            audience_interest = str(segment.get('audienceInterest') or '').strip()
            streamer_summary = str(segment.get('streamerSummary') or '').strip()
            if scene_key == '' or (audience_interest == '' and streamer_summary == ''):
                continue
            start_seconds = int(segment.get('startSeconds') or 0)
            end_seconds = int(segment.get('endSeconds') or 0)
            normalized = {
                'liveContentType': scene_key,
                'sceneKey': scene_key,
                'sceneText': scene_text,
                'startSeconds': start_seconds,
                'endSeconds': end_seconds,
                'startText': str(segment.get('startText') or '').strip()
                or self._format_chinese_duration(start_seconds),
                'endText': str(segment.get('endText') or '').strip()
                or self._format_chinese_duration(end_seconds),
                'durationText': str(segment.get('durationText') or '').strip()
                or self._format_chinese_duration(max(end_seconds - start_seconds, 0)),
                'audienceInterest': audience_interest,
                'streamerSummary': streamer_summary,
            }
            normalized_segments.append({
                'segmentIndex': index,
                'signature': self._segment_signature(normalized),
                **normalized,
            })

        payload = {
            'version': SEGMENT_SUMMARY_VERSION,
            'description': '直播复盘分时段总结：每段含直播内容类型(三选一)、观众兴趣、主播与内容',
            'liveContentOptions': [
                {
                    'liveContentType': scene_key,
                    'sceneKey': scene_key,
                    'sceneText': definition['sceneText'],
                }
                for scene_key, definition in SCENE_DEFINITIONS.items()
            ],
            'updatedAt': datetime.now().isoformat(timespec='seconds'),
            'segmentSignatures': self._build_segment_signatures(normalized_segments),
            'segments': normalized_segments,
        }
        summary_path = self._summary_file_path(session_dir)
        with open(summary_path, 'w', encoding='utf-8') as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write('\n')

        logger.info(
            'segment summaries saved room_id=%s stream_folder=%s count=%s path=%s',
            room_id,
            stream_folder,
            len(normalized_segments),
            summary_path,
        )
        return {
            'fileName': SUMMARY_FILENAME,
            'filePath': summary_path,
            'segmentCount': len(normalized_segments),
        }

    def get_scene_timeline(self, room_id: str, stream_folder: str):
        session_dir = self.get_session_dir_by_folder(room_id, stream_folder)
        live_info_path = os.path.join(session_dir, CATEGORY_FILES['live_info'])
        if not os.path.isfile(live_info_path):
            return None

        live_info = self._parse_live_info(self._read_text_file(live_info_path))
        duration_seconds = self._parse_chinese_duration(live_info.get('durationText') or '')
        picture_path = os.path.join(session_dir, CATEGORY_FILES['picture'])
        samples = self._parse_picture_samples(self._read_text_file(picture_path), duration_seconds)

        if duration_seconds <= 0 and samples:
            duration_seconds = max(int(sample.get('timeSeconds') or 0) for sample in samples)

        segments = self._build_scene_segments(samples, duration_seconds)
        mental_path = os.path.join(session_dir, CATEGORY_FILES['mental'])
        voice_path = os.path.join(session_dir, CATEGORY_FILES['voice'])
        mental_records = self._parse_timed_archive_lines(
            self._read_text_file(mental_path),
            MENTAL_LINE_MARKER,
        )
        voice_records = self._parse_timed_archive_lines(
            self._read_text_file(voice_path),
            VOICE_LINE_MARKER,
        )
        picture_conclusion_records = self._parse_picture_conclusion_records(
            self._read_text_file(picture_path),
        )
        enriched_segments = []
        for segment in segments:
            start_seconds = int(segment.get('startSeconds') or 0)
            end_seconds = int(segment.get('endSeconds') or 0)
            enriched_segments.append({
                **segment,
                'mentalExcerpts': self._prepare_segment_excerpts(
                    self._filter_timed_records_for_segment(
                        mental_records,
                        start_seconds,
                        end_seconds,
                    )
                ),
                'voiceExcerpts': self._prepare_segment_excerpts(
                    self._filter_timed_records_for_segment(
                        voice_records,
                        start_seconds,
                        end_seconds,
                    )
                ),
                'pictureConclusions': self._prepare_segment_excerpts(
                    self._filter_picture_conclusions_for_segment(
                        picture_conclusion_records,
                        start_seconds,
                        end_seconds,
                    )
                ),
            })

        cached_summaries = self._load_segment_summaries_map(session_dir, enriched_segments)
        for index, segment in enumerate(enriched_segments):
            cached_summary = cached_summaries.get(index)
            if cached_summary:
                segment['cachedSummary'] = cached_summary

        return {
            'durationSeconds': duration_seconds,
            'durationText': live_info.get('durationText') or '',
            'voteWindowSize': SCENE_VOTE_WINDOW_SIZE,
            'segments': enriched_segments,
            'sceneLegend': [
                {
                    'sceneKey': scene_key,
                    'sceneText': definition['sceneText'],
                    'color': definition['color'],
                }
                for scene_key, definition in SCENE_DEFINITIONS.items()
            ],
        }

    @staticmethod
    def _normalize_clip_duration(clip_duration_seconds: int) -> int:
        duration = int(clip_duration_seconds or CLIP_DURATION_DEFAULT)
        return max(CLIP_DURATION_MIN, min(CLIP_DURATION_MAX, duration))

    @staticmethod
    def _clip_type_value_key(clip_type: str) -> str:
        clip_type_key = str(clip_type or '').strip().lower()
        if clip_type_key == CLIP_TYPE_GIFT:
            return 'amount'
        if clip_type_key == CLIP_TYPE_DANMAKU:
            return 'count'
        raise ValueError(f'unsupported clip type: {clip_type}')

    @staticmethod
    def _format_chinese_duration(seconds: int) -> str:
        total = max(0, int(seconds or 0))
        hours = total // 3600
        minutes = (total % 3600) // 60
        secs = total % 60
        parts = []
        if hours > 0:
            parts.append(f'{hours}小时')
        if minutes > 0:
            parts.append(f'{minutes}分')
        if secs > 0 or not parts:
            parts.append(f'{secs}秒')
        return ''.join(parts)

    @staticmethod
    def _suggest_clip_window(timeline, value_key: str, total_duration: int, clip_duration: int):
        total_duration = max(0, int(total_duration or 0))
        clip_duration = LiveArchiveService._normalize_clip_duration(clip_duration)
        if total_duration <= 0:
            return {
                'startSeconds': 0,
                'endSeconds': 0,
                'clipDurationSeconds': clip_duration,
                'peakScore': 0.0,
            }

        effective_duration = min(clip_duration, total_duration)
        if total_duration <= effective_duration:
            return {
                'startSeconds': 0,
                'endSeconds': total_duration,
                'clipDurationSeconds': effective_duration,
                'peakScore': LiveArchiveService._score_clip_window(
                    timeline, value_key, 0, total_duration
                ),
            }

        best_start = 0
        best_score = -1.0
        latest_start = total_duration - effective_duration
        for start in range(0, latest_start + 1):
            end = start + effective_duration
            score = LiveArchiveService._score_clip_window(timeline, value_key, start, end)
            if score > best_score:
                best_score = score
                best_start = start

        return {
            'startSeconds': best_start,
            'endSeconds': best_start + effective_duration,
            'clipDurationSeconds': effective_duration,
            'peakScore': best_score,
        }

    @staticmethod
    def _score_clip_window(timeline, value_key: str, start_seconds: int, end_seconds: int) -> float:
        score = 0.0
        for point in timeline or []:
            time_seconds = int(point.get('timeSeconds') or 0)
            if start_seconds <= time_seconds <= end_seconds:
                try:
                    score += float(point.get(value_key) or 0)
                except (TypeError, ValueError):
                    continue
        return score

    def suggest_clip(self, room_id: str, stream_folder: str, clip_type: str, clip_duration_seconds: int):
        timeline_data = self.get_clip_timeline(room_id, stream_folder)
        if timeline_data is None:
            return None

        clip_type_key = str(clip_type or '').strip().lower()
        value_key = self._clip_type_value_key(clip_type_key)
        if clip_type_key == CLIP_TYPE_GIFT:
            timeline = timeline_data.get('giftTimeline') or []
        elif clip_type_key == CLIP_TYPE_DANMAKU:
            timeline = timeline_data.get('danmakuTimeline') or []
        else:
            raise ValueError(f'unsupported clip type: {clip_type}')

        total_duration = int(timeline_data.get('durationSeconds') or 0)
        clip_duration = self._normalize_clip_duration(clip_duration_seconds)
        suggestion = self._suggest_clip_window(timeline, value_key, total_duration, clip_duration)
        return {
            **suggestion,
            'clipType': clip_type_key,
            'totalDurationSeconds': total_duration,
            'startText': self._format_chinese_duration(suggestion['startSeconds']),
            'endText': self._format_chinese_duration(suggestion['endSeconds']),
            'clipDurationText': self._format_chinese_duration(suggestion['clipDurationSeconds']),
            'recordingFilePath': timeline_data.get('recordingFilePath') or '',
            'hasRecording': bool(timeline_data.get('hasRecording')),
        }

    @staticmethod
    def _build_clip_output_path(recording_path: str, clip_type: str) -> str:
        directory = os.path.dirname(recording_path)
        _, ext = os.path.splitext(recording_path)
        if ext == '':
            ext = '.mp4'
        suffix = '弹幕' if clip_type == CLIP_TYPE_DANMAKU else '礼物'
        return os.path.join(directory, f'自动切片_{suffix}{ext}')

    def _export_clip_with_ffmpeg(self, recording_path: str, output_path: str, start_seconds: int, duration_seconds: int):
        ffmpeg_path = _resolve_ffmpeg_tool('ffmpeg')
        if not ffmpeg_path:
            raise RuntimeError('ffmpeg not found')

        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        command = [
            ffmpeg_path,
            '-y',
            '-ss', f'{max(0, start_seconds):.3f}',
            '-i', recording_path,
            '-t', f'{max(0.1, duration_seconds):.3f}',
            '-c', 'copy',
            output_path,
        ]
        returncode, _, stderr = _run_media_command(command)
        if returncode != 0 or not os.path.isfile(output_path):
            reencode_command = [
                ffmpeg_path,
                '-y',
                '-ss', f'{max(0, start_seconds):.3f}',
                '-i', recording_path,
                '-t', f'{max(0.1, duration_seconds):.3f}',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-c:a', 'aac',
                output_path,
            ]
            returncode, _, stderr = _run_media_command(reencode_command)
            if returncode != 0 or not os.path.isfile(output_path):
                error_text = stderr or 'ffmpeg clip failed'
                raise RuntimeError(error_text)

    def export_clip(self, room_id: str, stream_folder: str, clip_type: str, start_seconds: int, end_seconds: int):
        timeline_data = self.get_clip_timeline(room_id, stream_folder)
        if timeline_data is None:
            return None

        clip_type_key = str(clip_type or '').strip().lower()
        self._clip_type_value_key(clip_type_key)

        recording_path = str(timeline_data.get('recordingFilePath') or '').strip()
        if recording_path == '' or not os.path.isfile(recording_path):
            raise ValueError('recording file not found')

        total_duration = int(timeline_data.get('durationSeconds') or 0)
        start = max(0, int(start_seconds or 0))
        end = max(start, int(end_seconds or 0))
        clip_duration = end - start
        if clip_duration < CLIP_DURATION_MIN:
            raise ValueError(f'clip duration must be at least {CLIP_DURATION_MIN} seconds')
        if clip_duration > CLIP_DURATION_MAX:
            raise ValueError(f'clip duration must be at most {CLIP_DURATION_MAX} seconds')
        if total_duration > 0 and end > total_duration:
            raise ValueError('clip end exceeds live duration')

        output_path = self._build_clip_output_path(recording_path, clip_type_key)
        self._export_clip_with_ffmpeg(recording_path, output_path, start, clip_duration)
        return {
            'clipType': clip_type_key,
            'startSeconds': start,
            'endSeconds': end,
            'clipDurationSeconds': clip_duration,
            'startText': self._format_chinese_duration(start),
            'endText': self._format_chinese_duration(end),
            'clipDurationText': self._format_chinese_duration(clip_duration),
            'sourceRecordingPath': recording_path,
            'outputPath': output_path,
            'outputFileName': os.path.basename(output_path),
        }

    def get_cover_path(self, room_id: str, stream_folder: str):
        session_dir = self.get_session_dir_by_folder(room_id, stream_folder)
        cover_path = os.path.join(session_dir, COVER_FILENAME)
        if os.path.isfile(cover_path):
            return cover_path
        return None

    @staticmethod
    def _probe_video_duration(video_path: str):
        ffprobe_path = _resolve_ffmpeg_tool('ffprobe')
        if not ffprobe_path:
            return 0.0
        try:
            returncode, stdout, stderr = _run_media_command([
                ffprobe_path,
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path,
            ])
            if returncode != 0:
                logger.warning(
                    'ffprobe failed for %s: %s',
                    video_path,
                    stderr or stdout,
                )
                return 0.0
            return max(0.0, float(stdout))
        except (OSError, ValueError) as e:
            logger.warning('ffprobe error for %s: %s', video_path, e)
            return 0.0

    def _generate_cover_from_video(self, video_path: str, cover_path: str):
        ffmpeg_path = _resolve_ffmpeg_tool('ffmpeg')
        if not ffmpeg_path:
            return False
        duration = self._probe_video_duration(video_path)
        if duration <= 0:
            return False
        seek_seconds = duration * random.uniform(0.2, 0.8)
        try:
            returncode, _, stderr = _run_media_command([
                ffmpeg_path,
                '-y',
                '-ss', f'{seek_seconds:.3f}',
                '-i', video_path,
                '-frames:v', '1',
                '-q:v', '2',
                cover_path,
            ])
            if returncode != 0:
                logger.warning(
                    'ffmpeg cover generation failed for %s: %s',
                    video_path,
                    stderr,
                )
                return False
            return os.path.isfile(cover_path)
        except OSError as e:
            logger.warning('ffmpeg error for %s: %s', video_path, e)
            return False

    def ensure_cover(self, room_id: str, stream_folder: str):
        existing = self.get_cover_path(room_id, stream_folder)
        if existing:
            return existing

        session_dir = self.get_session_dir_by_folder(room_id, stream_folder)
        live_info_path = os.path.join(session_dir, CATEGORY_FILES['live_info'])
        live_info = self._parse_live_info(self._read_text_file(live_info_path))
        recording_path = str(live_info.get('recordingFilePath') or '').strip()
        if recording_path == '' or not os.path.isfile(recording_path):
            return None

        cover_path = os.path.join(session_dir, COVER_FILENAME)
        if self._generate_cover_from_video(recording_path, cover_path):
            logger.info(
                'live archive cover generated room_id=%s stream_folder=%s path=%s',
                room_id,
                stream_folder,
                cover_path,
            )
            return cover_path
        return None
