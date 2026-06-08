"""n8n Agent 前端 E2E 测试

覆盖：
- 页面加载 & 基础布局
- 自部署 API 的添加、选择、切换
- 前端模式切换
- 聊天交互
- 配置面板
- 自部署 API 端到端流程
"""

import re
import json
import pytest
from playwright.sync_api import expect


# ═══════════════════════ 工具函数 ═══════════════════════

def add_custom_provider(page, name, url, api_key="", model=""):
    """在自部署 API 区域添加一个自定义 provider"""
    api_label = page.locator("label:has-text('自部署 API')")
    plus_btn = api_label.locator("..").locator("button:has-text('+')")
    plus_btn.click()

    page.locator("input[placeholder^='名称']").fill(name)
    page.locator("input[placeholder^='API 地址']").fill(url)
    if api_key:
        page.locator("input[placeholder^='API Key']").fill(api_key)
    if model:
        page.locator("input[placeholder^='模型名称']").fill(model)
    page.get_by_role("button", name="添加").click()


def select_provider_by_text(page, text):
    """通过 label 文本选择推理后端的 provider"""
    select = page.locator("select").first
    options = select.locator("option").all_text_contents()
    for i, opt_text in enumerate(options):
        if text in opt_text:
            select.select_option(index=i)
            return
    pytest.fail(f"未找到包含 '{text}' 的 provider 选项")


# ═══════════════════════ 页面加载 & 基础布局 ═══════════════════════

class TestPageLoad:
    """首页正确加载"""

    def test_title(self, page):
        expect(page).to_have_title(re.compile(r"n8n|Agent|Gemma"))

    def test_sidebar_and_main(self, page):
        expect(page.locator(".sidebar")).to_be_visible()
        expect(page.locator(".main")).to_be_visible()

    def test_key_elements(self, page):
        expect(page.get_by_text("n8n Agent")).to_be_visible()
        expect(page.get_by_text("推理后端")).to_be_visible()
        expect(page.get_by_text("自部署 API")).to_be_visible()
        expect(page.get_by_text("n8n 实例")).to_be_visible()

    def test_provider_dropdown_has_builtin(self, page):
        select = page.locator("select").first
        options = select.locator("option").all_text_contents()
        assert any("OpenRouter" in o for o in options)

    def test_status_bar(self, page):
        expect(page.locator(".status")).to_be_visible()


# ═══════════════════════ 自部署 API ═══════════════════════

class TestSelfDeployedAPI:
    """自部署 API 添加和管理"""

    def test_add_button_visible(self, page):
        api_label = page.locator("label:has-text('自部署 API')")
        plus_btn = api_label.locator("..").locator("button:has-text('+')")
        expect(plus_btn).to_be_visible()

    def test_add_button_opens_modal(self, page):
        api_label = page.locator("label:has-text('自部署 API')")
        api_label.locator("..").locator("button:has-text('+')").click()

        expect(page.get_by_text("添加自定义 API")).to_be_visible()
        expect(page.locator("input[placeholder^='名称']")).to_be_visible()
        expect(page.locator("input[placeholder^='API 地址']")).to_be_visible()
        expect(page.locator("input[placeholder^='API Key']")).to_be_visible()
        expect(page.locator("input[placeholder^='模型名称']")).to_be_visible()

    def test_cancel_closes_modal(self, page):
        api_label = page.locator("label:has-text('自部署 API')")
        api_label.locator("..").locator("button:has-text('+')").click()
        expect(page.get_by_text("添加自定义 API")).to_be_visible()

        page.get_by_role("button", name="取消").first.click()
        expect(page.get_by_text("添加自定义 API")).not_to_be_visible()

    def test_add_custom_provider_appears_in_dropdown(self, page):
        add_custom_provider(page, "我的 GPU", "https://my-gpu.example.com/v1",
                            "sk-test-key-123", "google/gemma-4-26b-it")
        expect(page.get_by_text("添加自定义 API")).not_to_be_visible()

        select = page.locator("select").first
        options = select.locator("option").all_text_contents()
        assert any("我的 GPU" in o for o in options)

    def test_custom_provider_persists_in_localstorage(self, page):
        add_custom_provider(page, "持久化测试", "https://persist.example.com/v1")

        stored = page.evaluate("localStorage.getItem('custom_providers')")
        assert stored is not None
        assert "持久化测试" in stored

    def test_select_custom_provider_using_select_option(self, page):
        """使用 select_option 选择自定义 provider"""
        add_custom_provider(page, "选择测试", "https://select-test.example.com/v1",
                            "sk-select", "test-model")
        # 使用 select_option 触发 change 事件
        select_provider_by_text(page, "选择测试")

        selected = page.locator("select").first.input_value()
        assert selected.startswith("custom_"), f"应选中 custom_ provider: {selected}"


