"""Gemma 4 n8n Agent — FastAPI 后端"""

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import N8nAgent
from api import get_client, check_health
from api.gemma_client import check_all_providers

# ── Provider 检查间隔（分钟）─────────────────────────
PROVIDER_CHECK_INTERVAL = int(os.environ.get("PROVIDER_CHECK_INTERVAL", "5"))
# 实际间隔为 PROVIDER_CHECK_INTERVAL ~ PROVIDER_CHECK_INTERVAL+1 分钟随机

# ── Provider 检查日志 ───────────────────────────────
import random
import time
provider_logs: list[dict] = []
MAX_LOGS = 100
n8n_logs: list[dict] = []

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="n8n Agent - Gemma 4")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

sessions: dict[str, N8nAgent] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    n8n_url: str | None = None
    n8n_api_key: str | None = None
    provider: str = "openrouter_26b"
    model: str = "google/gemma-4-26b-a4b-it"
    mode: str = "workflow"  # "workflow" | "chat"
    stream: bool = False
    custom_url: str | None = None  # 自定义 API 地址
    custom_key: str | None = None  # 自定义 API Key
    custom_model: str | None = None  # 自定义模型名称


class DeployRequest(BaseModel):
    workflow: dict
    n8n_url: str
    n8n_api_key: str


class ExecuteRequest(BaseModel):
    workflow_id: str
    n8n_url: str
    n8n_api_key: str


def get_agent(sid: str | None = None, provider: str = "openrouter_26b",
              model: str = "google/gemma-4-26b-it") -> N8nAgent:
    if sid and sid in sessions:
        return sessions[sid]
    client, resolved_model = get_client(provider)
    agent = N8nAgent(client=client, model=model or resolved_model)
    if sid:
        sessions[sid] = agent
    return agent


@app.get("/api/info")
def info():
    """静态服务信息（无需 API 连通）"""
    return {
        "name": "n8n Agent - Gemma 4",
        "version": "1.0.0",
        "providers": ["openrouter_26b", "openrouter_31b"],
        "check_interval_min": PROVIDER_CHECK_INTERVAL,
    }


@app.get("/api/health")
def health():
    ok = check_health()
    return {
        "status": "ok" if ok else "api_unavailable",
        "providers": ["openrouter_26b", "openrouter_31b"],
        "check_interval_min": PROVIDER_CHECK_INTERVAL,
    }


@app.get("/api/provider-status")
def provider_status():
    """检查所有 provider key 的连通性"""
    results = check_all_providers()
    # 记录日志
    ts = time.time()
    entry = {"time": ts, "results": dict(results)}
    provider_logs.append(entry)
    if len(provider_logs) > MAX_LOGS:
        provider_logs[:] = provider_logs[-MAX_LOGS:]
    # 返回带随机间隔信息
    base = PROVIDER_CHECK_INTERVAL
    return {
        "results": results,
        "next_check_min": f"{base}-{base+1}",
        "check_interval_min": base,
    }


@app.get("/api/provider-logs")
def get_provider_logs():
    """返回最近的 provider 检查记录"""
    return list(provider_logs)


@app.get("/api/default-instances")
def default_instances():
    raw = os.environ.get("N8N_DEFAULT_INSTANCES", "[]")
    builtin = [{"name": "Render 正式版", "url": "https://n8n-server-fepr.onrender.com", "key": "", "builtin": True}]
    try:
        env_list = json.loads(raw)
        if isinstance(env_list, list):
            # 返回给前端时不暴露 API Key
            clean = []
            for inst in env_list:
                clean.append({
                    "name": inst.get("name", ""),
                    "url": inst.get("url", ""),
                    "key": "",  # 不暴露给前端
                    "builtin": inst.get("builtin", False),
                })
            return builtin + clean
        return builtin
    except json.JSONDecodeError:
        return builtin


