# -*- coding: utf-8 -*-
import json
import logging
import os

import tornado.web

import api.base
import config

logger = logging.getLogger(__name__)


class QwenAuthStartHandler(tornado.web.RequestHandler):
    """启动千问认证"""

    async def post(self):
        user_code = 'YOUR_USER_CODE'
        callback_url = 'http://localhost:12450/api/qwen/auth/callback'
        auth_url = (
            f'https://chat.qwen.ai/authorize?user_code={user_code}'
            f'&client=qwen-code&redirect_uri={callback_url}'
        )
        self.write({
            'auth_url': auth_url,
            'user_code': user_code,
        })


class QwenAuthVerifyHandler(tornado.web.RequestHandler):
    """验证千问token"""

    async def post(self):
        auth_header = self.request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            self.set_status(401)
            self.write({'error': 'Invalid token'})
            return

        token = auth_header[7:]
        if token:
            self.write({'valid': True})
        else:
            self.set_status(401)
            self.write({'error': 'Invalid token'})


class QwenAuthCallbackHandler(tornado.web.RequestHandler):
    """千问认证回调页面"""

    async def get(self):
        code = self.get_argument('code', None)
        token = self.get_argument('token', None)
        error = self.get_argument('error', None)

        if error:
            html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>认证失败</title>
            </head>
            <body>
                <h2>认证失败</h2>
                <p>错误: {error}</p>
                <script>
                    setTimeout(function() {{
                        window.close();
                    }}, 3000);
                </script>
            </body>
            </html>
            '''
        else:
            auth_token = token or code
            html = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>认证成功</title>
            </head>
            <body>
                <h2>认证成功!</h2>
                <p>正在返回...</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'qwen-auth-success',
                            token: '{auth_token}'
                        }}, '*');
                    }}
                    setTimeout(function() {{
                        window.close();
                    }}, 1000);
                </script>
            </body>
            </html>
            '''

        self.set_header('Content-Type', 'text/html; charset=UTF-8')
        self.write(html)


class QwenStatusHandler(api.base.ApiHandler):
    """检查千问配置与连通性（供首页提示）"""

    async def get(self):
        cfg = config.get_config()
        config_path = os.path.join(config.DATA_PATH, 'config.ini')
        result = {
            'success': True,
            'configured': bool(cfg.qwen_api_key),
            'connected': False,
            'model': cfg.qwen_model,
            'baseUrl': cfg.qwen_base_url,
            'configPath': config_path,
            'error': '',
        }
        if not cfg.qwen_api_key:
            result['error'] = (
                '未配置 Qwen API 密钥。请在 config.ini 的 [qwen] 中设置 api_key，'
                '或设置环境变量 DASHSCOPE_API_KEY。'
            )
            self.write(result)
            return

        try:
            from openai import AsyncOpenAI
        except ImportError:
            result['error'] = '服务端未包含 openai 库，无法调用大模型。'
            self.write(result)
            return

        try:
            client = AsyncOpenAI(
                api_key=cfg.qwen_api_key,
                base_url=cfg.qwen_base_url,
            )
            await client.chat.completions.create(
                model=cfg.qwen_model,
                messages=[{'role': 'user', 'content': 'hi'}],
                max_tokens=1,
                timeout=20,
            )
            result['connected'] = True
        except Exception as e:
            logger.warning('Qwen connectivity probe failed: %s', e)
            result['error'] = str(e)
        self.write(result)


class QwenChatHandler(api.base.ApiHandler):
    """千问AI对话API"""

    async def post(self):
        try:
            data = json.loads(self.request.body)
            message = data.get('message', '')
            history = data.get('history', [])

            if not message:
                self.write({'success': False, 'error': '消息不能为空'})
                return

            cfg = config.get_config()
            if not cfg.qwen_api_key:
                self.write({
                    'success': False,
                    'error': (
                        '未配置Qwen API密钥。请在 '
                        f'{os.path.join(config.DATA_PATH, "config.ini")} '
                        '的 [qwen] 中配置 api_key，或设置环境变量 DASHSCOPE_API_KEY'
                    ),
                })
                return

            response, usage = await self._call_qwen_api(message, history, cfg)
            self.write({
                'success': True,
                'response': response,
                'usage': usage,
            })
        except Exception as e:
            logger.exception('Qwen chat error:')
            self.write({
                'success': False,
                'error': str(e),
            })

    async def _call_qwen_api(self, message: str, history: list, cfg):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            return '错误：未安装openai库。请运行: pip install openai', {
                'inputTokens': 0,
                'outputTokens': 0,
                'totalTokens': 0,
            }

        try:
            client = AsyncOpenAI(
                api_key=cfg.qwen_api_key,
                base_url=cfg.qwen_base_url,
            )

            messages = []
            for msg in history:
                messages.append({
                    'role': msg.get('role', 'user'),
                    'content': msg.get('content', ''),
                })
            messages.append({
                'role': 'user',
                'content': message,
            })

            completion = await client.chat.completions.create(
                model=cfg.qwen_model,
                messages=messages,
                timeout=90,
            )

            usage = getattr(completion, 'usage', None)
            input_tokens = getattr(usage, 'prompt_tokens', 0) if usage is not None else 0
            output_tokens = getattr(usage, 'completion_tokens', 0) if usage is not None else 0
            total_tokens = getattr(usage, 'total_tokens', input_tokens + output_tokens) if usage is not None else 0

            return completion.choices[0].message.content, {
                'inputTokens': input_tokens,
                'outputTokens': output_tokens,
                'totalTokens': total_tokens,
            }

        except Exception as e:
            logger.exception('Failed to call Qwen API:')
            raise Exception(f'调用Qwen API失败: {str(e)}') from e


ROUTES = [
    (r'/api/qwen/status', QwenStatusHandler),
    (r'/api/qwen/auth/start', QwenAuthStartHandler),
    (r'/api/qwen/auth/verify', QwenAuthVerifyHandler),
    (r'/api/qwen/auth/callback', QwenAuthCallbackHandler),
    (r'/api/qwen/chat', QwenChatHandler),
]
