"""backend.llm 层的领域异常（轻量，无第三方依赖，可被 orchestrator 安全导入）。"""

from __future__ import annotations


class ModelUnavailableError(Exception):
    """多模态模型不可用——音频/图像推理无法进行。

    在**产生地**抛出，而非靠下游 isinstance 嗅探宽泛内建异常类型反推：
    - `client.py`：单实例退纯文本（mmproj 缺失/下载失败），无 handler 却收到 audio。
    - `multimodal.py::_init_mtmd_context`：mmproj 不支持所需模态（缺 audio/vision 投影器）。

    orchestrator._finalize_np 干净映射为 `note.failed(model_unavailable)`，
    与 `NPParseError → parse_error` 对称。
    """
