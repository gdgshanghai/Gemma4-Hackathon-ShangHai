"""Import 顺序无关性回归测试。

历史坑：backend/pipelines/__init__.py 一旦 eager 再导出 l2_take/np_note，就会形成
config → tools.script → pipelines.l2_constants → pipelines/__init__（eager 拉 l2_take）
→ l2_take → config.TASK_CONFIG（此时未绑定）→ ImportError 的循环。

正常 app 入口先 import pipelines 子模块掩盖了它，全量 pytest 也因收集顺序碰巧不炸；
但任何以 backend.llm.config / backend.llm.service 为「首个 backend import」的脚本或
单文件测试（如 `pytest backend/tests/test_llm_service.py` 单跑）会直接崩，且 traceback
指向 l2_take 而非 config，排查成本高。

用子进程把目标模块作为首个 import，确保冷启动无循环。
"""

import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["backend.llm.config", "backend.llm.service"])
def test_module_imports_cold_without_cycle(module: str) -> None:
    """把 <module> 作为新进程里首个 backend import，必须干净导入（无循环 ImportError）。"""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{module} 冷启动 import 失败（疑似循环 import）：\n{result.stderr}"
    )
