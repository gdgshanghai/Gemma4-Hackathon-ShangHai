# -*- coding: utf-8 -*-
import configparser
import logging
import os
import re
import sys
from typing import *

logger = logging.getLogger(__name__)


def _application_base_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.realpath(__file__))


def _frozen_install_root() -> str:
    """Writable install state for packaged apps (not next to the .app/.exe)."""
    if not getattr(sys, 'frozen', False):
        return ''
    if sys.platform == 'darwin':
        return os.path.join(os.path.expanduser('~/Library/Application Support'), 'blivechat')
    program_data = os.environ.get('PROGRAMDATA', '').strip()
    if program_data:
        return os.path.join(program_data, 'blivechat')
    return ''


def _application_data_path(base_path: str) -> str:
    override = os.environ.get('BLIVECHAT_DATA_DIR', '').strip()
    if override:
        return override
    install_root = _frozen_install_root()
    if install_root:
        return os.path.join(install_root, 'data')
    return os.path.join(base_path, 'data')


def _application_log_path(base_path: str) -> str:
    override = os.environ.get('BLIVECHAT_LOG_DIR', '').strip()
    if override:
        return override
    install_root = _frozen_install_root()
    if install_root:
        return os.path.join(install_root, 'log')
    return os.path.join(base_path, 'log')


def _bundled_resource_dir(base_path: str) -> str:
    """PyInstaller onedir: static files live under _internal (sys._MEIPASS)."""
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            return meipass
    return base_path


BASE_PATH = _application_base_path()
_BUNDLED_DIR = _bundled_resource_dir(BASE_PATH)
WEB_ROOT = os.path.join(_BUNDLED_DIR, 'frontend', 'dist')
BUNDLED_PLUGINS_PATH = os.path.join(_BUNDLED_DIR, 'plugins')
DATA_PATH = _application_data_path(BASE_PATH)
LOG_PATH = _application_log_path(BASE_PATH)

CONFIG_PATH_LIST = [
    os.path.join(DATA_PATH, 'config.ini'),
    os.path.join(DATA_PATH, 'config.example.ini'),
    os.path.join(_BUNDLED_DIR, 'data', 'config.example.ini'),
]

_config: Optional['AppConfig'] = None


def ensure_runtime_dirs():
    os.makedirs(DATA_PATH, exist_ok=True)
    os.makedirs(os.path.join(DATA_PATH, 'plugins'), exist_ok=True)
    os.makedirs(LOG_PATH, exist_ok=True)


def _default_database_url() -> str:
    db_path = os.path.abspath(os.path.join(DATA_PATH, 'database.db'))
    return 'sqlite:///' + db_path.replace('\\', '/')


def _is_legacy_database_url(database_url: str) -> bool:
    if database_url in {
        'sqlite:///data/database.db',
        'sqlite:///./data/database.db',
    }:
        return True
    return database_url.startswith('sqlite:///data/')


