"""python -m backend.api 启动入口。

读取 env：
  SOUNDSPEED_DB       数据库文件路径（默认 <repo>/data/soundspeed.db，持久；不存在则自动创建）
  ADMIN_TOKEN         管理员 token（缺失则由 resolve_admin_token 随机生成 + console 打印）
  HOST                监听地址（默认 0.0.0.0）
  PORT                监听端口（默认 8000）
  SOUNDSPEED_DEV      dev 模式（=1 时挂载 /api/v1/debug/asr + 自动播种 active scene）
  SOUNDSPEED_PROFILE  显存档位（import=Gemma 独占 GPU/录制关；record=录制占 GPU/Gemma 退 CPU）；
                      只设默认，个别开关显式设置仍优先；8GB 卡三模型不能共存
  SOUNDSPEED_LIVE_ASR 实时 ASR 开关（默认启用；=0 显式关闭）
  SOUNDSPEED_ASR_MODEL  Whisper 模型大小（默认 "medium-q8_0" 量化版；fp16 基线设 "medium"）
  SOUNDSPEED_MODELS_DIR   Whisper 模型存放目录（默认 ./models/whisper/）
  SOUNDSPEED_HF_TOKEN     HuggingFace access token（pyannote 等 gated 模型必须）
  SOUNDSPEED_HF_CACHE_DIR pyannote 等 HF 模型缓存目录（默认 ./models/huggingface/）
  SOUNDSPEED_DIARIZATION  说话人分离开关（默认启用；=0 显式关闭）
  SOUNDSPEED_AUDIO_DEVICE 指定输入设备索引或名称（默认首个可用输入设备）
  SOUNDSPEED_VAD      VAD 探测器：silero（默认）| energy（无依赖 fallback）

跨平台（pathlib + env，无 shell 分支）。
"""
from __future__ import annotations

import logging
import os

if __name__ == "__main__":
    import uvicorn

    from backend.api.entrypoint import build_app

    # backend.* 日志默认随 SOUNDSPEED_LOG_LEVEL（默认 INFO）输出，使 diarization 耗时 /
    # 回填段数 / ASR 启用等 logger.info 可见（uvicorn 自身日志不受影响）。
    log_level = os.environ.get("SOUNDSPEED_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("backend").setLevel(log_level)

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(build_app(), host=host, port=port)
