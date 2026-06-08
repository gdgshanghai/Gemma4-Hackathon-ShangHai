"""Pipelines 包：各种 LLM Pipeline 的实现。

当前模块：
  l2_take: L2 Pipeline（台词 diff 检测）
  np_note: NP Pipeline（Note 归置）

注：不在此做 eager 再导出。l2_take 在模块级 import config.TASK_CONFIG，而 config 构造
l2_take 配置时又会经 tools.script → l2_constants 触发本包 __init__；一旦这里 eager 拉
l2_take，就形成 config → tools.script → l2_constants → __init__ → l2_take → config 的
循环 import（以 backend.llm.config / service 为首个 import 时直接 ImportError）。消费方
一律从子模块直接 import（from backend.pipelines.l2_take import ... /
from backend.pipelines.np_note import ...）。回归测试见 tests/test_import_hygiene.py。
"""
