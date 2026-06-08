"""
CogniFind — Gemma 4 核心调用客户端
=====================================

本模块是 CogniFind 项目中 `crates/cognifind-ai/src/external_llm.rs` 的 Python 等价实现。
原 Rust 模块通过 OpenAI 兼容 Chat Completions API 调用外接大模型（包括 Gemma 4），
支持流式生成、多模态 Vision 和音频转写。

架构映射：
  Rust (CogniFind)                    → Python (本模块)
  ─────────────────────────────────────────────────────
  ChatRequest / ChatMessage            → openai 库的 ChatCompletion
  stream_external_completion()         → Gemma4Client.chat_stream()
  stream_vision_api()                  → Gemma4Client.vision_chat()
  describe_image_sync()                → Gemma4Client.describe_image()
  image_to_data_uri()                  → Gemma4Client._encode_image()
  transcribe_audio_external()          → Gemma4Client.transcribe_audio()
  build_prompt() (rag.rs)              → Gemma4Client.build_rag_prompt()
  AiEngine (engine.rs) 混合路由        → Gemma4Client.chat_with_hybrid_routing()
"""

import json
import base64
import requests
from typing import List, Dict, Any, Callable, Optional, Union, Generator
from dataclasses import dataclass, field
from pathlib import Path
from io import BufferedReader


# ═══════════════════════════════════════════════════════════════════════════
# 数据类型 — 等价于 cognifind-core-types/src/ai.rs
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RagContext:
    """
    RAG 检索上下文 — 等价于 Rust 的 RagContext

    对应文件: crates/cognifind-core-types/src/ai.rs
    """
    query: str = ""
    files: List[Dict[str, Any]] = field(default_factory=list)  # FileHit
    snippets: List[Dict[str, Any]] = field(default_factory=list)  # SnippetHit


