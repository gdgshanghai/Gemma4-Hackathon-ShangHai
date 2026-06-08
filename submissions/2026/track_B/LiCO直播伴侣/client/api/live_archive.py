# -*- coding: utf-8 -*-
import asyncio
import logging
import os

import api.base
import services.live_archive
import tornado.web

logger = logging.getLogger(__name__)


class LiveArchiveInitHandler(api.base.ApiHandler):
    async def post(self):
        args = self.json_args or {}
        room_id = str(args.get('roomId', '') or '').strip()
        stream_started_at = int(args.get('streamStartedAt', 0) or 0)
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_started_at <= 0:
            self.write({'success': False, 'error': 'streamStartedAt is required'})
            return
        try:
            data = services.live_archive.ensure_session(room_id, stream_started_at)
            self.write({'success': True, 'data': data})
        except Exception as e:
            logger.exception('live archive init failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveAppendHandler(api.base.ApiHandler):
    async def post(self):
        args = self.json_args or {}
        room_id = str(args.get('roomId', '') or '').strip()
        stream_started_at = int(args.get('streamStartedAt', 0) or 0)
        category = str(args.get('category', '') or '').strip().lower()
        content = str(args.get('content', '') or '').strip()
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_started_at <= 0:
            self.write({'success': False, 'error': 'streamStartedAt is required'})
            return
        if content == '':
            self.write({'success': False, 'error': 'content is required'})
            return
        try:
            data = services.live_archive.append_record(
                room_id,
                stream_started_at,
                category,
                content,
            )
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive append failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveListHandler(api.base.ApiHandler):
    async def get(self):
        room_id = str(self.get_argument('roomId', '') or '').strip()
        limit = int(self.get_argument('limit', 10) or 10)
        generate_covers = str(self.get_argument('generateCovers', '1') or '1').strip().lower() not in ('0', 'false', 'no')
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.list_sessions(room_id, limit, generate_covers),
            )
            self.write({'success': True, 'data': data})
        except Exception as e:
            logger.exception('live archive list failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveCoverHandler(tornado.web.RequestHandler):
    async def get(self, room_id, stream_folder):
        try:
            cover_path = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.ensure_cover(room_id, stream_folder),
            )
            if cover_path is None:
                cover_path = services.live_archive.get_cover_path(room_id, stream_folder)
            if cover_path is None or not os.path.isfile(cover_path):
                raise tornado.web.HTTPError(404)
            self.set_header('Content-Type', 'image/jpeg')
            self.set_header('Cache-Control', 'public, max-age=86400')
            with open(cover_path, 'rb') as file:
                self.write(file.read())
        except ValueError:
            raise tornado.web.HTTPError(400)
        except tornado.web.HTTPError:
            raise
        except Exception:
            logger.exception('live archive cover failed:')
            raise tornado.web.HTTPError(500)


