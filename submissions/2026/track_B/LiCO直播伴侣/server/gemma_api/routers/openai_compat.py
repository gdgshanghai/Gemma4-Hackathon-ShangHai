from typing import Any, Dict
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio
import logging
import httpx
import base64
import json
import time
import uuid
from pathlib import Path

from gemma_api.config import (
    GEMMA_API_KEY,
    OLLAMA_AUDIO_MODEL,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_VISION_MODEL,
    RECEIVED_AUDIO_DIR,
    RECEIVED_REQUEST_DIR,
    SAVE_REQUESTS,
)

router = APIRouter(tags=["openai_compat"])
logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

import os

JOINT_MAX_AUDIO_CLIPS = 2
JOINT_MAX_IMAGES = 2
JOINT_MAX_AUDIO_SECONDS = 8.0
JOINT_ASR_TIMEOUT_SECONDS = 15.0
# 不对联合主推理做短超时截断。让客户端/上游自行决定等待上限。
JOINT_MAIN_TIMEOUT_SECONDS = 600.0

# Whisper / CTranslate2 模型并发调用会互相争抢 GPU，导致单次 ASR 超时被取消。
# 用信号量串行化（默认 1），让并发的分轨音频请求有序排队，延迟可预测。
_ASR_SEMAPHORE = asyncio.Semaphore(int(os.getenv("ASR_MAX_CONCURRENCY", "1")))