@app.get("/api/n8n-health")
def n8n_health():
    """检查所有默认 n8n 实例的连通性"""
    import httpx
    instances = default_instances()
    results = {}
    for inst in instances:
        url = inst["url"].rstrip("/") + "/healthz"
        try:
            r = httpx.get(url, timeout=5)
            ok = r.status_code == 200
            results[inst["url"]] = ok
            n8n_logs.append({
                "time": time.time(), "url": inst["url"], "status": r.status_code,
                "ok": ok, "error": None,
            })
        except Exception as e:
            results[inst["url"]] = False
            n8n_logs.append({
                "time": time.time(), "url": inst["url"], "status": None,
                "ok": False, "error": str(e),
            })
    if len(n8n_logs) > MAX_LOGS:
        n8n_logs[:] = n8n_logs[-MAX_LOGS:]
    return results


@app.get("/api/n8n-logs")
def get_n8n_logs():
    """返回 n8n 健康检查记录"""
    return list(reversed(n8n_logs))


@app.post("/api/chat")
def chat(req: ChatRequest):
    # 自定义 provider — 用前端传的 URL/Key 创建临时 client
    if req.custom_url:
        from openai import OpenAI as OpenAIClient
        client = OpenAIClient(base_url=req.custom_url, api_key=req.custom_key or "")
        resolved_model = req.custom_model or req.model or ""
    else:
        client, resolved_model = get_client(req.provider)

    if req.mode == "chat":
        if req.stream:
            return _stream_chat(req, client, resolved_model)
        try:
            from api import chat as simple_chat
            reply = simple_chat(
                messages=[{"role": "user", "content": req.message}],
                model=req.model or resolved_model,
                client=client,
            )
            return {"content": reply, "session_id": req.session_id, "provider": req.provider, "mode": "chat"}
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # workflow 模式
    agent = get_agent(req.session_id, req.provider, req.model)
    try:
        result = agent.run(req.message)
        # content 为空时有 workflow 则生成说明
        resp_content = result.get("content") or ""
        if not resp_content and result.get("workflow"):
            wf = result["workflow"]
            node_names = [n.get("name", "?") for n in wf.get("nodes", [])]
            resp_content = f"已生成工作流「{wf.get('name', '未命名')}」，包含 {len(wf.get('nodes', []))} 个节点：{' → '.join(node_names)}"
        return {
            "content": resp_content,
            "tool_calls": [
                {"name": tc["name"], "arguments": tc["arguments"]}
                for tc in result.get("tool_calls", [])
            ],
            "workflow": result.get("workflow"),
            "session_id": req.session_id,
            "provider": req.provider,
            "mode": "workflow",
        }
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _stream_chat(req: ChatRequest, client, resolved_model):
    """SSE 流式聊天"""
    import json as json_mod

    def event_stream():
        try:
            stream = client.chat.completions.create(
                model=req.model or resolved_model,
                messages=[{"role": "user", "content": req.message}],
                temperature=0.0,
                max_tokens=4096,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield f"data: {json_mod.dumps({'type': 'chunk', 'content': delta.content})}\n\n"
            yield f"data: {json_mod.dumps({'type': 'result', 'data': {'content': '', 'session_id': req.session_id, 'provider': req.provider, 'mode': 'chat'}})}\n\n"
        except Exception as e:
            yield f"data: {json_mod.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


import string

WEBHOOK_PATHS: dict[str, str] = {}  # workflow_id → webhook_path

# ── 默认 n8n 实例（Key 只存后端，不暴露前端）────────
_N8N_DEFAULT_KEY_MAP: dict[str, str] = {}  # url → api_key


def _load_default_n8n_keys():
    """从环境变量加载默认 n8n 实例的 API Key，仅后端使用"""
    raw = os.environ.get("N8N_DEFAULT_INSTANCES", "[]")
    try:
        instances = json.loads(raw)
        if isinstance(instances, list):
            for inst in instances:
                url = inst.get("url", "").rstrip("/")
                key = inst.get("key", "")
                if url and key:
                    _N8N_DEFAULT_KEY_MAP[url] = key
    except json.JSONDecodeError:
        pass


def _resolve_n8n_key(n8n_url: str, api_key: str) -> str:
    """如果是默认实例且前端没传 key，从后端配置补上"""
    if api_key:
        return api_key
    url = n8n_url.rstrip("/")
    return _N8N_DEFAULT_KEY_MAP.get(url, api_key)


_load_default_n8n_keys()


def _add_webhook_trigger(wf: dict) -> str:
    """为工作流添加 Webhook 触发器节点，返回 webhook path"""
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    # 如果已有 Webhook 节点，确保 httpMethod 设置为 POST
    for n in nodes:
        if n.get("type") in ("n8n-nodes-base.webhook",):
            params = n.get("parameters", {})
            if not params.get("httpMethod"):
                params["httpMethod"] = "POST"
                n["parameters"] = params
            path = params.get("path", f"ping-{''.join(random.choices(string.ascii_lowercase, k=6))}")
            return path

    # 将 ManualTrigger 替换为 Webhook
    for n in nodes:
        if n.get("type") in ("n8n-nodes-base.manualTrigger",):
            webhook_path = f"ping-{''.join(random.choices(string.ascii_lowercase, k=6))}"
            n["type"] = "n8n-nodes-base.webhook"
            n["typeVersion"] = 1
            n["parameters"] = {"httpMethod": "POST", "path": webhook_path, "options": {}}
            return webhook_path

    # 生成唯一 path
    webhook_path = f"ping-{''.join(random.choices(string.ascii_lowercase, k=6))}"

    # 调整现有节点坐标腾出空间
    for n in nodes:
        pos = n.get("position", [0, 0])
        if pos[0] < 300:
            n["position"] = [pos[0] + 300, pos[1]]

    # 插入 Webhook 节点
    webhook_node = {
        "name": "Webhook (Trigger)",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 1,
        "position": [0, 250],
        "parameters": {
            "httpMethod": "POST",
            "path": webhook_path,
            "options": {},
        },
    }
    nodes.insert(0, webhook_node)

    # 更新 connections: 原 0→1 改为 webhook→0
    new_conn = {}
    for old_first_name, first_node_conn in connections.items():
        new_conn[old_first_name] = first_node_conn
    new_conn[webhook_node["name"]] = {"main": [[{"node": nodes[1]["name"], "type": "1", "index": 0}]]}

    wf["nodes"] = nodes
    wf["connections"] = new_conn
    return webhook_path


@app.post("/api/deploy")
def deploy(req: DeployRequest):
    import httpx
    api_key = _resolve_n8n_key(req.n8n_url, req.n8n_api_key)
    headers = {
        "X-N8N-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    wf = dict(req.workflow)
    wf.pop("version", None)
    wf.pop("active", None)
    nodes = wf.get("nodes", [])

    # 清理节点中 n8n 不接受的额外字段
    ALLOWED_NODE_KEYS = {"name", "type", "typeVersion", "position", "parameters", "id", "webhookId", "notes", "notesFlow", "onError", "continueOnFail", "credentials", "alwaysOutputData"}
    for n in nodes:
        for k in list(n.keys()):
            if k not in ALLOWED_NODE_KEYS:
                n.pop(k, None)
        n["typeVersion"] = n.get("typeVersion", 1)

    # 修正未知节点类型为 n8n 支持的等效类型
    TYPE_MAP = {
        "debugLoop": "code",
        "readWriteFile": "code",
        "writeBinaryFile": "code",
        "debug": "code",
    }
    for n in nodes:
        t = n.get("type", "")
        for old, new in TYPE_MAP.items():
            if t.endswith(old):
                n["type"] = f"n8n-nodes-base.{new}"
                if new == "code":
                    n["parameters"]["jsCode"] = n["parameters"].pop("jsCode", "console.log($json);") or "console.log($json);"
                break

    # 自动添加 Webhook 触发器 + 转换 connections 格式
    webhook_path = _add_webhook_trigger(wf)
    nodes = wf.get("nodes", [])
    old_conn = wf.get("connections", {})
    new_conn = {}
    for src_key, outputs in old_conn.items():
        if isinstance(src_key, str) and not any(n["name"] == src_key for n in nodes):
            continue  # 跳过已被替换的旧连接键
        src_name = src_key
        new_outputs = {}
        for out_key, targets in outputs.items():
            if isinstance(targets, list):
                new_targets = []
                if len(targets) > 0 and isinstance(targets[0], list):
                    for t in targets[0]:
                        if isinstance(t, dict) and "node" in t:
                            new_targets.append(t)
                        elif isinstance(t, (int, float)):
                            tidx = int(t)
                            tname = nodes[tidx]["name"] if tidx < len(nodes) else str(tidx)
                            new_targets.append({"node": tname, "type": "1", "index": 0})
                else:
                    for t in targets:
                        if isinstance(t, (int, float)):
                            tidx = int(t)
                            tname = nodes[tidx]["name"] if tidx < len(nodes) else str(tidx)
                            new_targets.append({"node": tname, "type": "1", "index": 0})
                        elif isinstance(t, dict):
                            new_targets.append(t)
                new_outputs["main"] = [new_targets]
            elif isinstance(targets, dict):
                new_outputs[out_key] = targets
            else:
                new_outputs[out_key] = targets
        new_conn[src_name] = new_outputs
    wf["connections"] = new_conn
    if "settings" not in wf:
        wf["settings"] = {}

    url = f"{req.n8n_url.rstrip('/')}/api/v1/workflows"
    try:
        with httpx.Client() as client:
            resp = client.post(url, json=wf, headers=headers, timeout=30)
            if resp.status_code in (200, 201):
                result = resp.json()
                wf_id = result.get("id", "")
                # 激活工作流（使 webhook 生效）
                try:
                    activate_url = f"{req.n8n_url.rstrip('/')}/api/v1/workflows/{wf_id}/activate"
                    act_resp = client.post(activate_url, headers=headers, timeout=10)
                    if webhook_path:
                        # 使用 webhook 节点的 path 参数作为 URL，确保与 n8n 注册一致
                        WEBHOOK_PATHS[wf_id] = webhook_path
                        result["webhook_url"] = f"{req.n8n_url.rstrip('/')}/webhook/{webhook_path}"
                    result["activated"] = act_resp.status_code in (200, 201)
                except Exception:
                    result["activated"] = False
                return {"status": "ok", "workflow": result}
            elif resp.status_code == 401:
                raise HTTPException(status_code=401, detail="API Key 无效，请检查")
            else:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"无法连接到 {req.n8n_url}")


@app.post("/api/execute-workflow")
def execute_workflow(req: ExecuteRequest):
    """触发已部署的 n8n 工作流执行（POST 到 webhook 地址）"""
    import httpx
    webhook_path = WEBHOOK_PATHS.get(req.workflow_id)
    if not webhook_path:
        raise HTTPException(status_code=400, detail="该工作流没有可触发的 webhook 路径")

    webhook_url = f"{req.n8n_url.rstrip('/')}/webhook/{webhook_path}"
    try:
        with httpx.Client() as client:
            # 尝试 POST，如果返回 404 则回退到 GET
            resp = client.post(webhook_url, json={"ping": True, "timestamp": __import__("time").time()}, timeout=30)
            if resp.status_code == 200:
                return {"status": "ok", "execution": resp.json(), "message": "工作流已触发执行，ping 已发送"}
            elif resp.status_code == 404:
                # 可能是 GET webhook，尝试 GET
                resp2 = client.get(webhook_url, timeout=30)
                if resp2.status_code == 200:
                    return {"status": "ok", "execution": resp2.json(), "message": "工作流已触发执行，ping 已发送 (GET)"}
            raise HTTPException(status_code=resp.status_code, detail=f"执行失败: {resp.text}")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"无法连接到 webhook: {webhook_url}")
@app.post("/api/reset")
def reset(session_id: str | None = None):
    if session_id and session_id in sessions:
        sessions[session_id].reset()
    return {"status": "ok"}


# ── 静态文件 ─────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>n8n Agent</h1><p>Frontend not found</p>")
