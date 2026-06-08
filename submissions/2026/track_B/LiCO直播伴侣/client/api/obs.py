# -*- coding: utf-8 -*-
import logging

import tornado.websocket

import api.base
import config
import services.obs_bridge

logger = logging.getLogger(__name__)


class ObsStateHandler(api.base.ApiHandler):
    async def get(self):
        self.write({
            'success': True,
            'data': services.obs_bridge.get_state(),
        })


class ObsEventHandler(api.base.ApiHandler):
    async def post(self):
        services.obs_bridge.update_event(self.json_args or {})
        # 插件不解析响应；勿返回含 audioData 的完整 state，否则 curl 读超大 JSON 会失败
        self.write({'success': True})


class ObsFrameHandler(api.base.ApiHandler):
    async def post(self):
        services.obs_bridge.update_frame(self.json_args or {})
        self.write({'success': True})


class ObsAudioHandler(api.base.ApiHandler):
    async def post(self):
        services.obs_bridge.update_audio(self.json_args or {})
        self.write({'success': True})


class ObsConfigHandler(api.base.ApiHandler):
    async def get(self):
        self.write({
            'success': True,
            'data': services.obs_bridge.get_config(),
        })

    async def post(self):
        config = services.obs_bridge.update_config(self.json_args or {})
        self.write({'success': True, 'data': config})


class ObsAgentWebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        logger.info('OBS agent client=%s connected', self.request.remote_ip)
        services.obs_bridge.subscribe(self)
        self.write_message({
            'type': 'state',
            'data': services.obs_bridge.get_public_state(),
        })

    def on_close(self):
        logger.info('OBS agent client=%s disconnected', self.request.remote_ip)
        services.obs_bridge.unsubscribe(self)

    def check_origin(self, origin):
        cfg = config.get_config()
        return (
            cfg.debug
            or cfg.is_allowed_cors_origin(origin)
            or super().check_origin(origin)
        )


ROUTES = [
    (r'/api/obs/state', ObsStateHandler),
    (r'/api/obs/config', ObsConfigHandler),
    (r'/api/obs/event', ObsEventHandler),
    (r'/api/obs/frame', ObsFrameHandler),
    (r'/api/obs/audio', ObsAudioHandler),
    (r'/api/obs-agent', ObsAgentWebSocketHandler),
]