def build_chat_completion(
    *,
    model: str,
    content: str,
    finish_reason: str = "stop",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """验证客户端 API Key"""
    if GEMMA_API_KEY:
        if not credentials or credentials.scheme != "Bearer":
            raise HTTPException(status_code=401, detail="Missing or invalid authentication scheme")
        if credentials.credentials != GEMMA_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API Key")

@router.post("/v1/echo_size", dependencies=[Depends(verify_api_key)])
async def echo_size(request: Request):
    """上传探测接口：只读取请求体并返回字节数与服务端读取耗时，不做任何推理。
    用法：客户端把真实的联合请求体 POST 到此接口，对比客户端测得的总耗时：
      - 若 server_body_read_seconds 很大 → 上传链路慢（服务端在等 body）。
      - 若 server_body_read_seconds≈0 但客户端总耗时很大 → 网关在上游缓冲整个 body，瓶颈在客户端↔网关。
    """
    t0 = time.perf_counter()
    body = await request.body()
    dt = time.perf_counter() - t0
    n = len(body)
    mbps = (n * 8 / 1e6 / dt) if dt > 0 else 0.0
    logger.info("echo_size: bytes=%d read_seconds=%.2f throughput_mbps=%.2f", n, dt, mbps)
    return {
        "bytes": n,
        "megabytes": round(n / 1024 / 1024, 3),
        "server_body_read_seconds": round(dt, 3),
        "server_read_throughput_mbps": round(mbps, 2),
        "hint": "客户端总耗时 - server_body_read_seconds ≈ 客户端↔网关上传耗时",
    }


@router.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(request: Request):
    """
    OpenAI 兼容接口代理。
    允许客户端直接以 OpenAI 格式（含 input_audio, image_url 和严格 JSON 要求）调用，
    自动将 Qwen 模型映射为 Gemma 4 模型，并透传给后端的 Ollama。
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    original_model = body.get("model", "")
    model_lower = original_model.lower()
    
    # 自动映射模型
    if "qwen" in model_lower:
        if "omni" in model_lower or "audio" in model_lower or "asr" in model_lower:
            body["model"] = OLLAMA_AUDIO_MODEL
        elif "vision" in model_lower or "plus" in model_lower or "vl" in model_lower:
            body["model"] = OLLAMA_VISION_MODEL
        else:
            body["model"] = OLLAMA_MODEL
    elif "gemma" in model_lower:
        if "e4b" in model_lower or "audio" in model_lower:
            body["model"] = OLLAMA_AUDIO_MODEL
        else:
            body["model"] = OLLAMA_MODEL
    elif not original_model:
        body["model"] = OLLAMA_MODEL

    # 清洗请求，解决格式兼容问题，提取音频，并根据载荷自动纠正目标模型
    messages = body.get("messages", [])
    request_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    has_audio = False
    has_image = False
    audio_bytes_list = []
    audio_formats = []
    audio_paths = []
    audio_diagnostics = []
    req_t0 = time.perf_counter()

    # 落盘保存客户端原始请求体（含 base64），便于离线复现/回放实测耗时。
    if SAVE_REQUESTS:
        try:
            save_body = dict(body)
            save_body["model"] = original_model or body.get("model", "")
            raw = json.dumps(save_body, ensure_ascii=False)
            req_dir = Path(RECEIVED_REQUEST_DIR)
            req_dir.mkdir(parents=True, exist_ok=True)
            (req_dir / f"{request_id}.json").write_text(raw, encoding="utf-8")
            n_audio = sum(
                1 for m in messages if isinstance(m.get("content"), list)
                for p in m.get("content", []) if p.get("type") == "input_audio"
            )
            n_image = sum(
                1 for m in messages if isinstance(m.get("content"), list)
                for p in m.get("content", []) if p.get("type") == "image_url"
            )
            logger.info(
                "OpenAI proxy: saved request request_id=%s bytes=%d audio=%d image=%d stream=%s file=%s",
                request_id, len(raw), n_audio, n_image, body.get("stream", False),
                req_dir / f"{request_id}.json",
            )
        except Exception as e:
            logger.warning("OpenAI proxy: failed to save request request_id=%s error=%s", request_id, e)

    # 我们需要在决定最终模型前，检查载荷
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "input_audio":
                    has_audio = True
                elif part.get("type") == "image_url":
                    has_image = True

    if has_audio or has_image:
        body["model"] = OLLAMA_MODEL

    if sum(
        1
        for msg in messages
        if isinstance(msg.get("content"), list)
        for part in msg.get("content", [])
        if part.get("type") == "input_audio"
    ) > JOINT_MAX_AUDIO_CLIPS:
        raise HTTPException(status_code=413, detail=f"Too many audio clips; max={JOINT_MAX_AUDIO_CLIPS}")

    if sum(
        1
        for msg in messages
        if isinstance(msg.get("content"), list)
        for part in msg.get("content", [])
        if part.get("type") == "image_url"
    ) > JOINT_MAX_IMAGES:
        raise HTTPException(status_code=413, detail=f"Too many images; max={JOINT_MAX_IMAGES}")

    # 联合推理模式下，音频先由服务端 ASR 转写，再统一交给 31B 主模型推理。
    # 不再自动路由到 E4B，否则会破坏“图片/文本/音频转写结果共享上下文”的目标。
            
    is_31b = (body["model"] == OLLAMA_MODEL)
    
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            new_content = []
            for part in content:
                if part.get("type") == "input_audio":
                    audio_data = part.get("input_audio", {}).get("data", "")
                    audio_fmt = part.get("input_audio", {}).get("format", "wav")
                    
                    if audio_data.startswith("data:audio/"):
                        try:
                            # 提取正确的格式，如果有的话
                            if "base64," in audio_data:
                                prefix, _ = audio_data.split("base64,")
                                if "/" in prefix and ";" in prefix:
                                    mime_fmt = prefix.split("/")[1].split(";")[0]
                                    if mime_fmt:
                                        audio_fmt = mime_fmt
                            audio_data = audio_data.split("base64,")[1]
                            part["input_audio"]["data"] = audio_data
                        except IndexError:
                            pass
                    
                    try:
                        audio_bytes = base64.b64decode(audio_data)
                        audio_bytes_list.append(audio_bytes)
                        audio_formats.append(audio_fmt)
                        audio_dir = Path(RECEIVED_AUDIO_DIR)
                        audio_dir.mkdir(parents=True, exist_ok=True)
                        audio_path = audio_dir / f"{request_id}-{len(audio_bytes_list)}.{audio_fmt}"
                        audio_path.write_bytes(audio_bytes)
                        audio_paths.append(str(audio_path))
                        logger.info(
                            "OpenAI proxy: received audio request_id=%s index=%d format=%s bytes=%d saved=%s",
                            request_id,
                            len(audio_bytes_list),
                            audio_fmt,
                            len(audio_bytes),
                            audio_path,
                        )
                        try:
                            from gemma_api.services.stt import inspect_audio_file

                            # ffprobe/ffmpeg 是阻塞子进程，必须放到线程池，否则会卡死事件循环、
                            # 导致并发的流式请求拿不到首 token（客户端 60s 超时）。
                            diag = await asyncio.to_thread(inspect_audio_file, str(audio_path))
                            audio_diagnostics.append(diag)
                            logger.info("OpenAI proxy: audio diagnostics request_id=%s diag=%s", request_id, diag)
                        except Exception as e:
                            logger.warning("OpenAI proxy: audio diagnostics failed request_id=%s error=%s", request_id, e)
                    except Exception:
                        logger.exception("OpenAI proxy: failed to decode/save input_audio request_id=%s", request_id)
                        
                    # 针对 31B 模型，不兼容 input_audio，将其替换为文本提示，引导其调用 ASR 工具
                    if is_31b:
                        new_content.append({
                            "type": "text",
                            "text": "[系统提示：用户上传了一段语音，但当前模型不支持原生听音。请务必调用 asr_transcribe 工具获取高精度转写文本以进行后续分析。]"
                        })
                    else:
                        new_content.append(part)
                else:
                    new_content.append(part)
            msg["content"] = new_content

    for diag in audio_diagnostics:
        duration = diag.get("duration_sec_est")
        if duration is None:
            try:
                duration = float(diag.get("ffprobe", {}).get("format", {}).get("duration", 0))
            except Exception:
                duration = 0
        if duration and duration > JOINT_MAX_AUDIO_SECONDS:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Audio clip too long for 30s joint reasoning budget: "
                    f"{duration:.2f}s > {JOINT_MAX_AUDIO_SECONDS:.2f}s"
                ),
            )

    forced_asr_done = False
    if audio_bytes_list:
        from gemma_api.services.stt import transcribe_audio

        audio_fmt = audio_formats[0] if audio_formats else "wav"
        _t_asr = time.perf_counter()
        try:
            async with _ASR_SEMAPHORE:
                text = await asyncio.wait_for(
                    asyncio.to_thread(
                        transcribe_audio,
                        audio_bytes_list[0],
                        filename=f"audio.{audio_fmt}",
                    ),
                    timeout=JOINT_ASR_TIMEOUT_SECONDS,
                )
            forced_asr_done = True
            if not text or "(未识别到有效语音内容)" in text:
                asr_payload = {
                    "tool": "asr_transcribe",
                    "status": "ok",
                    "request_id": request_id,
                    "audio_file": audio_paths[0] if audio_paths else "",
                    "audio_diagnostics": audio_diagnostics[0] if audio_diagnostics else {},
                    "transcript": "",
                    "observation": "未检测到有效人声。服务端已成功接收并解码音频，但 ASR 未得到可转写的人声文本。请结合音频诊断将其判断为无语音活动、环境音、BGM 或非人声声音，而不是系统故障。",
                }
            else:
                asr_payload = {
                    "tool": "asr_transcribe",
                    "status": "ok",
                    "request_id": request_id,
                    "audio_file": audio_paths[0] if audio_paths else "",
                    "audio_diagnostics": audio_diagnostics[0] if audio_diagnostics else {},
                    "transcript": text,
                }
            logger.info("OpenAI proxy: forced ASR completed request_id=%s len=%d", request_id, len(text))
        except Exception as e:
            logger.exception("OpenAI proxy: forced ASR failed request_id=%s file=%s", request_id, audio_paths[0] if audio_paths else "")
            asr_payload = {
                "tool": "asr_transcribe",
                "status": "error",
                "request_id": request_id,
                "audio_file": audio_paths[0] if audio_paths else "",
                "audio_diagnostics": audio_diagnostics[0] if audio_diagnostics else {},
                "error": str(e),
            }
        logger.info("OpenAI proxy: timing request_id=%s stage=asr seconds=%.2f", request_id, time.perf_counter() - _t_asr)
        messages.append({
            "role": "user",
            "content": (
                "[服务端音频分析上下文]\n"
                f"{json.dumps(asr_payload, ensure_ascii=False)}\n"
                "请基于以上服务端实际 ASR 结果、音频诊断、图片内容和用户原始任务目标做一次联合推理；不要声称没有收到音频。"
            ),
        })

    joint_mode = has_audio or has_image
    if joint_mode:
        body["messages"].insert(0, {
            "role": "system",
            "content": (
                "你是 Gemma 4 31B 多模态联合推理服务。服务端已经把图片、用户文本/JSON、"
                "音频转写结果和任务目标放入同一个上下文。你必须只做一次综合判断。"
                "最终回答必须使用简体中文，并且只能输出用户要求的 JSON 对象；"
                "不要输出英文，不要输出 markdown，不要输出思考过程、分析过程、Task/Input/Constraints 等说明。"
                "若音频转写为空，结合音频诊断判断为静音、环境音、BGM、游戏声或非人声，"
                "不要说 ASR 工具缺失或未收到音频。为了满足 30 秒响应上限，输出必须简短。"
            ),
        })
        body.pop("tools", None)
        # 不对输出 token 做服务端截断。旧客户端可能仍会传 max_tokens；
        # 这里移除它，避免 Gemma 只输出 reasoning 后因 length 截断，拿不到最终 JSON。
        body.pop("max_tokens", None)
        body.setdefault("temperature", 0.2)
        # Ollama/OpenAI 兼容接口会把部分模型的思考过程放到 reasoning 字段。
        # 对前端业务接口禁用思考输出，避免把英文 reasoning 当作正式答案。
        body["think"] = False

    # 自动注入搜索工具和 ASR 工具。联合推理模式走单次主推理，禁用工具循环以满足 30s 预算。
    if not joint_mode:
        if "tools" not in body:
            body["tools"] = []
        body["tools"].append({
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "当需要获取最新信息、解释网络梗、或者分析不知道的直播事件时调用此工具进行联网搜索。如果不确定，请务必调用。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"]
                }
            }
        })
        
        if has_audio and not forced_asr_done:
            body["tools"].append({
                "type": "function",
                "function": {
                    "name": "asr_transcribe",
                    "description": "调用外部高精度语音识别(ASR)引擎，对用户上传的语音片段进行精确的文本转写。如果原生听音不清，或系统提示当前模型不支持听音，请务必调用此工具。",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            })

    stream = body.get("stream", False)
    logger.info(f"OpenAI proxy: mapped model '{original_model}' to '{body['model']}'")
    logger.info(
        "OpenAI proxy: request_id=%s joint_mode=%s has_audio=%s has_image=%s stream=%s max_tokens=%s",
        request_id,
        joint_mode,
        has_audio,
        has_image,
        stream,
        body.get("max_tokens"),
    )

    url = f"{OLLAMA_HOST}/v1/chat/completions"
    
    try:
        if stream:
            async def generate():
                timeout = JOINT_MAIN_TIMEOUT_SECONDS if joint_mode else 600.0
                _t_stream = time.perf_counter()
                _ttfb = None
                _nchunks = 0
                _content_chunks = 0
                # 立即给客户端一个字节，证明连接已建立（SSE 注释，解析器会忽略）
                yield b": connected\n\n"
                async with httpx.AsyncClient(timeout=timeout) as client:
                    is_tool_call = False
                    tool_calls_data = ""
                    tc_name = ""
                    
                    async with client.stream("POST", url, json=body) as response:
                        if response.status_code != 200:
                            err = await response.aread()
                            yield err
                            return
                        
                        line_iter = response.aiter_lines()
                        while True:
                            try:
                                chunk = await asyncio.wait_for(line_iter.__anext__(), timeout=10.0)
                            except StopAsyncIteration:
                                break
                            except asyncio.TimeoutError:
                                # 首 token 迟迟未到（prefill/排队/冷加载）：发心跳避免客户端 60s 无 token 超时
                                yield b": keepalive\n\n"
                                continue
                            if not chunk: continue
                            if _ttfb is None:
                                _ttfb = time.perf_counter() - _t_stream
                                logger.info(
                                    "OpenAI proxy: timing request_id=%s stage=stream_ttfb seconds=%.2f",
                                    request_id, _ttfb,
                                )
                            _nchunks += 1
                            if chunk.startswith("data: "):
                                data_str = chunk[6:]
                                if data_str == "[DONE]":
                                    if not is_tool_call:
                                        if _content_chunks == 0:
                                            fallback_chunk = {
                                                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                                                "object": "chat.completion.chunk",
                                                "created": int(time.time()),
                                                "model": body["model"],
                                                "choices": [
                                                    {
                                                        "index": 0,
                                                        "delta": {
                                                            "content": json.dumps(
                                                                {
                                                                    "status": "no_final_content",
                                                                    "message": "模型仅返回了思考过程，没有返回最终 JSON。请重试或缩短输入。",
                                                                },
                                                                ensure_ascii=False,
                                                            )
                                                        },
                                                        "finish_reason": None,
                                                    }
                                                ],
                                            }
                                            yield ("data: " + json.dumps(fallback_chunk, ensure_ascii=False) + "\n\n").encode()
                                        yield (chunk + "\n\n").encode()
                                    break
                                
                                try:
                                    data = json.loads(data_str)
                                    delta = data.get("choices", [{}])[0].get("delta", {})
                                    # Do not expose Ollama/Gemma reasoning as final content.
                                    # The business client expects the final Chinese JSON answer,
                                    # not the model's internal (often English) reasoning trace.
                                    if "tool_calls" in delta:
                                        is_tool_call = True
                                        for tc in delta["tool_calls"]:
                                            if "function" in tc:
                                                if tc["function"].get("name"):
                                                    tc_name += tc["function"]["name"]
                                                if tc["function"].get("arguments"):
                                                    tool_calls_data += tc["function"]["arguments"]
                                    else:
                                        if not is_tool_call:
                                            if delta.get("content"):
                                                _content_chunks += 1
                                            yield (chunk + "\n\n").encode()
                                except Exception:
                                    if not is_tool_call:
                                        yield (chunk + "\n\n").encode()

                    if not is_tool_call:
                        logger.info(
                            "OpenAI proxy: timing request_id=%s stage=stream_total seconds=%.2f chunks=%d",
                            request_id, time.perf_counter() - _t_stream, _nchunks,
                        )

                    if is_tool_call:
                        tool_res = ""
                        logger.info(f"OpenAI proxy: Intercepted tool call for: {tc_name}")
                        
                        if tc_name == "web_search":
                            query = ""
                            try:
                                args = json.loads(tool_calls_data)
                                query = args.get("query", "")
                            except Exception:
                                pass
                            if query:
                                from gemma_api.services.search import web_search
                                search_res, _ = await web_search(query)
                                tool_res = search_res
                                
                        elif tc_name == "asr_transcribe":
                            if audio_bytes_list:
                                from gemma_api.services.stt import transcribe_audio
                                try:
                                    # 将音频抛给本地 Whisper 引擎
                                    audio_fmt = audio_formats[0] if audio_formats else "wav"
                                    text = transcribe_audio(audio_bytes_list[0], filename=f"audio.{audio_fmt}")
                                    
                                    if not text or "(未识别到有效语音内容)" in text:
                                        tool_res = json.dumps({
                                            "tool": "asr_transcribe",
                                            "status": "ok",
                                            "request_id": request_id,
                                            "audio_file": audio_paths[0] if audio_paths else "",
                                            "transcript": "",
                                            "observation": "未检测到有效人声。ASR 工具已正常完成分析，但没有可转写的人声内容。",
                                        }, ensure_ascii=False)
                                    else:
                                        tool_res = json.dumps({
                                            "tool": "asr_transcribe",
                                            "status": "ok",
                                            "request_id": request_id,
                                            "audio_file": audio_paths[0] if audio_paths else "",
                                            "transcript": text,
                                        }, ensure_ascii=False)
                                    logger.info(f"ASR 转写成功: {len(text)} 字符")
                                except Exception as e:
                                    logger.exception("ASR 转写失败 request_id=%s file=%s", request_id, audio_paths[0] if audio_paths else "")
                                    tool_res = json.dumps({
                                        "tool": "asr_transcribe",
                                        "status": "error",
                                        "request_id": request_id,
                                        "audio_file": audio_paths[0] if audio_paths else "",
                                        "error": str(e),
                                    }, ensure_ascii=False)
                            else:
                                tool_res = "没有找到可供转写的语音数据。"
                        
                        if tool_res:
                            body["messages"].append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": "call_auto",
                                    "type": "function",
                                    "function": {
                                        "name": tc_name,
                                        "arguments": tool_calls_data
                                    }
                                }]
                            })
                            body["messages"].append({
                                "role": "tool",
                                "tool_call_id": "call_auto",
                                "name": tc_name,
                                "content": tool_res
                            })
                            
                            # 去除工具，强制其作答
                            body.pop("tools", None)
                            async with client.stream("POST", url, json=body) as response2:
                                async for chunk in response2.aiter_bytes():
                                    yield chunk
                        else:
                            # 工具解析或执行失败，直接重新生成文本
                            body.pop("tools", None)
                            async with client.stream("POST", url, json=body) as response2:
                                async for chunk in response2.aiter_bytes():
                                    yield chunk

            return StreamingResponse(generate(), media_type="text/event-stream")
        else:
            timeout = JOINT_MAIN_TIMEOUT_SECONDS if joint_mode else 600.0
            _t_main = time.perf_counter()
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.post(url, json=body)
                except httpx.ReadTimeout:
                    if joint_mode:
                        logger.warning(
                            "OpenAI proxy: joint main inference timeout request_id=%s timeout=%ss",
                            request_id,
                            timeout,
                        )
                        fallback = {
                            "status": "timeout_degraded",
                            "request_id": request_id,
                            "message": "主模型联合推理超过服务端 30 秒响应预算，已返回降级结果。",
                            "audio": asr_payload if audio_bytes_list else None,
                            "limits": {
                                "max_audio_clips": JOINT_MAX_AUDIO_CLIPS,
                                "max_images": JOINT_MAX_IMAGES,
                                "max_audio_seconds": JOINT_MAX_AUDIO_SECONDS,
                            },
                            "suggestion": "请客户端减少图片数量、缩短音频到 3-5 秒，或改用 streaming=true。",
                        }
                        return build_chat_completion(
                            model=body["model"],
                            content=json.dumps(fallback, ensure_ascii=False),
                            finish_reason="timeout",
                        )
                    raise
                if response.status_code != 200:
                    logger.error(f"Ollama API HTTP error: {response.text}")
                    raise HTTPException(status_code=response.status_code, detail=response.text)
                
                data = response.json()
                _main_secs = time.perf_counter() - _t_main
                _ct = data.get("usage", {}).get("completion_tokens", 0) or 0
                logger.info(
                    "OpenAI proxy: timing request_id=%s stage=main seconds=%.2f completion_tokens=%s tok_per_s=%.1f",
                    request_id,
                    _main_secs,
                    _ct,
                    (_ct / _main_secs if _main_secs > 0 else 0),
                )
                logger.info(
                    "OpenAI proxy: timing request_id=%s stage=total seconds=%.2f",
                    request_id,
                    time.perf_counter() - req_t0,
                )
                message = data.get("choices", [{}])[0].get("message", {})
                if message.get("reasoning") and not message.get("content"):
                    message["content"] = json.dumps(
                        {
                            "status": "no_final_content",
                            "message": "模型仅返回了思考过程，没有返回最终 JSON。请重试或缩短输入。",
                        },
                        ensure_ascii=False,
                    )
                    data["choices"][0]["message"] = message
                if message.get("tool_calls"):
                    tool_calls = message["tool_calls"]
                    body["messages"].append(message)
                    for tc in tool_calls:
                        tc_name = tc["function"]["name"]
                        tool_res = ""
                        
                        if tc_name == "web_search":
                            try:
                                args = json.loads(tc["function"]["arguments"])
                                query = args.get("query", "")
                            except Exception:
                                query = ""
                            if query:
                                logger.info(f"OpenAI proxy: Server auto-executing web_search for query: {query}")
                                from gemma_api.services.search import web_search
                                tool_res, _ = await web_search(query)
                                
                        elif tc_name == "asr_transcribe":
                            logger.info("OpenAI proxy: Server auto-executing asr_transcribe")
                            if audio_bytes_list:
                                from gemma_api.services.stt import transcribe_audio
                                try:
                                    audio_fmt = audio_formats[0] if audio_formats else "wav"
                                    text = transcribe_audio(audio_bytes_list[0], filename=f"audio.{audio_fmt}")
                                    
                                    if not text or "(未识别到有效语音内容)" in text:
                                        tool_res = json.dumps({
                                            "tool": "asr_transcribe",
                                            "status": "ok",
                                            "request_id": request_id,
                                            "audio_file": audio_paths[0] if audio_paths else "",
                                            "transcript": "",
                                            "observation": "未检测到有效人声。ASR 工具已正常完成分析，但没有可转写的人声内容。",
                                        }, ensure_ascii=False)
                                    else:
                                        tool_res = json.dumps({
                                            "tool": "asr_transcribe",
                                            "status": "ok",
                                            "request_id": request_id,
                                            "audio_file": audio_paths[0] if audio_paths else "",
                                            "transcript": text,
                                        }, ensure_ascii=False)
                                except Exception as e:
                                    logger.exception("ASR 转写失败 request_id=%s file=%s", request_id, audio_paths[0] if audio_paths else "")
                                    tool_res = json.dumps({
                                        "tool": "asr_transcribe",
                                        "status": "error",
                                        "request_id": request_id,
                                        "audio_file": audio_paths[0] if audio_paths else "",
                                        "error": str(e),
                                    }, ensure_ascii=False)
                            else:
                                tool_res = "没有找到可供转写的语音数据。"
                                
                        if tool_res:
                            body["messages"].append({
                                "role": "tool",
                                "content": tool_res,
                                "tool_call_id": tc["id"],
                                "name": tc_name
                            })
                    
                    body.pop("tools", None)
                    response2 = await client.post(url, json=body)
                    return response2.json()
                
                return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying to Ollama: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))