def _repair_config_ini_file():
    """Fix broken config.ini (e.g. section header merged into comment line)."""
    config_ini = os.path.join(DATA_PATH, 'config.ini')
    example_path = os.path.join(_BUNDLED_DIR, 'data', 'config.example.ini')
    if not os.path.isfile(config_ini):
        return
    try:
        config = configparser.ConfigParser(strict=False)
        config.read(config_ini, 'utf-8-sig')
        if config.sections():
            match = re.search(r'^database_url\s*=\s*(.+)$', open(config_ini, encoding='utf-8-sig').read(), re.MULTILINE)
            if match is not None and _is_legacy_database_url(match.group(1).strip()):
                if 'app' not in config:
                    config.add_section('app')
                config['app']['database_url'] = _default_database_url()
                with open(config_ini, 'w', encoding='utf-8') as f:
                    config.write(f)
                logger.info('Repaired database_url in %s', config_ini)
            return
    except Exception:
        logger.warning('config.ini unreadable, restoring from example')

    if os.path.isfile(example_path):
        import shutil
        shutil.copy2(example_path, config_ini)
        lines = open(config_ini, 'r', encoding='utf-8-sig').readlines()
        new_url = _default_database_url()
        with open(config_ini, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.strip().startswith('database_url'):
                    f.write(f'database_url = {new_url}\n')
                else:
                    f.write(line)
        logger.info('Restored config from example: %s', config_ini)


def apply_install_defaults(app_config: 'AppConfig'):
    """Packaged install: keep writable data under OS user data dir (ProgramData / Application Support)."""
    ensure_runtime_dirs()
    if _is_legacy_database_url(app_config.database_url):
        app_config.database_url = _default_database_url()


def _bootstrap_config_ini():
    config_ini = os.path.join(DATA_PATH, 'config.ini')
    if os.path.isfile(config_ini):
        return
    for example_path in CONFIG_PATH_LIST[1:]:
        if example_path.endswith('config.example.ini') and os.path.isfile(example_path):
            import shutil
            shutil.copy2(example_path, config_ini)
            logger.info('Created config from example: %s', config_ini)
            return
    ensure_runtime_dirs()
    with open(config_ini, 'w', encoding='utf-8') as f:
        f.write(
            '[app]\n'
            f'host = 127.0.0.1\n'
            f'port = 12450\n'
            f'database_url = {_default_database_url()}\n'
            f'open_browser_at_startup = true\n'
            f'loader_url = \n'
        )
    logger.info('Created default config: %s', config_ini)


def init(cmd_args):
    ensure_runtime_dirs()
    if getattr(sys, 'frozen', False):
        _bootstrap_config_ini()
        _repair_config_ini_file()

    if reload(cmd_args):
        apply_install_defaults(get_config())
        return

    logger.warning('Using default config')
    config = AppConfig()
    config.load_cmd_args(cmd_args)
    apply_install_defaults(config)

    global _config
    _config = config


def reload(cmd_args=None):
    config_path = ''
    for path in CONFIG_PATH_LIST:
        if os.path.exists(path):
            config_path = path
            break
    if config_path == '':
        return False

    config = AppConfig()
    if not config.load(config_path):
        return False
    config.load_cmd_args(cmd_args)
    apply_install_defaults(config)

    global _config
    _config = config
    return True


def get_config():
    return _config


class AppConfig:
    def __init__(self):
        self.debug = False
        self.host = '127.0.0.1'
        self.port = 12450
        self.database_url = 'sqlite:///data/database.db'
        self.tornado_xheaders = False
        self.loader_url = ''
        self.open_browser_at_startup = True
        self.enable_upload_file = True
        self.enable_admin_plugins = True

        self.fetch_avatar_max_queue_size = 4
        self.avatar_cache_size = 10000

        self.open_live_access_key_id = ''
        self.open_live_access_key_secret = ''
        self.open_live_app_id = 0

        self.enable_translate = True
        self.allow_translate_rooms: Set[int] = set()
        self.translate_max_queue_size = 10
        self.translation_cache_size = 50000
        self.translator_configs: List[dict] = []

        self.text_emoticons: List[dict] = []

        self.qwen_api_key = 'sk-crazy-thursday-viwo50'
        self.qwen_base_url = 'https://u1027991-ab00-48a182a5.westb.seetacloud.com:8443/v1'
        self.qwen_model = 'gemma4-31b-mm'
        self.qwen_asr_model = 'gemma4-e4b-mm'
        self.qwen_vision_model = 'gemma4-31b-mm'

        self.registered_endpoints: List[str] = []
        self.cors_origins: List[re.Pattern[str]] = []

    @property
    def is_open_live_configured(self):
        return (
            self.open_live_access_key_id != '' and self.open_live_access_key_secret != '' and self.open_live_app_id != 0
        )

    def load_cmd_args(self, args=None):
        if args is None:
            return
        if args.host is not None:
            self.host = args.host
        if args.port is not None:
            self.port = args.port
        self.debug = args.debug

    def load(self, path):
        try:
            config = configparser.ConfigParser(strict=False)
            config.read(path, 'utf-8-sig')

            self._load_app_config(config)
            self._load_translator_configs(config)
            self._load_text_emoticons(config)
            self._load_qwen_config(config)
            self._load_registered_endpoints(config)
            self._load_cors_origins(config)
        except Exception:  # noqa
            logger.exception('Failed to load config:')
            return False
        return True

    def _load_app_config(self, config: configparser.ConfigParser):
        app_section = config['app']
        self.host = app_section.get('host', self.host)
        self.port = app_section.getint('port', self.port)
        self.database_url = app_section.get('database_url', self.database_url)
        self.tornado_xheaders = app_section.getboolean('tornado_xheaders', self.tornado_xheaders)
        self.loader_url = app_section.get('loader_url', self.loader_url)
        if self.loader_url == '{local_loader}':
            self.loader_url = self._get_local_loader_url()
        self.open_browser_at_startup = app_section.getboolean('open_browser_at_startup', self.open_browser_at_startup)
        self.enable_upload_file = app_section.getboolean('enable_upload_file', self.enable_upload_file)
        self.enable_admin_plugins = app_section.getboolean('enable_admin_plugins', self.enable_admin_plugins)

        self.fetch_avatar_max_queue_size = app_section.getint(
            'fetch_avatar_max_queue_size', self.fetch_avatar_max_queue_size
        )
        self.avatar_cache_size = app_section.getint('avatar_cache_size', self.avatar_cache_size)

        self.open_live_access_key_id = app_section.get('open_live_access_key_id', self.open_live_access_key_id)
        self.open_live_access_key_secret = app_section.get(
            'open_live_access_key_secret', self.open_live_access_key_secret
        )
        self.open_live_app_id = app_section.getint('open_live_app_id', self.open_live_app_id)

        self.enable_translate = app_section.getboolean('enable_translate', self.enable_translate)
        self.allow_translate_rooms = _str_to_list(app_section.get('allow_translate_rooms', ''), int, set)
        self.translate_max_queue_size = app_section.getint('translate_max_queue_size', self.translate_max_queue_size)
        self.translation_cache_size = app_section.getint('translation_cache_size', self.translation_cache_size)

    @staticmethod
    def _get_local_loader_url():
        url = os.path.abspath(os.path.join(DATA_PATH, 'loader.html'))
        url = url.replace('\\', '/')
        if not url.startswith('/'):  # Windows
            url = '/' + url
        url = 'file://' + url
        return url

    def _load_translator_configs(self, config: configparser.ConfigParser):
        try:
            app_section = config['app']
        except KeyError:
            return
        section_names = _str_to_list(app_section.get('translator_configs', ''))
        translator_configs = []
        for section_name in section_names:
            try:
                section = config[section_name]
                type_ = section['type']

                translator_config = {
                    'type': type_,
                    'query_interval': section.getfloat('query_interval'),
                }
                if type_ in ('TencentTranslateFree', 'BilibiliTranslateFree'):
                    doc_url = (
                        'https://github.com/xfgryujk/blivechat/wiki/%E9%85%8D%E7%BD%AE%E5%AE%98%E6%96%B9'
                        '%E7%BF%BB%E8%AF%91%E6%8E%A5%E5%8F%A3'
                    )
                    logger.warning('%s is deprecated, please see %s', type_, doc_url)
                elif type_ == 'TencentTranslate':
                    translator_config['source_language'] = section['source_language']
                    translator_config['target_language'] = section['target_language']
                    translator_config['secret_id'] = section['secret_id']
                    translator_config['secret_key'] = section['secret_key']
                    translator_config['region'] = section['region']
                elif type_ == 'BaiduTranslate':
                    translator_config['source_language'] = section['source_language']
                    translator_config['target_language'] = section['target_language']
                    translator_config['app_id'] = section['app_id']
                    translator_config['secret'] = section['secret']
                elif type_ == 'GeminiTranslate':
                    logger.warning('%s is deprecated, please migrate to OpenAiApi', type_)
                elif type_ == 'OpenAiApi':
                    translator_config['api_key'] = section['api_key']
                    translator_config['base_url'] = section['base_url']
                    translator_config['proxy'] = section['proxy']
                    translator_config['model'] = section['model']
                    translator_config['prompt'] = section['prompt'].replace('\n', ' ').replace('\\n', '\n')
                    translator_config['max_tokens'] = section.getint('max_tokens')
                    translator_config['temperature'] = section.getfloat('temperature')
                    translator_config['top_p'] = section.getfloat('top_p')
                else:
                    raise ValueError(f'Invalid translator type: {type_}')
            except Exception:  # noqa
                logger.exception('Failed to load translator=%s config:', section_name)
                continue

            translator_configs.append(translator_config)
        self.translator_configs = translator_configs

    def _load_text_emoticons(self, config: configparser.ConfigParser):
        try:
            mappings_section = config['text_emoticon_mappings']
        except KeyError:
            return
        text_emoticons = []
        for value in mappings_section.values():
            keyword, _, url = value.partition(',')
            text_emoticons.append({'keyword': keyword, 'url': url})
        self.text_emoticons = text_emoticons

    def _load_qwen_config(self, config: configparser.ConfigParser):
        try:
            qwen_section = config['qwen']
            self.qwen_api_key = qwen_section.get('api_key', self.qwen_api_key).strip()
            self.qwen_base_url = qwen_section.get('base_url', self.qwen_base_url).strip()
            self.qwen_model = qwen_section.get('model', self.qwen_model).strip()
            self.qwen_asr_model = qwen_section.get('asr_model', self.qwen_asr_model).strip()
            self.qwen_vision_model = qwen_section.get('vision_model', self.qwen_vision_model).strip()
        except KeyError:
            pass
        if not self.qwen_api_key:
            self.qwen_api_key = os.environ.get('DASHSCOPE_API_KEY', '').strip()

    def _load_registered_endpoints(self, config: configparser.ConfigParser):
        try:
            registered_endpoints_section = config['registered_endpoints']
        except KeyError:
            return
        registered_endpoints = list(registered_endpoints_section.values())
        self.registered_endpoints = registered_endpoints

    def _load_cors_origins(self, config: configparser.ConfigParser):
        try:
            cors_origins_section = config['cors_origins']
        except KeyError:
            return
        cors_origins = [
            re.compile(origin, re.IGNORECASE)
            for origin in cors_origins_section.values()
        ]
        self.cors_origins = cors_origins

    def is_allowed_cors_origin(self, origin):
        return any(
            pattern.fullmatch(origin) is not None
            for pattern in self.cors_origins
        )


def _str_to_list(value, item_type: Type = str, container_type: Type = list):
    value = value.strip()
    if value == '':
        return container_type()
    items = value.split(',')
    items = map(lambda item: item.strip(), items)
    if item_type is not str:
        items = map(item_type, items)
    return container_type(items)
