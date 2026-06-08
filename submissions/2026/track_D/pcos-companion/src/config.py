"""
模型与运行时配置 —— 她健康·PCOS伴侣（赛道 D / Social Good）

设计原则（与《技术报告》一致）：
  - 隐私优先：默认走「端侧 Gemma 4 4B」，敏感对话不出设备 / 不出自有服务器。
  - 分级调度：轻量共情对话 + 函数调用走端侧；多模态化验单解析等重任务，
              在「用户显式授权」后走自托管云端 Gemma 4 26B MoE。
  - 自托管：不调用任何第三方闭源大模型 API，模型权重与推理全部在本团队
            可控的基础设施内（vLLM / Ollama / llama.cpp），满足健康数据合规。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class ModelTier(str, Enum):
    """模型分级。"""
    EDGE = "edge"        # 端侧 / 默认，隐私优先
    CLOUD = "cloud"      # 自托管云端，仅在显式授权的重任务时启用


@dataclass(frozen=True)
class GemmaModelSpec:
    """单个 Gemma 4 规格的部署描述。"""
    name: str                 # 业务别名
    hf_repo: str              # 模型权重标识（可替换为内网镜像）
    served_model: str         # 推理服务暴露的 model 名
    backend: str              # ollama | vllm | llama_cpp
    endpoint: str             # OpenAI 兼容 /v1 端点
    supports_vision: bool     # 是否启用多模态
    quantization: str         # 量化方式（端侧关键）
    purpose: str


# —— 端侧：Gemma 4 4B，Q4_K_M 量化，手机/边缘盒子本地推理 ——
# 选型理由：4B 在「可靠的原生函数调用 + 有温度的共情对话」与「端侧内存占用」
# 之间是甜点位；2B 函数调用稳定性不足，26B/31B 无法在消费级设备本地运行。
EDGE_MODEL = GemmaModelSpec(
    name="xiaonuan-edge",
    hf_repo=os.getenv("GEMMA_EDGE_REPO", "google/gemma-4-4b-it"),
    served_model=os.getenv("GEMMA_EDGE_MODEL", "gemma-4-4b-it-q4"),
    backend=os.getenv("GEMMA_EDGE_BACKEND", "ollama"),
    endpoint=os.getenv("GEMMA_EDGE_ENDPOINT", "http://127.0.0.1:11434/v1"),
    supports_vision=False,
    quantization="Q4_K_M",
    purpose="情绪陪伴对话 + 原生函数调用（隐私优先，默认）",
)

# —— 云端：Gemma 4 26B MoE，多模态，自托管 vLLM ——
# 选型理由：26B MoE 以更低的「激活参数」推理成本逼近 31B Dense 的质量，
# MVP 阶段云端成本更可控；多模态用于解析用户上传的化验单 / B 超报告图片。
CLOUD_MODEL = GemmaModelSpec(
    name="xiaonuan-cloud",
    hf_repo=os.getenv("GEMMA_CLOUD_REPO", "google/gemma-4-26b-moe-it"),
    served_model=os.getenv("GEMMA_CLOUD_MODEL", "gemma-4-26b-moe-it"),
    backend=os.getenv("GEMMA_CLOUD_BACKEND", "vllm"),
    endpoint=os.getenv("GEMMA_CLOUD_ENDPOINT", "http://127.0.0.1:8000/v1"),
    supports_vision=True,
    quantization="bf16",
    purpose="多模态化验单解析 + 复杂知识问答（显式授权后启用）",
)


@dataclass
class RuntimeConfig:
    default_tier: ModelTier = ModelTier(os.getenv("DEFAULT_TIER", "edge"))
    max_tool_iterations: int = int(os.getenv("MAX_TOOL_ITERATIONS", "5"))
    request_timeout_s: int = int(os.getenv("REQUEST_TIMEOUT_S", "30"))
    temperature: float = float(os.getenv("TEMPERATURE", "0.6"))
    top_p: float = float(os.getenv("TOP_P", "0.9"))
    # 心理援助热线（危机干预函数使用）
    crisis_hotline: str = os.getenv("CRISIS_HOTLINE", "400-161-9995")
    models: dict = field(default_factory=lambda: {
        ModelTier.EDGE: EDGE_MODEL,
        ModelTier.CLOUD: CLOUD_MODEL,
    })

    def model_for(self, tier: ModelTier) -> GemmaModelSpec:
        return self.models[tier]


CONFIG = RuntimeConfig()
