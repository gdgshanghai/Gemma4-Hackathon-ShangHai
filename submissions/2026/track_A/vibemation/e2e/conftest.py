"""n8n Agent — E2E 前端测试"""

import pytest


@pytest.fixture(autouse=True)
def reset_before_test(page):
    """清除 localStorage，确保每次测试从干净状态开始"""
    page.goto("/", wait_until="domcontentloaded")
    page.evaluate("localStorage.clear()")
    page.goto("/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
