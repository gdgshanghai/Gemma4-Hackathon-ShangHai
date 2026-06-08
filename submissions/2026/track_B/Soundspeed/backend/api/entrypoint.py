"""可测试的 app 装配工厂（1.J-1.L §2.3 + v0.3 §2.5）。

build_app() 读 env 并完成 DAL + LLMService + Orchestrator + FastAPI 装配，返回 app。
不调用 uvicorn.run——这样测试可以直接 import build_app() 通过 TestClient 验证。

__main__.py 从此模块 import build_app()，再调 uvicorn.run()。

DEV 自动播种（仅在此函数，不在 create_app）：
  SOUNDSPEED_DEV=1 + DB 为空 → 委托 seed_dev_scene(dal) 播种一个 active 空场。
  幂等：list_scenes() 非空时跳过，持久 DB 重启不重复播种。
  播种落在 create_orchestrator 之前，确保 orchestrator.dal 与 app 共用同一连接。
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI

from backend.api.app import create_app
from backend.core.events import broadcast_tool_call
from backend.core.orchestrator import Orchestrator, create_orchestrator
from backend.core.session import SessionState
from backend.db.dal import DAL
from backend.db.seed import seed_dev_scene
from backend.llm.service import get_service

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = _REPO_ROOT / "data" / "soundspeed.db"


def _resolve_db_path() -> Path:
    """解析 DB 文件路径。

    SOUNDSPEED_DB 显式设置时优先；否则用仓库根下的持久路径 data/soundspeed.db
    （绝对路径，不依赖启动 cwd）。路径不存在时由 build_app 负责创建（含父目录）。
    """
    env = os.environ.get("SOUNDSPEED_DB")
    return Path(env) if env else _DEFAULT_DB_PATH


# 显存档位：一个 env (SOUNDSPEED_PROFILE) 选一组开关预设，省得手动记一串。
# 8GB 卡上三模型（Whisper+Pyannote+Gemma）无法共存（见 client.py / engine.py 的 OOM 注释），
# 故按工作阶段分档：import = Gemma 独占 GPU、录制关；record = 录制占 GPU、Gemma 退 CPU。
_VRAM_PROFILES: dict[str, dict[str, str]] = {
    "import": {
        "SOUNDSPEED_LIVE_ASR": "0",     # 录制关
        "SOUNDSPEED_DIARIZATION": "0",  # 分离关
        "SOUNDSPEED_LLM_GPU_LAYERS": "-1",  # Gemma 全 GPU（剧本解析/FC/照片提速）
    },
    "record": {
        "SOUNDSPEED_LIVE_ASR": "1",     # 实时 ASR 开
        "SOUNDSPEED_DIARIZATION": "1",  # 说话人分离开（Pyannote 默认走 GPU）
        "SOUNDSPEED_LLM_GPU_LAYERS": "0",   # Gemma 退 CPU，把显存让给 Whisper/Pyannote
    },
}


def _apply_vram_profile() -> None:
    """按 SOUNDSPEED_PROFILE 预设一组显存开关（须在任何开关被读取前调用）。

    用 os.environ.setdefault：个别开关已显式设置时仍优先，档位只补默认值。
    不设 SOUNDSPEED_PROFILE → no-op（行为不变）；未知档位 → 警告 + 跳过。
    兜底：record 下若 Whisper+Pyannote 仍 OOM，可再单独设 SOUNDSPEED_DIARIZATION_DEVICE=cpu。
    """
    profile = os.environ.get("SOUNDSPEED_PROFILE")
    if not profile:
        return
    presets = _VRAM_PROFILES.get(profile)
    if presets is None:
        logger.warning(
            "未知 SOUNDSPEED_PROFILE=%s，忽略（可选：%s）", profile, ", ".join(_VRAM_PROFILES)
        )
        return
    for key, value in presets.items():
        os.environ.setdefault(key, value)  # 个别 env 显式设置者优先
    logger.info("显存档位 SOUNDSPEED_PROFILE=%s 生效（个别 env 显式设置者优先）：%s", profile, presets)


def restore_active_scene(dal: DAL, session: SessionState) -> None:
    """启动时从 DB 把活跃场（is_active=1）恢复进内存 session，让重启后 NP 立即有上下文。

    SessionState 是内存态，重启清空；DB 持久。不恢复则 session.scene_id=None →
    NP（文本/语音）take_context 为空 → 模型无真 take 可归 → 静默 take_not_found，
    直到有人手动激活场。这里在 build_app 装配时补上。
    只恢复活跃**场**，不恢复活跃 take——录制进程已随重启消失，take_active 须保持 False。
    DB 无活跃场则 no-op。
    """
    active = dal.get_active_scene_id()
    if active is not None:
        session.activate_scene(active)


def _make_take_start_handler(live_asr, enroll_recorder):
    """TAKE_START 处理器：Capture 优先 —— 先 abort 任何进行中的 enroll 录音（释放
    设备），再 start live ASR。单 handler 保证顺序，不依赖事件订阅次序。

    abort() 是同步的（join enroll 线程）：现场麦 DeviceSource 阻塞读每块 ~chunk_ms
    返回，故正常 ~一个音频块内收束；5s 只是卡死线程的上限。
    """
    def handler(_payload):
        if enroll_recorder is not None:
            enroll_recorder.abort()
        live_asr.start()
    return handler


def build_app() -> FastAPI:
    """装配完整 FastAPI app 并返回（不启动 uvicorn）。

    读取 env：
      SOUNDSPEED_DB  数据库文件路径（默认 <repo>/data/soundspeed.db，持久；不存在则自动创建）
      ADMIN_TOKEN    管理员 token（缺失则 resolve_admin_token 随机生成）
      SOUNDSPEED_DEV dev 模式（=1 时挂载 /api/v1/debug/asr + 自动播种 active scene）
      SOUNDSPEED_PROFILE 显存档位（import=Gemma 独占 GPU/录制关；record=录制占 GPU/Gemma 退 CPU）

    llm_service 使用 get_service() 单例（codex P6），lazy 不触发模型加载。
    create_orchestrator 自动绑定 run_l2_take（llm_service 非 None 时）。
    """
    _apply_vram_profile()  # 先按 SOUNDSPEED_PROFILE 预设显存开关，再读各开关

    db_path = _resolve_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)  # 无库/无目录则自动创建持久库
    dal = DAL(db_path)

    # 清理上次进程残留的 'parsing' 上传（其后台任务已随进程消失，否则前端无限转圈）。
    stale = dal.reset_stale_parsing_uploads()
    if stale:
        logger.info("启动清理：%d 条残留 parsing 上传已复位为 error", stale)

    # DEV 自动播种：保证 dev server 启动后即有 active scene，1.K 可直接 take/start。
    # 仅在 SOUNDSPEED_DEV=1 且 DB 为空时执行（幂等，重启不重复播种）。
    if os.environ.get("SOUNDSPEED_DEV") == "1" and not dal.list_scenes():
        seed_dev_scene(dal)

    llm_service = get_service()
    orchestrator = create_orchestrator(dal, llm_service=llm_service)
    # 重启后从 DB 恢复活跃场到内存 session，否则 NP（文本/语音）首条都会因空上下文 take_not_found。
    restore_active_scene(dal, orchestrator.session)
    live_asr = _maybe_wire_live_asr(orchestrator)
    diarization_engine = _maybe_wire_diarization(orchestrator, live_asr)

    enroll_recorder = None
    if live_asr is not None:
        from backend.core.events import TAKE_END, TAKE_START
        from backend.diarization.enroll_recorder import EnrollRecorder

        enroll_recorder = EnrollRecorder(
            make_source=live_asr.make_source,
            is_capture_active=lambda: live_asr.running,
        )
        orchestrator.subscribe(TAKE_START, _make_take_start_handler(live_asr, enroll_recorder))
        orchestrator.subscribe(TAKE_END, lambda _p: live_asr.stop())

    app = create_app(orchestrator, llm_service=llm_service)

    # tool.call WS 实时推送：把 LLMService 每次 function-calling 成功的结果 tap 给 cm.broadcast。
    # cm 在 create_app 里初始化，此处安全取用。tap 内解析 tool_calls[0] 拿 name/arguments，
    # 不修改推理主流程（tap 异常由 service._worker 内的 try/except 保护，不会传播）。
    _cm = app.state.connection_manager

    def _tool_call_tap(task_type: str, tc: dict, gen_kwargs: dict, result_dict: dict) -> None:
        try:
            fn = tc.get("function") or {}

            # finish_reason / model
            choices = result_dict.get("choices") or []
            choice0 = choices[0] if choices else {}
            finish_reason: str | None = choice0.get("finish_reason")
            model: str | None = result_dict.get("model")

            # usage（llama-cpp 不保证带）
            usage = result_dict.get("usage") or {}
            prompt_tokens: int | None = usage.get("prompt_tokens")
            completion_tokens: int | None = usage.get("completion_tokens")
            total_tokens: int | None = usage.get("total_tokens")

            # available_tools：从 gen_kwargs["tools"] 抽 function.name
            raw_tools = gen_kwargs.get("tools") or []
            available_tools: tuple[str, ...] = tuple(
                t["function"]["name"]
                for t in raw_tools
                if isinstance(t, dict) and isinstance(t.get("function"), dict) and t["function"].get("name")
            )

            # tool_choice 规整：dict {function:{name}} → name；字符串原样；缺失 None
            raw_tc = gen_kwargs.get("tool_choice")
            if isinstance(raw_tc, dict):
                tool_choice: str | None = (raw_tc.get("function") or {}).get("name")
            elif isinstance(raw_tc, str):
                tool_choice = raw_tc
            else:
                tool_choice = None

            broadcast_tool_call(
                _cm,
                task_type=task_type,
                tool_name=fn.get("name") or "",
                arguments=fn.get("arguments") or "",
                ts=time.time(),
                tool_id=tc.get("id"),
                tool_type=tc.get("type"),
                finish_reason=finish_reason,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                available_tools=available_tools,
                tool_choice=tool_choice,
            )
        except Exception:
            pass  # 字段缺失等异常不影响推理；logger 在 service._worker 层已有 warning

    llm_service.set_tool_call_tap(_tool_call_tap)

    app.state.live_asr = live_asr  # None 表示未启用实时 ASR（devices 路由据此判断）
    app.state.diarization_engine = diarization_engine  # None 表示未启用（无 HF token）
    app.state.enroll_recorder = enroll_recorder  # None 表示实时采集未启用

    # 真实音频设备枚举/选择端点（独立于实时 ASR 开关，GET 总能枚举）
    from backend.api.routes.asr import router as asr_router
    from backend.api.routes.devices import router as devices_router
    from backend.api.routes.scripts import router as scripts_router
    from backend.api.routes.speakers import router as speakers_router

    app.include_router(devices_router)
    app.include_router(asr_router)
    app.include_router(speakers_router)
    app.include_router(scripts_router)
    return app


def _maybe_wire_live_asr(orchestrator: Orchestrator):
    """返回 LiveAsrSession（启用时）或 None（未启用）。

    实时 ASR：take.start 起采集线程，take.end 停。默认启用；SOUNDSPEED_LIVE_ASR=0 可关闭。

    env：
      SOUNDSPEED_LIVE_ASR=0      显式关闭（默认启用）
      SOUNDSPEED_ASR_MODEL       whisper.cpp 模型大小（默认 medium-q8_0 量化版；
                                 切回 fp16 基线：SOUNDSPEED_ASR_MODEL=medium）
      SOUNDSPEED_AUDIO_DEVICE    设备名或索引（首次引导用；UI 选过后持久化优先）
      SOUNDSPEED_VAD=energy      VAD 探测器：energy（默认，零依赖）| silero（需 torch venv）
      SOUNDSPEED_MODELS_DIR      Whisper 模型存放目录（默认 ./models/whisper/）

    启动时设备解析优先级：
      持久化名字（DB app_settings）> env > 系统默认 > 第一个可用

    Phase 1：只出实时文本，speaker 留 None。take.end 后批量 diarization 回填是 Phase 2。
    """
    if os.environ.get("SOUNDSPEED_LIVE_ASR") == "0":
        return None

    from backend.asr import DEFAULT_ASR_MODEL, ASRConfig, WhisperRunner
    from backend.asr.live_session import LiveAsrSession
    from backend.audio.device_resolve import resolve_device_index, resolve_device_name
    from backend.audio.devices import get_default_input_index, list_input_devices
    from backend.audio.source import AudioConfig
    from backend.vad.models import VadConfig

    # 生效的默认 ASR 模型在此（entrypoint 总是显式传 model_size，config.py 的 dataclass
    # 默认在生产路径上不生效）。两处都引用 DEFAULT_ASR_MODEL，防默认值漂移。
    model_size = os.environ.get("SOUNDSPEED_ASR_MODEL", DEFAULT_ASR_MODEL)
    vad_kind = os.environ.get("SOUNDSPEED_VAD", "silero")
    # 项目默认转录语言（zh/en/auto…）；运行时可在设置面板切换（POST /asr/language 覆盖本次）。
    language = os.environ.get("SOUNDSPEED_ASR_LANGUAGE", "zh")

    # 模型目录：优先 env 指定；否则用项目内 models/whisper/（统一管理模型权重）
    models_dir_env = os.environ.get("SOUNDSPEED_MODELS_DIR")
    models_dir = models_dir_env or str(Path("./models/whisper").resolve())

    runner = WhisperRunner(
        ASRConfig(model_size=model_size, language=language, models_dir=models_dir)
    )

    def _source_factory(device: object):
        """将 session._device（设备名 str）解析为当前 index，按 index 开流。

        device=None（零设备退化）→ 退系统默认 index；查不到 → 退第一个可用 / 让 sounddevice 自选。
        device=name（str）→ list_input_devices() 反查当前 index；设备拔走 → 退系统默认 + warning。
        """
        from backend.audio.device_source import DeviceError, DeviceSource, open_device_with_fallback

        devices = list_input_devices()
        default_idx = get_default_input_index()
        name_str = device if isinstance(device, str) else None
        idx, available = resolve_device_index(name_str, devices, default_idx)

        if not available and name_str is not None:
            # 设备已拔走：log + publish device.warning 事件（前端需在 app.py lifespan 转发才可见）
            logger.warning("设备 %r 当前不在场，采集 fallback 到系统默认（index=%s）", name_str, idx)
            from backend.core.events import DEVICE_WARNING, DeviceWarningPayload  # noqa: PLC0415

            orchestrator.publish(
                DEVICE_WARNING,
                DeviceWarningPayload(
                    message=f"设备 '{name_str}' 当前不在场，已 fallback 到系统默认",
                    device_name=name_str,
                ),
            )

        # 候选顺序：解析到的 idx → 系统默认 → 所有可用设备（open_device_with_fallback 去重保序）
        # 探测每个候选是否真能打开（防幽灵设备 PortAudioError），返回首个成功的 index
        candidates = [idx, default_idx, *(d.index for d in devices)]
        try:
            winning = open_device_with_fallback(candidates, AudioConfig())
        except DeviceError:
            # 全部失败（零设备或全部幽灵）→ 退到让 sounddevice 自选（传 None）
            logger.warning("所有候选设备均无法打开，退至 sounddevice 自选")
            winning = None  # type: ignore[assignment]
        return DeviceSource(winning, AudioConfig())  # type: ignore[arg-type]

    def _detector_factory():
        if vad_kind == "silero":
            from backend.vad.detector import SileroVad

            return SileroVad()
        from backend.vad.detector import EnergyVad

        return EnergyVad()

    # 启动时全优先级解析初始设备名
    available_devices = list_input_devices()
    default_idx = get_default_input_index()
    persisted_name = orchestrator.dal.get_setting("audio_input_device")
    env_value = os.environ.get("SOUNDSPEED_AUDIO_DEVICE")

    initial_device_name, source = resolve_device_name(
        persisted_name=persisted_name,
        env_value=env_value,
        devices=available_devices,
        default_index=default_idx,
    )
    logger.info(
        "实时 ASR 初始设备：%r（来源=%s）",
        initial_device_name,
        source,
    )

    session = LiveAsrSession(
        runner=runner,
        publish=orchestrator.publish,
        source_factory=_source_factory,
        vad_config=VadConfig(),
        detector_factory=_detector_factory,
        default_device=initial_device_name,  # 存名字
    )

    # 后台预热模型（首次含下载），不阻塞启动
    threading.Thread(target=runner.warmup, name="asr-warmup", daemon=True).start()
    logger.info("实时 ASR 已启用（VAD=%s, model=%s）", vad_kind, model_size)
    return session


def _maybe_wire_diarization(orchestrator, live_asr):  # -> DiarizationEngine | None
    """在 orchestrator 上挂载 DiarizationBackfill（可选）。

    要求：
      SOUNDSPEED_HF_TOKEN  HuggingFace access token（gated 模型必须）
      SOUNDSPEED_DIARIZATION=0  显式关闭（默认启用，但无 HF token 时自动跳过）
    """
    if os.environ.get("SOUNDSPEED_DIARIZATION") == "0":
        logger.info("diarization 已关闭（SOUNDSPEED_DIARIZATION=0）")
        return None

    if live_asr is None:
        logger.info("diarization 跳过：live ASR 未启用")
        return None

    hf_token = os.environ.get("SOUNDSPEED_HF_TOKEN") or os.environ.get("HF_TOKEN")
    if not hf_token:
        logger.warning(
            "diarization 跳过：未设置 SOUNDSPEED_HF_TOKEN / HF_TOKEN。"
            "如需启用说话人标签，请设置该环境变量。"
        )
        return None

    hf_cache_dir = str(Path(
        os.environ.get("SOUNDSPEED_HF_CACHE_DIR", "./models/huggingface")
    ).resolve())

    from backend.diarization.backfill import DiarizationBackfill
    from backend.diarization.engine import DiarizationEngine
    from backend.diarization.registry import SpeakerRegistry

    engine = DiarizationEngine(hf_token=hf_token, cache_dir=hf_cache_dir)
    registry = SpeakerRegistry()  # 无状态映射器；候选演员由 backfill 从 DAL.list_take_speakers 传入

    # l2_trigger 在 backfill.run() 中由 orchestrator._on_take_end 动态注入
    backfill = DiarizationBackfill(
        dal=orchestrator.dal,
        buffer=live_asr.audio_buffer,
        engine=engine,
        registry=registry,
        publish=orchestrator.publish,
        l2_trigger=None,  # 由 _on_take_end 注入
    )

    # 将 backfill 注入 orchestrator 的 deps
    orchestrator._deps.diarization_backfill = backfill
    logger.info("diarization 已启用（pyannote.audio 4.0）")

    # 把预热回调存到 orchestrator，由 app lifespan startup 在 event loop 启动后触发
    async def _warmup():
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            logger.info("diarization 预热：开始下载/加载 pyannote 模型（后台进行）…")
            await loop.run_in_executor(None, engine._ensure_loaded)
            logger.info("diarization 预热完成，模型已就绪")
        except Exception:
            logger.warning("diarization 预热失败（不影响正常功能，首次 take 时会重试）", exc_info=True)

    orchestrator._warmup_coro = _warmup
    return engine
