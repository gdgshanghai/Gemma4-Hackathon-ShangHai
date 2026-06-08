# -*- coding: utf-8 -*-
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import *

logger = logging.getLogger(__name__)

_service: Optional['ObsBridgeService'] = None


def init():
    global _service
    _service = ObsBridgeService()


async def shut_down():
    if _service is not None:
        _service.shut_down()


def get_state():
    if _service is None:
        return {}
    return _service.get_state()


def get_public_state():
    if _service is None:
        return {}
    return _service.get_public_state()


def subscribe(client: Any):
    if _service is not None:
        _service.subscribe(client)


def unsubscribe(client: Any):
    if _service is not None:
        _service.unsubscribe(client)


def update_event(data: dict):
    if _service is None:
        return {}
    return _service.update_event(data)


def update_frame(data: dict):
    if _service is None:
        return {}
    return _service.update_frame(data)


def update_audio(data: dict):
    if _service is None:
        return {}
    return _service.update_audio(data)


def update_config(data: dict):
    if _service is None:
        return {}
    return _service.update_config(data)


def get_config():
    if _service is None:
        return {}
    return _service.get_config()


class ObsBridgeService:
    def __init__(self):
        self._clients: Set[Any] = set()
        self._state = {
            'connected': False,
            'streamingActive': False,
            'splitAudioTracks': False,
            'lastEvent': None,
            'latestFrame': None,
            'latestAudio': None,
            'latestMicAudio': None,
            'latestDesktopAudio': None,
            'streamStartedAt': 0,
            'streamDurationSeconds': 0,
            'lastStreamStartedAt': 0,
            'lastStreamDurationSeconds': 0,
            'recordingFilePath': '',
            'updatedAt': None,
        }

    def shut_down(self):
        for client in list(self._clients):
            try:
                client.close()
            except Exception:
                logger.exception('Failed to close OBS bridge client:')
        self._clients.clear()

    def get_state(self):
        return self._state_with_current_duration(include_private=True)

    def get_public_state(self):
        state = self._state_with_current_duration(include_private=True)
        for audio_key in ('latestAudio', 'latestMicAudio', 'latestDesktopAudio'):
            latest_audio = state.get(audio_key)
            if isinstance(latest_audio, dict):
                state[audio_key] = self._public_audio(latest_audio)
        latest_frame = state.get('latestFrame')
        if isinstance(latest_frame, dict):
            state['latestFrame'] = self._public_frame(latest_frame)
        return state

    def get_config(self):
        return {
            'splitAudioTracks': bool(self._state.get('splitAudioTracks')),
            'updatedAt': self._state.get('updatedAt'),
        }

    def update_config(self, data: dict):
        if 'splitAudioTracks' in data:
            self._state['splitAudioTracks'] = bool(data.get('splitAudioTracks'))
        self._touch()
        self._broadcast('config', self.get_config())
        self._broadcast('state', self.get_public_state())
        return self.get_config()

    def _state_with_current_duration(self, include_private: bool = False):
        state = dict(self._state)
        if state.get('streamingActive') and state.get('streamStartedAt'):
            state['streamDurationSeconds'] = max(0, time.time() - float(state['streamStartedAt']))
        elif state.get('streamDurationSeconds', 0) <= 0 and state.get('lastStreamDurationSeconds', 0) > 0:
            state['streamDurationSeconds'] = float(state['lastStreamDurationSeconds'])
        if not include_private:
            for audio_key in ('latestAudio', 'latestMicAudio', 'latestDesktopAudio'):
                latest_audio = state.get(audio_key)
                if isinstance(latest_audio, dict):
                    state[audio_key] = self._public_audio(latest_audio)
            latest_frame = state.get('latestFrame')
            if isinstance(latest_frame, dict):
                state['latestFrame'] = self._public_frame(latest_frame)
        return state

    def subscribe(self, client: Any):
        self._clients.add(client)

    def unsubscribe(self, client: Any):
        self._clients.discard(client)

    def update_event(self, data: dict):
        event_type = str(data.get('type', '')).strip()
        if event_type == '':
            event_type = 'obs_event'

        streaming_active = data.get('streamingActive', None)
        if streaming_active is None:
            if event_type in ('streaming_started', 'streaming_starting'):
                streaming_active = True
            elif event_type in ('streaming_stopped', 'streaming_stopping'):
                streaming_active = False

        recording_file_path = str(data.get('recordingFilePath', '') or '').strip()

        event = {
            'type': event_type,
            'streamingActive': bool(streaming_active) if streaming_active is not None else self._state['streamingActive'],
            'outputState': data.get('outputState', ''),
            'message': data.get('message', ''),
            'streamStartedAt': int(data.get('streamStartedAt', 0) or 0),
            'streamDurationSeconds': self._state.get('streamDurationSeconds', 0),
            'recordingFilePath': recording_file_path,
            'ts': self._now_iso(),
        }
        if 'streamDurationSeconds' in data:
            event['streamDurationSeconds'] = self._to_float(data.get('streamDurationSeconds', 0))
        self._state['connected'] = True
        self._state['streamingActive'] = event['streamingActive']
        if event['streamingActive']:
            self._state['streamStartedAt'] = event['streamStartedAt']
            self._state['streamDurationSeconds'] = 0
            self._state['lastStreamStartedAt'] = 0
            self._state['lastStreamDurationSeconds'] = 0
            self._state['recordingFilePath'] = ''
        elif event_type in ('streaming_stopped', 'streaming_stopping'):
            if event['streamStartedAt'] > 0:
                self._state['lastStreamStartedAt'] = event['streamStartedAt']
            if event['streamDurationSeconds'] > 0:
                self._state['lastStreamDurationSeconds'] = event['streamDurationSeconds']
            self._state['streamStartedAt'] = 0
            self._state['streamDurationSeconds'] = event['streamDurationSeconds']
        if recording_file_path:
            self._state['recordingFilePath'] = recording_file_path
        if 'streamDurationSeconds' in data:
            self._state['streamDurationSeconds'] = event['streamDurationSeconds']
        self._state['lastEvent'] = event
        self._touch()
        self._broadcast('event', event)
        self._broadcast('state', self.get_public_state())
        return self.get_state()

    def update_frame(self, data: dict):
        frame = {
            'sourceName': data.get('sourceName', ''),
            'imageFormat': data.get('imageFormat', 'jpg'),
            'imageData': data.get('imageData', ''),
            'imageFilePath': data.get('imageFilePath', ''),
            'width': data.get('width', 0),
            'height': data.get('height', 0),
            'summary': data.get('summary', ''),
            'ts': self._now_iso(),
        }
        self._state['connected'] = True
        self._state['latestFrame'] = frame
        self._touch()
        self._broadcast('frame', self._public_frame(frame))
        return self.get_state()

    def update_audio(self, data: dict):
        track_role = str(data.get('trackRole', 'mixed') or 'mixed').strip().lower()
        audio = {
            'trackRole': track_role,
            'mixIdx': int(data.get('mixIdx', 0) or 0),
            'level': self._to_float(data.get('level', 0)),
            'rms': self._to_float(data.get('rms', 0)),
            'peak': self._to_float(data.get('peak', 0)),
            'transcript': str(data.get('transcript', '') or ''),
            'sampleRate': int(data.get('sampleRate', 0) or 0),
            'channels': int(data.get('channels', 0) or 0),
            'audioFormat': str(data.get('audioFormat', '') or ''),
            'audioData': str(data.get('audioData', '') or ''),
            'durationSeconds': self._to_float(data.get('durationSeconds', 0)),
            'ts': self._now_iso(),
        }
        self._state['connected'] = True
        if track_role == 'mic':
            self._state['latestMicAudio'] = audio
        elif track_role == 'desktop':
            self._state['latestDesktopAudio'] = audio
        else:
            self._state['latestAudio'] = audio
        self._touch()
        self._broadcast('audio', self._public_audio(audio))
        return self.get_state()

    @staticmethod
    def _public_audio(audio: dict):
        public_audio = dict(audio)
        public_audio.pop('audioData', None)
        return public_audio

    @staticmethod
    def _public_frame(frame: dict):
        public_frame = dict(frame)
        public_frame.pop('imageData', None)
        return public_frame

    def _touch(self):
        self._state['updatedAt'] = self._now_iso()

    def _broadcast(self, msg_type: str, data: dict):
        body = {
            'type': msg_type,
            'data': data,
        }
        for client in list(self._clients):
            try:
                client.write_message(body)
            except Exception:
                self._clients.discard(client)

    @staticmethod
    def _now_iso():
        return datetime.now(timezone.utc).astimezone().isoformat()

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