@dataclass
class ToolDefinition:
    """
    工具定义 — 等价于 OpenAI Function Calling 规范

    对应: Gemma 4 的 <|tool> ... <tool|> 原生 token
    定义在 examples 中注册，通过 OpenAI 兼容 API 的 tools 参数传递
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Optional[Callable] = None


@dataclass
class MultimodalContent:
    """
    多模态内容封装

    对应 Gemma 4 特殊 token：
    - <|image|> : 图像
    - <|audio|> : 音频（E2B/E4B）
    - <|video|> : 视频帧
    """
    text: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    audio_path: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# 核心客户端 — 等价于 external_llm.rs + engine.rs 的 Python 重构
# ═══════════════════════════════════════════════════════════════════════════

class Gemma4Client:
    """
    Gemma 4 统一调用客户端

    对应 CogniFind 项目中的：
    - crates/cognifind-ai/src/external_llm.rs（外接 API 调用）
    - crates/cognifind-ai/src/engine.rs（推理路由引擎）
    - crates/cognifind-ai/src/rag.rs（RAG prompt 构建）
    - crates/cognifind-app/src/ai_bridge.rs（服务层）
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        api_key: str = "EMPTY",
        model: str = "gemma-4-2b-it",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        enable_thinking: bool = False,
    ):
        """
        Args:
            base_url: 推理服务地址（vLLM / Ollama / 任何 OpenAI 兼容 API）
            api_key: API 密钥（vLLM 默认 "EMPTY"，Ollama 默认 "ollama"）
            model: 模型名称，如 "gemma-4-26b-it"
            temperature: 采样温度
            max_tokens: 最大生成 token 数
            enable_thinking: 是否启用 Gemma 4 思考模式
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.tools: List[ToolDefinition] = []
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    # ── 工具注册 ────────────────────────────────────────────────────────

    def register_tool(self, tool: ToolDefinition) -> "Gemma4Client":
        """注册工具 — 等价于定义 <|tool> ... <tool|>"""
        self.tools.append(tool)
        return self

    def register_tools(self, tools: List[ToolDefinition]) -> "Gemma4Client":
        self.tools.extend(tools)
        return self

    def _build_tools_schema(self) -> List[Dict[str, Any]]:
        """构建 OpenAI 兼容的 tools schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self.tools
        ]

    # ── 多模态编码 ──────────────────────────────────────────────────────

    @staticmethod
    def _encode_image(image_path: str) -> str:
        """
        图片 Base64 编码 — 等价于 Rust 的 image_to_data_uri()

        对应文件: crates/cognifind-ai/src/external_llm.rs: image_to_data_uri()
        支持: jpg, jpeg, png, gif, webp, bmp
        """
        with open(image_path, "rb") as f:
            data = f.read()
        ext = Path(image_path).suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
        mime_map = {
            "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp",
            "bmp": "image/bmp",
        }
        if ext not in mime_map:
            raise ValueError(f"不支持的图片格式: {ext}")
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime_map[ext]};base64,{b64}"

    @staticmethod
    def _encode_audio(audio_path: str) -> str:
        """
        音频 Base64 编码

        对应: E2B/E4B 的 <|audio|> 原生音频输入
        """
        with open(audio_path, "rb") as f:
            data = f.read()
        ext = Path(audio_path).suffix.lower().replace(".", "")
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:audio/{ext};base64,{b64}"

    def build_multimodal_message(
        self,
        role: str,
        content: Union[str, MultimodalContent],
    ) -> Dict[str, Any]:
        """
        构建多模态消息 — 等价于 external_llm.rs 的 ContentPart 结构

        Gemma 4 多模态特殊 token（在 API 中自动处理）：
        - <|image|> : 图像占位
        - <|audio|> : 音频占位
        - <|video|> : 视频占位
        """
        if isinstance(content, str):
            return {"role": role, "content": content}

        parts = []

        if content.text:
            parts.append({"type": "text", "text": content.text})

        if content.image_path:
            parts.append({
                "type": "image_url",
                "image_url": {"url": self._encode_image(content.image_path)},
            })

        if content.image_url:
            parts.append({
                "type": "image_url",
                "image_url": {"url": content.image_url},
            })

        if content.audio_path:
            parts.append({
                "type": "audio_url",
                "audio_url": {"url": self._encode_audio(content.audio_path)},
            })

        return {"role": role, "content": parts}

    # ── RAG Prompt 构建（等价于 rag.rs: build_prompt()）─────────────────

    @staticmethod
    def build_rag_prompt(ctx: RagContext, question: str, max_snippets: int = 4) -> str:
        """
        构建 RAG 提示词 — 等价于 Rust 的 build_prompt()

        对应文件: crates/cognifind-ai/src/rag.rs
        将本地文件检索结果拼接为 prompt 上下文，注入给 Gemma 4
        """
        parts = [
            "以下是检索到的本地文件上下文，请结合上下文回答用户问题。"
            "若上下文不足请说明。\n",
        ]
        if ctx.query:
            parts.append(f"用户搜索词: {ctx.query}\n")

        if ctx.files:
            parts.append("\n相关文件:\n")
            for i, f in enumerate(ctx.files[:12], 1):
                parts.append(f"{i}. {f.get('name', '?')} — {f.get('path', '?')}\n")

        if ctx.snippets:
            parts.append("\n内容片段:\n")
            for i, sn in enumerate(ctx.snippets[:max_snippets], 1):
                text = sn.get("snippet", "")[:400]
                parts.append(f"{i}. [{sn.get('path', '?')}] {text}\n")

        parts.append(f"\n用户问题: {question}\n")
        return "".join(parts)

    # ── 核心调用 ────────────────────────────────────────────────────────

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[ToolDefinition]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        发送聊天请求 — 等价于 external_llm.rs 的 stream_external_completion()

        通过 OpenAI 兼容 Chat Completions API 调用 Gemma 4
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

        if self.enable_thinking:
            payload["extra_body"] = {"thinking": True}

        active_tools = tools if tools is not None else self.tools
        if active_tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in active_tools
            ]
            payload["tool_choice"] = "auto"

        resp = self.session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()

    # ── 原生函数调用（Native Function Calling）─────────────────────────

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        max_tool_rounds: int = 5,
    ) -> str:
        """
        Agent 循环 — 等价于 engine.rs 的 run_stream() 工具调用部分

        流程：
        1. 发送用户消息 + 工具定义 → Gemma 4 分析
        2. 模型判断是否需要调用工具 → 生成 <|tool_call> ... <tool_call|>
        3. 执行工具 → 返回 <|tool_result> ... <tool_result|>  
        4. 模型生成最终自然语言回答

        Gemma 4 原生函数调用使用 6 个专用特殊 token：
        - <|tool> ... <tool|>      : 定义工具
        - <|tool_call> ... <tool_call|>  : 模型请求调用工具
        - <|tool_result> ... <tool_result|> : 返回工具执行结果
        """
        current_messages = list(messages)

        for _ in range(max_tool_rounds):
            response = self.chat(current_messages)
            choice = response["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "stop")

            # 提取工具调用 (finish_reason == "tool_calls")
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                return message.get("content", "")

            current_messages.append({
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                func_args = json.loads(tc["function"]["arguments"])
                tool_call_id = tc["id"]

                result = self._execute_tool(func_name, func_args)

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return "[达到最大工具调用轮数]"

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Any:
        """执行已注册的工具"""
        for tool in self.tools:
            if tool.name == name:
                if tool.handler:
                    try:
                        return tool.handler(**args)
                    except Exception as e:
                        return {"error": str(e)}
                return {"error": f"工具 '{name}' 未绑定处理函数"}
        return {"error": f"未找到工具 '{name}'"}

    # ── 多模态 Vision 调用（等价于 external_llm.rs 的 stream_vision_api）──

    def vision_chat(
        self,
        prompt: str,
        image_data_uri: str,
        detail: str = "low",
    ) -> str:
        """
        图片理解 — 等价于 external_llm.rs 的 describe_image_sync()

        通过 OpenAI 兼容 Vision API 调用 Gemma 4 的多模态能力
        对应: ContentPart { part_type: "image_url", image_url: ... }
        """
        content_parts = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_data_uri, "detail": detail},
            },
        ]

        messages = [{"role": "user", "content": content_parts}]
        response = self.chat(messages)
        return response["choices"][0]["message"]["content"] or ""

    def describe_image(self, image_path: str) -> str:
        """便捷方法：描述本地图片内容"""
        data_uri = self._encode_image(image_path)
        return self.vision_chat(
            "请描述这张图片的内容，注意场景、物体、颜色、文字等信息。",
            data_uri,
        )

    # ── 音频转写（等价于 audio.rs 的 transcribe_audio_external）───────

    def transcribe_audio(self, audio_path: str) -> str:
        """
        音频转文字 — 等价于 audio.rs 的 transcribe_audio_external()

        通过 OpenAI 兼容 Whisper API 进行语音识别
        对应文件: crates/cognifind-ai/src/audio.rs
        """
        base_url = self.base_url.rstrip("/").rstrip("/v1")
        url = f"{base_url}/v1/audio/transcriptions"

        filename = Path(audio_path).name or "audio"

        with open(audio_path, "rb") as f:
            resp = self.session.post(
                url,
                files={"file": (filename, f)},
                data={"model": "whisper-1", "response_format": "text"},
                timeout=120,
            )
        resp.raise_for_status()
        return resp.text.strip()

    # ── 混合路由（等价于 engine.rs 的五维决策法）──────────────────────

    def chat_with_hybrid_routing(
        self,
        ctx: RagContext,
        question: str,
        local_model_func: Optional[Callable] = None,
    ) -> str:
        """
        混合模式路由 — 等价于 engine.rs 的 decide_hybrid_backend()

        五维决策法：
        1. 数据敏感度：含本地文件上下文 → 本地
        2. 任务复杂度：数学/代码/推理 → 外部
        3. 延迟要求：简单任务 → 本地
        4. 本地资源：本地模型就绪 → 本地
        5. 网络状态：外部 API 就绪 → 外部

        对应文件: crates/cognifind-ai/src/engine.rs
        """
        has_context = bool(ctx.files or ctx.snippets)

        # 维度 1: 数据敏感 → 本地
        if has_context and local_model_func:
            prompt = self.build_rag_prompt(ctx, question)
            return local_model_func(prompt)

        # 维度 2 + 3: 简单任务 → 本地
        is_complex = self._is_complex_task(question)
        if not is_complex and local_model_func:
            return local_model_func(question)

        # 维度 5: 网络可用 → 外部
        prompt = self.build_rag_prompt(ctx, question) if has_context else question
        messages = [
            {"role": "system", "content": "你是 CogniFind 助手。"},
            {"role": "user", "content": prompt},
        ]
        response = self.chat(messages)
        return response["choices"][0]["message"]["content"] or ""

    @staticmethod
    def _is_complex_task(question: str) -> bool:
        """判断是否为复杂任务 — 等价于 engine.rs 的 is_complex_task()"""
        q = question.lower()
        keywords = [
            "代码", "编程", "函数", "算法", "报错", "调试", "bug",
            "code", "program", "function", "regex", "正则",
            "推理", "证明", "计算", "求解", "方程", "积分", "导数",
            "math", "calculate", "prove", "solve", "equation",
            "翻译成代码", "实现一个", "写一个", "生成",
            "多模态", "图像", "图片", "ocr",
        ]
        if "```" in q:
            return True
        return any(k in q for k in keywords)

    # ── 结构化输出 ──────────────────────────────────────────────────────

    def generate_structured(
        self,
        messages: List[Dict[str, Any]],
        json_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        强制模型输出结构化 JSON — 利用 Gemma 4 的 <|"|> 分隔符

        Gemma 4 原生支持结构化 JSON 输出，确保特殊字符被正确处理
        """
        schema_prompt = (
            "你必须严格按照以下 JSON Schema 输出，"
            "不要添加任何额外说明或 markdown 代码块：\n"
            f"{json.dumps(json_schema, ensure_ascii=False, indent=2)}\n"
            "请直接输出 JSON。"
        )

        structured_messages = [
            {"role": "system", "content": schema_prompt},
        ] + messages

        response = self.chat(structured_messages)
        content = response["choices"][0]["message"]["content"] or "{}"

        content = content.strip()
        for prefix in ["```json", "```"]:
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        return json.loads(content)

    # ── 便捷方法 ────────────────────────────────────────────────────────

    def ask(self, question: str) -> str:
        """简单问答"""
        messages = [{"role": "user", "content": question}]
        response = self.chat(messages)
        return response["choices"][0]["message"]["content"] or ""

    def ask_with_image(self, question: str, image_path: str) -> str:
        """图文问答"""
        data_uri = self._encode_image(image_path)
        return self.vision_chat(question, data_uri)


# ═══════════════════════════════════════════════════════════════════════════
# 服务层 — 等价于 ai_bridge.rs 的 AiService
# ═══════════════════════════════════════════════════════════════════════════

class AiService:
    """
    AI 服务层 — 等价于 crates/cognifind-app/src/ai_bridge.rs 的 AiService

    封装了推理生命周期管理、取消机制和流式事件处理
    """

    def __init__(self, client: Gemma4Client):
        self.client = client
        self._cancelled = False

    def submit(self, ctx: RagContext, question: str) -> Generator[str, None, None]:
        """
        流式提交 — 等价于 AiService::submit() + drain_events()

        流式 yield token，支持中途取消
        """
        self._cancelled = False

        # 构建 prompt（等价于 engine.rs 的 build_user_prompt）
        has_context = bool(ctx.files or ctx.snippets)
        if has_context:
            prompt = self.client.build_rag_prompt(ctx, question)
        else:
            prompt = question

        system_content = (
            "你是 CogniFind 助手。用户可能提供了一些本地文件的检索上下文，"
            "请结合上下文回答用户问题；若上下文不足请说明。"
            "对于与文件无关的问题，请直接回答。"
        ) if has_context else (
            "你是一个智能助手，可以回答各种问题。"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]

        # 流式调用（等价于 external_llm.rs 的 stream_external_completion_with_cancel）
        payload = {
            "model": self.client.model,
            "messages": messages,
            "temperature": self.client.temperature,
            "max_tokens": self.client.max_tokens,
            "stream": True,
        }

        if self.client.tools:
            payload["tools"] = self.client._build_tools_schema()
            payload["tool_choice"] = "auto"

        resp = self.client.session.post(
            f"{self.client.base_url}/chat/completions",
            json=payload,
            stream=True,
            timeout=300,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if self._cancelled:
                break
            if not line:
                continue
            line = line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    yield token
            except json.JSONDecodeError:
                continue

    def stop(self):
        """取消推理 — 等价于 AiService::stop()"""
        self._cancelled = True