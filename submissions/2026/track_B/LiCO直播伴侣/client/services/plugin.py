# -*- coding: utf-8 -*-
import dataclasses
import datetime
import json
import logging
import os
import random
import shutil
import string
import subprocess
import sys
from typing import *

import api.plugin
import blcsdk
import blcsdk.models as sdk_models
import config
import update

logger = logging.getLogger(__name__)

PLUGINS_PATH = os.path.join(config.DATA_PATH, 'plugins')
PLUGIN_SEARCH_PATHS = [
    PLUGINS_PATH,
    getattr(config, 'BUNDLED_PLUGINS_PATH', ''),
]

_plugins: Dict[str, 'Plugin'] = {}


def init():
    plugin_ids = _discover_plugin_ids()
    if not plugin_ids:
        return
    logger.info('Found plugins: %s', plugin_ids)

    for plugin_id in plugin_ids:
        plugin = _create_plugin(plugin_id)
        if plugin is not None:
            _plugins[plugin_id] = plugin

    for plugin in _plugins.values():
        if plugin.enabled:
            try:
                plugin.start()
            except SwitchPluginError:
                pass


def shut_down():
    for plugin in _plugins.values():
        plugin.stop()


def _discover_plugin_ids():
    res = []
    seen = set()
    for plugins_path in PLUGIN_SEARCH_PATHS:
        if not plugins_path:
            continue
        try:
            with os.scandir(plugins_path) as it:
                for entry in it:
                    if not entry.is_dir():
                        continue
                    if entry.name in seen:
                        continue
                    if os.path.isfile(os.path.join(entry.path, 'plugin.json')):
                        seen.add(entry.name)
                        res.append(entry.name)
        except OSError:
            logger.exception('Failed to discover plugins in %s:', plugins_path)
    return res


def _plugin_config_path(plugin_id: str) -> str:
    for plugins_path in PLUGIN_SEARCH_PATHS:
        if not plugins_path:
            continue
        config_path = os.path.join(plugins_path, plugin_id, 'plugin.json')
        if os.path.isfile(config_path):
            return config_path
    return os.path.join(PLUGINS_PATH, plugin_id, 'plugin.json')


def _create_plugin(plugin_id):
    config_path = _plugin_config_path(plugin_id)
    try:
        plugin_config = PluginConfig.from_file(config_path)
    except (OSError, json.JSONDecodeError, TypeError):
        logger.exception('plugin=%s failed to load config:', plugin_id)
        return None
    return Plugin(plugin_id, plugin_config)


def iter_plugins() -> Iterable['Plugin']:
    return _plugins.values()


def get_plugin(plugin_id):
    return _plugins.get(plugin_id, None)


def get_plugin_by_token(token):
    if token == '':
        return None
    # 应该最多就十几个插件吧，偷懒用遍历了
    for plugin in _plugins.values():
        if plugin.token == token:
            return plugin
    return None


def broadcast_cmd_data(cmd, data, extra: Optional[dict] = None):
    body = api.plugin.make_message_body(cmd, data, extra)
    for plugin in _plugins.values():
        plugin.send_body_no_raise(body)


@dataclasses.dataclass
class PluginConfig:
    name: str = ''
    version: str = ''
    author: str = ''
    description: str = ''
    run_cmd: str = ''
    enabled: bool = False

    @classmethod
    def from_file(cls, path):
        with open(path, encoding='utf-8-sig') as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise TypeError(f'Config type error, type={type(cfg)}')

        return cls(
            name=str(cfg.get('name', '')),
            version=str(cfg.get('version', '')),
            author=str(cfg.get('author', '')),
            description=str(cfg.get('description', '')),
            run_cmd=str(cfg.get('run', '')),
            enabled=bool(cfg.get('enabled', False)),
        )

    def save(self, path):
        try:
            with open(path, encoding='utf-8-sig') as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise TypeError(f'Config type error, type={type(cfg)}')
        except (OSError, json.JSONDecodeError, TypeError):
            cfg = {}

        cfg['name'] = self.name
        cfg['version'] = self.version
        cfg['author'] = self.author
        cfg['description'] = self.description
        cfg['run'] = self.run_cmd
        cfg['enabled'] = self.enabled

        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)


class SwitchPluginError(Exception):
    """开关插件时错误"""


class SwitchTooFrequently(SwitchPluginError):
    """开关插件太频繁"""