class LiveArchiveSessionHandler(api.base.ApiHandler):
    async def get(self):
        room_id = str(self.get_argument('roomId', '') or '').strip()
        stream_folder = str(self.get_argument('streamStartFolder', '') or '').strip()
        generate_cover = str(self.get_argument('generateCover', '0') or '0').strip().lower() in ('1', 'true', 'yes')
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_folder == '':
            self.write({'success': False, 'error': 'streamStartFolder is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.get_session(room_id, stream_folder, generate_cover),
            )
            if data is None:
                self.write({'success': False, 'error': 'session not found'})
                return
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive session failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveClipTimelineHandler(api.base.ApiHandler):
    async def get(self):
        room_id = str(self.get_argument('roomId', '') or '').strip()
        stream_folder = str(self.get_argument('streamStartFolder', '') or '').strip()
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_folder == '':
            self.write({'success': False, 'error': 'streamStartFolder is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.get_clip_timeline(room_id, stream_folder),
            )
            if data is None:
                self.write({'success': False, 'error': 'session not found'})
                return
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive clip timeline failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveClipSuggestionHandler(api.base.ApiHandler):
    async def get(self):
        room_id = str(self.get_argument('roomId', '') or '').strip()
        stream_folder = str(self.get_argument('streamStartFolder', '') or '').strip()
        clip_type = str(self.get_argument('clipType', '') or '').strip().lower()
        clip_duration_seconds = int(self.get_argument('clipDurationSeconds', 120) or 120)
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_folder == '':
            self.write({'success': False, 'error': 'streamStartFolder is required'})
            return
        if clip_type == '':
            self.write({'success': False, 'error': 'clipType is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.suggest_clip(
                    room_id,
                    stream_folder,
                    clip_type,
                    clip_duration_seconds,
                ),
            )
            if data is None:
                self.write({'success': False, 'error': 'session not found'})
                return
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive clip suggestion failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveClipExportHandler(api.base.ApiHandler):
    async def post(self):
        args = self.json_args or {}
        room_id = str(args.get('roomId', '') or '').strip()
        stream_folder = str(args.get('streamStartFolder', '') or '').strip()
        clip_type = str(args.get('clipType', '') or '').strip().lower()
        start_seconds = int(args.get('startSeconds', 0) or 0)
        end_seconds = int(args.get('endSeconds', 0) or 0)
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_folder == '':
            self.write({'success': False, 'error': 'streamStartFolder is required'})
            return
        if clip_type == '':
            self.write({'success': False, 'error': 'clipType is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.export_clip(
                    room_id,
                    stream_folder,
                    clip_type,
                    start_seconds,
                    end_seconds,
                ),
            )
            if data is None:
                self.write({'success': False, 'error': 'session not found'})
                return
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive clip export failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveSegmentSummariesHandler(api.base.ApiHandler):
    async def post(self):
        args = self.json_args or {}
        room_id = str(args.get('roomId', '') or '').strip()
        stream_folder = str(args.get('streamStartFolder', '') or '').strip()
        segments = args.get('segments') or []
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_folder == '':
            self.write({'success': False, 'error': 'streamStartFolder is required'})
            return
        if not isinstance(segments, list) or len(segments) == 0:
            self.write({'success': False, 'error': 'segments is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.save_segment_summaries(
                    room_id,
                    stream_folder,
                    segments,
                ),
            )
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive segment summaries save failed:')
            self.write({'success': False, 'error': str(e)})


class LiveArchiveSceneTimelineHandler(api.base.ApiHandler):
    async def get(self):
        room_id = str(self.get_argument('roomId', '') or '').strip()
        stream_folder = str(self.get_argument('streamStartFolder', '') or '').strip()
        if room_id == '':
            self.write({'success': False, 'error': 'roomId is required'})
            return
        if stream_folder == '':
            self.write({'success': False, 'error': 'streamStartFolder is required'})
            return
        try:
            data = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: services.live_archive.get_scene_timeline(room_id, stream_folder),
            )
            if data is None:
                self.write({'success': False, 'error': 'session not found'})
                return
            self.write({'success': True, 'data': data})
        except ValueError as e:
            self.write({'success': False, 'error': str(e)})
        except Exception as e:
            logger.exception('live archive scene timeline failed:')
            self.write({'success': False, 'error': str(e)})


ROUTES = [
    (r'/api/live/archive/init', LiveArchiveInitHandler),
    (r'/api/live/archive/append', LiveArchiveAppendHandler),
    (r'/api/live/archive/list', LiveArchiveListHandler),
    (r'/api/live/archive/session', LiveArchiveSessionHandler),
    (r'/api/live/archive/scene-timeline', LiveArchiveSceneTimelineHandler),
    (r'/api/live/archive/segment-summaries', LiveArchiveSegmentSummariesHandler),
    (r'/api/live/archive/clip-timeline', LiveArchiveClipTimelineHandler),
    (r'/api/live/archive/clip-suggestion', LiveArchiveClipSuggestionHandler),
    (r'/api/live/archive/clip-export', LiveArchiveClipExportHandler),
    (r'/api/live/archive/cover/([^/]+)/([^/]+)', LiveArchiveCoverHandler),
]