# ═══════════════════════ 前端模式 ═══════════════════════

class TestFrontendMode:
    """前端模式切换"""

    def test_checkbox_exists_and_toggle(self, page):
        checkbox = page.locator("input[type='checkbox']").first
        expect(checkbox).to_be_visible()
        checkbox.check()
        expect(checkbox).to_be_checked()
        checkbox.uncheck()
        expect(checkbox).not_to_be_checked()


# ═══════════════════════ 聊天交互 ═══════════════════════

class TestChatInteraction:
    """聊天发送 & 示例"""

    def test_input_and_buttons_visible(self, page):
        input_bar = page.locator(".input-bar")
        expect(input_bar).to_be_visible()
        expect(input_bar.locator("input")).to_be_visible()
        expect(input_bar.get_by_role("button", name="发送")).to_be_visible()
        expect(input_bar.get_by_role("button", name="清空")).to_be_visible()
        expect(input_bar.get_by_role("button", name="模拟")).to_be_visible()

    def test_example_chip_fills_input(self, page):
        example_btns = page.locator(".example-chip")
        count = example_btns.count()
        assert count > 0
        example_btns.first.click()
        # 点击后等待一下让 DOM 更新
        page.wait_for_timeout(500)
        input_el = page.locator(".input-bar input")
        val = input_el.input_value()
        assert len(val) > 0

    def test_simulate_generates_messages(self, page):
        page.get_by_role("button", name="模拟").click()
        msgs = page.locator(".msg")
        expect(msgs.first).to_be_visible(timeout=5000)


# ═══════════════════════ 配置面板 ═══════════════════════

class TestConfigPanel:
    """⚙️ 配置面板"""

    def test_config_button_opens_panel(self, page):
        page.get_by_role("button", name="配置").click()
        expect(page.locator("text=📡 API 连通性").first).to_be_visible()
        expect(page.locator("text=🔗 n8n 实例").first).to_be_visible()

    def test_config_tabs_switch(self, page):
        page.get_by_role("button", name="配置").click()
        expect(page.locator("text=📡 API 连通性").first).to_be_visible()
        page.get_by_text("🔗 n8n 实例").first.click()
        expect(page.locator("text=📡 API 连通性").first).to_be_visible()


# ═══════════════════════ 自部署 API — 端到端流程 ═══════════════════════

class TestCustomProviderFullFlow:
    """完整流程：添加 → 选中 → 发送 (验证请求体)"""

    def test_chat_payload_includes_custom_fields(self, page):
        """验证发送时给后端传 custom_url / custom_key / custom_model"""
        captured = []

        def on_request(request):
            if request.url.endswith("/api/chat") and request.method == "POST":
                captured.append(request)

        page.on("request", on_request)

        add_custom_provider(page, "E2E Test API", "https://e2e-test.example.com/v1",
                            "sk-e2e-key", "e2e-model")
        select_provider_by_text(page, "E2E Test API")

        page.locator(".input-bar input").fill("创建一个 webhook 工作流")
        page.get_by_role("button", name="发送").click()
        page.wait_for_timeout(3000)

        assert len(captured) > 0, "应有 /api/chat 请求被拦截"
        body = json.loads(captured[0].post_data)
        assert body.get("provider", "").startswith("custom_")
        assert body.get("custom_url") == "https://e2e-test.example.com/v1"
        assert body.get("custom_key") == "sk-e2e-key"
        assert body.get("custom_model") == "e2e-model"

    def test_frontend_mode_direct_call(self, page):
        """前端模式下自定义 provider 应尝试直连外部 API"""
        # 拦截外部域名请求
        page.route(re.compile(r"direct-test\.example\.com"), lambda route: route.abort())

        add_custom_provider(page, "Direct API", "https://direct-test.example.com/v1", "sk-direct")
        # 开启前端模式
        page.locator("input[type='checkbox']").first.check()
        select_provider_by_text(page, "Direct API")

        captured = []

        def on_request(request):
            if "direct-test.example.com" in request.url:
                captured.append(request)

        page.on("request", on_request)

        page.locator(".input-bar input").fill("你好")
        page.get_by_role("button", name="发送").click()

        # 等待请求被拦截和捕获
        page.wait_for_timeout(1000)

        assert len(captured) > 0, "前端模式应直连自定义 API"
        assert "/chat/completions" in captured[0].url
