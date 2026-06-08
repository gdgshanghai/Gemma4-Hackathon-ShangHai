"""深读搜索结果 TopN：优先 Playwright 浏览器；不可用时由 search 模块 HTTP 降级。"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def playwright_read_top_results(
    query: str, results: list[dict[str, Any]], *, max_pages: int
) -> str:
    from playwright.async_api import async_playwright

    top = results[:max_pages]
    parts: list[str] = [f"【Playwright 深读：{query}，共 {len(top)} 页】"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        for i, item in enumerate(top, 1):
            title = item.get("title", "")
            url = item.get("url", "")
            page = await context.new_page()
            body = ""
            try:
                if not url:
                    body = "(无 URL)"
                else:
                    await page.goto(url, wait_until="domcontentloaded", timeout=35000)
                    await page.wait_for_timeout(1500)
                    body = await page.evaluate(
                        """() => {
                        const rm = s => { s.querySelectorAll('script,style,nav,footer,header').forEach(n=>n.remove()); return s; };
                        const el = document.querySelector('article') || document.querySelector('main') || document.body;
                        return rm(el).innerText.slice(0, 3500);
                    }"""
                    )
                    if not body or len(body.strip()) < 60:
                        body = (item.get("snippet") or "") + "\n(页面正文较少，已附搜索摘要)"
            except Exception as e:
                body = f"(页面打开失败: {e})\n摘要: {item.get('snippet', '')}"
            finally:
                await page.close()
            parts.append(f"\n--- [{i}] {title} ---\nURL: {url}\n{body.strip()}")
        await browser.close()

    parts.append(
        "\n【说明】请综合以上各来源回答；区分现实关系与网络梗/模因。"
    )
    return "\n".join(parts)