class Plugin:
    def __init__(self, plugin_id, cfg: PluginConfig):
        self._id = plugin_id
        self._config = cfg

        self._last_switch_time = datetime.datetime.fromtimestamp(0)
        self._token = ''
        self._client: Optional['api.plugin.PluginWsHandler'] = None

    @property
    def id(self):
        return self._id

    @property
    def config(self):
        return self._config

    @property
    def enabled(self):
        return self._config.enabled

    @enabled.setter
    def enabled(self, value):
        if self._config.enabled == value:
            return
        self._config.enabled = value

        config_path = os.path.join(self.base_path, 'plugin.json')
        try:
            self._config.save(config_path)
        except OSError:
            logger.exception('plugin=%s failed to save config', self._id)

        if value:
            self.start()
        else:
            self.stop()

    @property
    def base_path(self):
        return os.path.dirname(_plugin_config_path(self._id))

    @property
    def token(self):
        return self._token

    @property
    def is_started(self):
        return self._token != ''

    @property
    def is_connected(self):
        return self._client is not None

    def _plugin_python_executable(self) -> str:
        if getattr(sys, 'frozen', False):
            return sys.executable
        return shutil.which('python') or shutil.which('python3') or sys.executable

    def _plugin_sdk_path(self) -> str:
        if getattr(sys, 'frozen', False):
            meipass = getattr(sys, '_MEIPASS', '')
            if meipass:
                return meipass
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _resolve_run_cmd(self) -> Optional[str]:
        run_cmd = (self._config.run_cmd or '').strip()
        if run_cmd == '':
            return None
        exe_path = os.path.join(self.base_path, run_cmd)
        if os.path.isfile(exe_path):
            return run_cmd
        for entry in ('main.py', 'main.pyw'):
            main_script = os.path.join(self.base_path, entry)
            if not os.path.isfile(main_script):
                continue
            python = self._plugin_python_executable()
            if getattr(sys, 'frozen', False):
                return f'"{python}" --run-plugin "{main_script}"'
            return f'"{python}" "{main_script}"'
        logger.warning(
            'plugin=%s run target missing (run=%s, no exe/main.py/main.pyw in %s)',
            self._id, run_cmd, self.base_path,
        )
        return None

    def start(self):
        if self.is_started:
            return
        self._refresh_last_switch_time()

        token = ''.join(random.choice(string.hexdigits) for _ in range(32))
        self._set_token(token)

        cfg = config.get_config()
        env = {
            **os.environ,
            'BLC_PORT': str(cfg.port),
            'BLC_TOKEN': self._token,
        }
        run_cmd = self._resolve_run_cmd()
        if not run_cmd:
            logger.warning('plugin=%s cannot start (no runnable target)', self._id)
            raise SwitchPluginError(f'plugin={self._id} has no runnable target')
        sdk_path = self._plugin_sdk_path()
        if sdk_path:
            prev = env.get('PYTHONPATH', '')
            env['PYTHONPATH'] = sdk_path if prev == '' else sdk_path + os.pathsep + prev
        try:
            subprocess.Popen(
                run_cmd,
                shell=True,
                cwd=self.base_path,
                env=env,
            )
        except OSError as e:
            logger.exception('plugin=%s failed to start', self._id)
            raise SwitchPluginError(str(e))

    def _refresh_last_switch_time(self):
        cur_time = datetime.datetime.now()
        if cur_time - self._last_switch_time < datetime.timedelta(seconds=3):
            raise SwitchTooFrequently(f'plugin={self._id} switches too frequently')
        self._last_switch_time = cur_time

    def stop(self):
        if not self.is_started:
            return
        self._refresh_last_switch_time()

        self._set_token('')

    def _set_token(self, token):
        if self._token == token:
            return
        self._token = token

        # 踢掉已经连接的客户端
        self._set_client(None)

    def _set_client(self, client: Optional['api.plugin.PluginWsHandler']):
        if self._client is client:
            return
        if self._client is not None:
            logger.info('plugin=%s closing old client', self._id)
            self._client.close()
        self._client = client

    def on_client_connect(self, client: 'api.plugin.PluginWsHandler'):
        self._set_client(client)

        # 发送初始化消息
        self.send_cmd_data(sdk_models.Command.BLC_INIT, {
            'blcVersion': update.VERSION,
            'sdkVersion': blcsdk.__version__,
            'pluginId': self._id,
        })

    def on_client_close(self, client: 'api.plugin.PluginWsHandler'):
        if self._client is client:
            self._set_client(None)

    def send_cmd_data(self, cmd, data, extra: Optional[dict] = None):
        if self._client is not None:
            self._client.send_cmd_data(cmd, data, extra)

    def send_body_no_raise(self, body):
        if self._client is not None:
            self._client.send_body_no_raise(body)
