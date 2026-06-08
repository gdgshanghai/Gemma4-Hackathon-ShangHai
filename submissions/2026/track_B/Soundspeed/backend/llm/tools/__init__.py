"""LLM 工具包。

子模块：
  script.py    build_l2_tool 构造 report_script_analysis tool dict（Tier 1）
  registry.py  工具注册表（Tier 2 脚手架，当前无生产消费者）

本 __init__ 故意不做任何 import：包导入保持轻量，且不强制拉起 script/registry。
调用方按需直接 import 子模块：
  from backend.llm.tools.script import build_l2_tool
  from backend.llm.tools.registry import get_tool_schema, ...
"""
