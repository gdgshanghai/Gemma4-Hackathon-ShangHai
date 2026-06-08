"""联网搜索：国内百度/搜狗取 TopN → 自动 browser-use 深读（不熟悉时由模型触发 web_search）。"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from gemma_api.config import (
    AUTO_BROWSER_USE,
    BROWSER_USE_ENABLE_EXTENSIONS,
    BROWSER_USE_MAX_STEPS,
    BROWSER_USE_MODEL,
    BROWSER_USE_IDLE_WAIT_SEC,
    BROWSER_USE_WAIT_BETWEEN_ACTIONS,
    ENABLE_BROWSER_USE,
    MAX_SEARCH_RESULTS,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    QIANFAN_ENABLE_DEEP_SEARCH,
    QIANFAN_SEARCH_API_KEY,
    QIANFAN_SEARCH_API_KEY_FILE,
    QIANFAN_SEARCH_MODEL,
    QIANFAN_SEARCH_RECENCY_FILTER,
    QIANFAN_SEARCH_SOURCE,
    SEARCH_BACKENDS,
    SEARCH_READ_TOP_N,
    SEARCH_TIMEOUT,
)

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_BACKENDS: dict[str, Any] = {}
_FORCED_BACKENDS = ("baidu_ai", "sogou", "ddg")
_QIANFAN_KEY_CACHE: str | None = None


def _resolve_qianfan_api_key() -> str:
    """
    自动解析 QIANFAN API Key：
    1) 环境变量 QIANFAN_SEARCH_API_KEY
    2) 文件 QIANFAN_SEARCH_API_KEY_FILE（默认 /root/Gemma/.qianfan_search_api_key）
    """
    global _QIANFAN_KEY_CACHE
    if _QIANFAN_KEY_CACHE:
        return _QIANFAN_KEY_CACHE
    if QIANFAN_SEARCH_API_KEY:
        _QIANFAN_KEY_CACHE = QIANFAN_SEARCH_API_KEY
        return _QIANFAN_KEY_CACHE
    key_file = Path(QIANFAN_SEARCH_API_KEY_FILE)
    if key_file.exists():
        content = key_file.read_text(encoding="utf-8").strip()
        if content:
            _QIANFAN_KEY_CACHE = content
            return _QIANFAN_KEY_CACHE
    return ""


def _is_high_risk_fact_query(query: str) -> bool:
    q = query.strip()
    return bool(
        re.search(
            r"(是否去世|去世了吗|还活着|在世吗|逝世|死亡|身亡|病逝|离世)",
            q,
        )
    )


def _expand_query(query: str) -> str:
    # 按用户要求：调用搜索时严格使用原始 query，不做自动关键词扩展。
    return query.strip()


def format_search_results(results: list[dict[str, Any]], *, source: str) -> str:
    if not results:
        return f"未找到相关搜索结果。（来源：{source}）"
    lines = [f"【搜索引擎：{source}】"]
    for i, r in enumerate(results, 1):
        lines.append(
            f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('snippet', '')}"
        )
    return "\n\n".join(lines)


def format_page_extractions(
    extractions: list[tuple[int, str, str, str]], *, mode: str
) -> str:
    """extractions: (index, title, url, body)"""
    lines = [f"【{mode}：已阅读前 {len(extractions)} 条链接正文】"]
    for idx, title, url, body in extractions:
        lines.append(f"\n--- 来源 [{idx}] {title} ---\nURL: {url}\n{body}")
    return "\n".join(lines)


def _parse_baidu(html: str, max_results: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for div in soup.select("div.result, div.c-container, div[tpl]"):
        h3 = div.select_one("h3")
        if not h3:
            continue
        a = h3.select_one("a") or h3.find("a")
        title = (a.get_text(strip=True) if a else h3.get_text(strip=True)) or ""
        if not title or title in seen:
            continue
        seen.add(title)
        url = (a.get("href", "") if a else "") or ""
        snippet = ""
        for sel in (
            ".c-abstract",
            ".content-right_8Zs40",
            "span.content-right_8Zs40",
            ".c-span-last",
            "div.c-span9",
        ):
            node = div.select_one(sel)
            if node:
                snippet = node.get_text(" ", strip=True)
                break
        if not snippet:
            snippet = div.get_text(" ", strip=True)
            snippet = re.sub(r"\s+", " ", snippet)
            if title in snippet:
                snippet = snippet.replace(title, "", 1).strip()
        items.append({"title": title, "url": url, "snippet": snippet[:400]})
        if len(items) >= max_results:
            break
    return items


def _parse_sogou(html: str, max_results: int) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for div in soup.select(".vrwrap, .rb, .result"):
        h3 = div.select_one("h3")
        if not h3:
            continue
        a = h3.select_one("a") or h3.find("a")
        title = (a.get_text(strip=True) if a else h3.get_text(strip=True)) or ""
        if not title or title in seen:
            continue
        seen.add(title)
        url = (a.get("href", "") if a else "") or ""
        if url.startswith("/"):
            url = urljoin("https://www.sogou.com", url)
        snippet = ""
        for sel in (".str-info", ".str-text", "p.str-text", ".space-txt"):
            node = div.select_one(sel)
            if node:
                snippet = node.get_text(" ", strip=True)
                break
        items.append({"title": title, "url": url, "snippet": snippet[:400]})
        if len(items) >= max_results:
            break
    return items


async def search_baidu(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    n = max_results or MAX_SEARCH_RESULTS
    async with httpx.AsyncClient(
        timeout=SEARCH_TIMEOUT, follow_redirects=True, headers=_BROWSER_HEADERS
    ) as client:
        r = await client.get("https://www.baidu.com/s", params={"wd": query})
        r.raise_for_status()
        return _parse_baidu(r.text, n)


async def search_sogou(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    n = max_results or MAX_SEARCH_RESULTS
    async with httpx.AsyncClient(
        timeout=SEARCH_TIMEOUT, follow_redirects=True, headers=_BROWSER_HEADERS
    ) as client:
        r = await client.get("https://www.sogou.com/web", params={"query": query})
        r.raise_for_status()
        return _parse_sogou(r.text, n)


async def search_baidu_ai(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    """
    百度千帆智能搜索生成：
    POST /v2/ai_search/chat/completions
    """
    api_key = _resolve_qianfan_api_key()
    if not api_key:
        raise RuntimeError("未配置 QIANFAN_SEARCH_API_KEY")

    n = max_results or MAX_SEARCH_RESULTS
    payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": query}],
        "stream": False,
        "model": QIANFAN_SEARCH_MODEL,
        "search_source": QIANFAN_SEARCH_SOURCE or "baidu_search_v2",
        "search_mode": "required",
        "enable_deep_search": QIANFAN_ENABLE_DEEP_SEARCH,
        "enable_corner_markers": True,
        "resource_type_filter": [{"type": "web", "top_k": max(1, min(n, 10))}],
    }
    if QIANFAN_SEARCH_RECENCY_FILTER:
        payload["search_recency_filter"] = QIANFAN_SEARCH_RECENCY_FILTER

    headers = {
        "Content-Type": "application/json",
        # 文档示例推荐该头
        "X-Appbuilder-Authorization": f"Bearer {api_key}",
    }
    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(
                "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        except httpx.ReadTimeout:
            # 针对千帆 API 偶发的 ReadTimeout 做降级兜底返回（不报错打断流程）
            logger.warning("baidu_ai 接口发生 ReadTimeout，直接视为无结果返回")
            return []

    refs = data.get("references") or []
    if not refs:
        # 便于排查：接口成功但无引用时输出关键字段
        summary = (data.get("message") or "")[:300]
        raise RuntimeError(
            f"baidu_ai 返回空 references（code={data.get('code')}, message={summary}）"
        )
    out: list[dict[str, Any]] = []
    for ref in refs:
        if ref.get("type") and ref.get("type") != "web":
            continue
        title = (ref.get("title") or "").strip()
        url = (ref.get("url") or "").strip()
        snippet = (ref.get("content") or "").strip()
        if not title and not url:
            continue
        out.append(
            {
                "title": title or (url[:120] if url else "未命名来源"),
                "url": url,
                "snippet": snippet[:400],
            }
        )
        if len(out) >= n:
            break
    return out


def search_duckduckgo(query: str, max_results: int | None = None) -> list[dict[str, Any]]:
    from duckduckgo_search import DDGS

    n = max_results or MAX_SEARCH_RESULTS
    results: list[dict[str, Any]] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, region="cn-zh", max_results=n):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                }
            )
    return results


_BACKENDS.update(
    {
        "baidu_ai": search_baidu_ai,
        "baidu": search_baidu,
        "sogou": search_sogou,
        "ddg": lambda q, n=None: asyncio.to_thread(search_duckduckgo, q, n),
        "duckduckgo": lambda q, n=None: asyncio.to_thread(search_duckduckgo, q, n),
    }
)


async def search_cn_results(
    query: str, max_results: int | None = None
) -> tuple[list[dict[str, Any]], str]:
    """返回 (结果列表, 来源名)。"""
    n = max_results or MAX_SEARCH_RESULTS
    errors: list[str] = []
    # 安全兜底：即便环境变量包含其它后端，也仅允许 baidu_ai。
    for name in _FORCED_BACKENDS:
        fn = _BACKENDS.get(name)
        if not fn:
            continue
        try:
            if name in ("ddg", "duckduckgo"):
                results = await fn(query, n)
            else:
                results = await fn(query, n)
            if results:
                return results, name
            errors.append(f"{name}: 无结果")
        except Exception as e:
            logger.warning("搜索后端 %s 失败: %r", name, e)
            errors.append(f"{name}: {repr(e)}")
    return [], "none"


async def search_cn(query: str, max_results: int | None = None) -> tuple[str, str]:
    results, source = await search_cn_results(query, max_results)
    if results:
        return format_search_results(results, source=source), source
    return "搜索失败: 无可用国内搜索引擎结果", "none"


def _html_to_text(html: str, max_chars: int = 3500) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:max_chars]


async def _fetch_one_page(
    client: httpx.AsyncClient, idx: int, item: dict[str, Any]
) -> tuple[int, str, str, str]:
    title = item.get("title", "")
    url = item.get("url", "")
    if not url:
        return idx, title, url, "(无 URL)"
    try:
        r = await client.get(url)
        r.raise_for_status()
        body = _html_to_text(r.text)
        if len(body) < 80:
            body = item.get("snippet", "") or "(正文过短，可能需浏览器渲染)"
        return idx, title, url, body
    except Exception as e:
        snippet = item.get("snippet", "")
        return idx, title, url, f"(HTTP 抓取失败: {e})\n摘要: {snippet}"


async def fetch_pages_httpx(results: list[dict[str, Any]]) -> list[tuple[int, str, str, str]]:
    """并行 HTTP 抓取搜索结果链接正文（browser-use 不可用时的降级）。"""
    top = results[:SEARCH_READ_TOP_N]
    async with httpx.AsyncClient(
        timeout=SEARCH_TIMEOUT,
        follow_redirects=True,
        headers=_BROWSER_HEADERS,
        limits=httpx.Limits(max_connections=5),
    ) as client:
        tasks = [_fetch_one_page(client, i + 1, r) for i, r in enumerate(top)]
        return await asyncio.gather(*tasks)


async def browser_read_top_results(
    query: str, results: list[dict[str, Any]]
) -> str:
    """
    深读 TopN：优先 browser-use（Py≥3.11）；否则 Playwright 直读（Py3.10 可用）。
    """
    top_n = SEARCH_READ_TOP_N

    # 1) browser-use + LLM Agent（需 Python 3.11+）
    try:
        from browser_use import Agent  # type: ignore
        from browser_use.llm import ChatOllama  # type: ignore

        top = results[:top_n]
        listing = "\n".join(
            f"{i + 1}. 标题: {r.get('title', '')}\n   URL: {r.get('url', '')}"
            for i, r in enumerate(top)
        )
        from browser_use.browser.profile import BrowserProfile

        bu_model = BROWSER_USE_MODEL or OLLAMA_MODEL
        llm = ChatOllama(model=bu_model, host=OLLAMA_HOST)
        n = len(top)
        task = (
            f"【任务】针对「{query}」阅读下列 {n} 个已抓取的搜索结果链接，写中文综合摘要。\n\n"
            f"【链接列表（禁止打开百度/搜狗首页或搜索页，仅访问下列 URL）】\n{listing}\n\n"
            f"1. 按序号 1~{n} 逐个用 navigate 打开上述 URL 并阅读正文。\n"
            "2. 区分现实关系与网络梗/模因；若涉及「巧乐兹梗」等须说明含义与由来。\n"
            "3. 输出【深度阅读摘要】【分条要点 1~N】【参考链接】（无论找到与否，务必严格输出这三个标题）。\n"
            "禁止未打开网页就臆测；遇验证码则跳过该链接并注明。"
        )
        profile = BrowserProfile(
            headless=True,
            enable_default_extensions=BROWSER_USE_ENABLE_EXTENSIONS,
            wait_between_actions=BROWSER_USE_WAIT_BETWEEN_ACTIONS,
            wait_for_network_idle_page_load_time=BROWSER_USE_IDLE_WAIT_SEC,
            minimum_wait_page_load_time=0.1,
            highlight_elements=False,
            filter_highlight_ids=True,
        )
        progress = {"seen": set(), "total": n}

        async def on_step_start(browser_state, model_output, step_number):
            # Browser-use 执行每步时输出可见进度，便于前端SSE展示。
            try:
                idx = int(step_number)
            except Exception:
                idx = len(progress["seen"]) + 1
            progress["seen"].add(idx)
            logger.info(
                "[browser_use_progress] query=%s step=%s/%s",
                query[:80],
                idx,
                BROWSER_USE_MAX_STEPS,
            )
            return None

        agent = Agent(
            task=task,
            llm=llm,
            browser_profile=profile,
            use_vision=False,
            use_judge=False,
            flash_mode=True,
            register_new_step_callback=on_step_start,
        )
        history = await agent.run(max_steps=BROWSER_USE_MAX_STEPS)
        final = history.final_result() if hasattr(history, "final_result") else str(history)
        if final and len(final.strip()) >= 50:
            return final.strip()
    except ImportError:
        logger.info("browser-use 未安装，尝试 Playwright 直读")
    except Exception as e:
        logger.warning("browser-use Agent 失败: %s", e)

    # 2) Playwright 无 Agent 直读（推荐 Py3.10 环境）
    from gemma_api.services.deep_read import playwright_read_top_results

    return await playwright_read_top_results(query, results, max_pages=top_n)


def _should_deep_read() -> bool:
    return AUTO_BROWSER_USE or ENABLE_BROWSER_USE


async def iter_web_search_events(query: str):
    """流式推送搜索各阶段状态。"""
    q = _expand_query(query)
    top_n = SEARCH_READ_TOP_N

    yield {
        "event": "status",
        "phase": "search",
        "message": f"正在国内搜索（{','.join(SEARCH_BACKENDS)}）…",
        "query": q,
    }
    results, source = await search_cn_results(q, max_results=top_n)
    if not results:
        yield {"event": "error", "phase": "search", "message": "国内搜索引擎未返回结果"}
        return

    yield {
        "event": "status",
        "phase": "search_done",
        "message": f"检索完成（{source}），共 {len(results)} 条",
        "source": source,
        "count": len(results),
    }

    header = format_search_results(results, source=source)
    body, mode = header, "snippet-only"
    high_risk_fact = _is_high_risk_fact_query(q)

    if high_risk_fact:
        # 生死/死亡等高风险事实：默认开启深读，至少阅读 1 篇再回答。
        deep_n = min(1, len(results))
        yield {
            "event": "status",
            "phase": "fact_check_mode",
            "message": f"高风险事实核验：已开启深读，至少阅读 {deep_n} 篇来源。",
        }
        try:
            yield {
                "event": "status",
                "phase": "deep_read",
                "message": f"深读进行中：准备读取第 1/{deep_n} 篇来源（browser-use）…",
            }
            deep = await browser_read_top_results(q, results[:deep_n])
            body = (
                header
                + "\n\n"
                + format_page_extractions(
                    [
                        (
                            i + 1,
                            r.get("title", ""),
                            r.get("url", ""),
                            "(见下方 browser-use 摘要)",
                        )
                        for i, r in enumerate(results[:deep_n])
                    ],
                    mode="browser-use",
                )
                + "\n\n"
                + deep
            )
            mode = "browser-use-agent" if "【深度阅读摘要】" in deep else "browser-deep-read"
            yield {
                "event": "status",
                "phase": "deep_read_done",
                "message": f"高风险事实深读完成（已读 {deep_n} 篇）",
                "mode": mode,
            }
        except ImportError:
            logger.warning("未安装 Playwright/browser-use，降级 HTTP 抓取")
            pages = await fetch_pages_httpx(results[:deep_n])
            body = header + "\n\n" + format_page_extractions(pages, mode="HTTP 正文抓取")
            mode = "httpx-fetch"
        except Exception as e:
            logger.warning("高风险事实深读失败，降级 HTTP 抓取: %s", e)
            try:
                pages = await fetch_pages_httpx(results[:deep_n])
                body = header + "\n\n" + format_page_extractions(
                    pages, mode="HTTP 正文抓取"
                )
                mode = "httpx-fetch"
            except Exception as e2:
                body = header + f"\n\n【深读失败】{e2}"
                mode = "snippet-only"
    elif _should_deep_read():
        yield {
            "event": "status",
            "phase": "deep_read",
            "message": f"正在深读 Top {top_n} 条链接（Playwright / browser-use）…",
        }
        try:
            deep = await browser_read_top_results(q, results)
            body = (
                header
                + "\n\n"
                + format_page_extractions(
                    [
                        (
                            i + 1,
                            r.get("title", ""),
                            r.get("url", ""),
                            "(见下方 browser-use 摘要)",
                        )
                        for i, r in enumerate(results[:top_n])
                    ],
                    mode="browser-use",
                )
                + "\n\n"
                + deep
            )
            mode = "browser-use-agent" if "【深度阅读摘要】" in deep else "browser-deep-read"
            yield {
                "event": "status",
                "phase": "deep_read_done",
                "message": "网页深读完成",
                "mode": mode,
            }
        except ImportError:
            logger.warning("未安装 Playwright/browser-use，降级 HTTP 抓取")
            yield {
                "event": "status",
                "phase": "deep_read_fallback",
                "message": "深读降级为 HTTP 抓取正文",
            }
            pages = await fetch_pages_httpx(results)
            body = header + "\n\n" + format_page_extractions(pages, mode="HTTP 正文抓取")
            mode = "httpx-fetch"
        except Exception as e:
            logger.warning("browser 深读失败，降级 HTTP 抓取: %s", e)
            yield {
                "event": "status",
                "phase": "deep_read_fallback",
                "message": f"深读失败，HTTP 抓取：{e}",
            }
            try:
                pages = await fetch_pages_httpx(results)
                body = header + "\n\n" + format_page_extractions(
                    pages, mode="HTTP 正文抓取"
                )
                mode = "httpx-fetch"
            except Exception as e2:
                body = header + f"\n\n【深读失败】{e2}"
                mode = "snippet-only"
    else:
        try:
            pages = await fetch_pages_httpx(results)
            body = header + "\n\n" + format_page_extractions(pages, mode="HTTP 正文抓取")
            mode = "httpx-fetch"
        except Exception as e:
            body = header + f"\n\n【抓取失败】{e}"
            mode = "snippet-only"

    yield {
        "event": "tool_result",
        "phase": "search",
        "preview": body[:500],
        "deep_read": mode,
    }
    # 供调用方取完整结果
    yield {"event": "_search_complete", "text": body, "deep_read": mode}


async def web_search(query: str) -> tuple[str, str]:
    """
    模型调用 web_search（表示不熟悉）时的标准流程：
    1. 国内搜索 TopN
    2. 自动 browser-use 深读 TopN（默认开启）
    3. 失败则 HTTP 抓取正文降级

    返回 (检索文本, 深读模式)。
    """
    text, mode = "搜索失败: 国内搜索引擎未返回结果。", "none"
    async for ev in iter_web_search_events(query):
        if ev.get("event") == "_search_complete":
            text = ev["text"]
            mode = ev["deep_read"]
        elif ev.get("event") == "error":
            return ev.get("message", text), "none"
    return text, mode
