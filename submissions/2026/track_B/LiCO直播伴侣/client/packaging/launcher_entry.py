#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PyInstaller 入口：与 main.py 等价，便于打包为 blivechat.exe。"""
import os
import runpy
import sys


def _run_bundled_plugin():
    plugin_main = os.path.abspath(sys.argv[2])
    plugin_dir = os.path.dirname(plugin_main)
    os.chdir(plugin_dir)
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)
    runpy.run_path(plugin_main, run_name='__main__')


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--run-plugin':
        _run_bundled_plugin()
        raise SystemExit(0)

    import asyncio

    import main

    raise SystemExit(asyncio.run(main.main()))
