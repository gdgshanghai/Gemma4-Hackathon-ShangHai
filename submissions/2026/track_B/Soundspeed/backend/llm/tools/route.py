"""route_memo 工具（入口调度器 forced 二分类，对标 tools/note.py）。

build_route_memo_tool() 返回 OpenAI function calling 风格 tool dict：模型读这条 memo
是「记录（note）」还是「查询（query）」。Tier-1 forced + grammar，零解析风险。

kind enum 是字面量 ["note","query"]，本模块 import-neutral（不拉 pipelines），
config 可模块级 eager import（无循环 import 风险，同 build_l2_tool）。
"""

from __future__ import annotations

# 工具名（config tool_choice / registry 注册 / 本构造器三处须一致）。
ROUTE_TOOL_NAME = "route_memo"


def build_route_memo_tool() -> dict:
    """构造 route_memo OpenAI 风格 tool dict（单参 kind: note|query）。"""
    return {
        "type": "function",
        "function": {
            "name": ROUTE_TOOL_NAME,
            "description": (
                "判断录音师这条输入是「记录一条备注」还是「查询场记信息」。"
                "想知道/查/问某个事实（拍了多少条、在哪拍、有几个角色、第几场……）→ query；"
                "对某条素材的评价、好坏、问题、要保要过要废 → note。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["note", "query"],
                        "description": "note=记录备注；query=查询信息。",
                    },
                },
                "required": ["kind"],
            },
        },
    }
