"""
工具（函数）注册表 —— Gemma 4 原生函数调用的 schema 定义。

设计理念（合规 + 安全的核心）：
  把「不能交给大模型自由发挥」的事，下沉成确定性的 Python 函数，由模型*调用*而非*臆造*：
    - 风险评估  → 规则评分函数（assess_pcos_risk），杜绝 LLM「下诊断」
    - 知识问答  → 指南来源的 RAG 检索（lookup_pcos_knowledge），保证医学准确性
    - 危机干预  → 强制触发热线（escalate_to_crisis_support），安全不靠 prompt 自觉
    - 记录类    → 写入本地档案（record_symptom / log_menstrual_period）
  这正是「深度利用原生函数调用，而非简单 Prompt 工程」。
"""
from __future__ import annotations

from typing import Any, Callable

# OpenAI 兼容的工具 schema（Gemma 4 原生解析）
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "record_symptom",
            "description": "把用户描述的某个症状记录到她的本地健康档案，供后续对话引用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom_type": {
                        "type": "string",
                        "enum": ["月经", "痤疮", "多毛", "体重", "脱发", "情绪", "血糖", "其他"],
                        "description": "症状类别",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["轻", "中", "重"],
                        "description": "用户主诉的严重程度",
                    },
                    "note": {"type": "string", "description": "原文描述或补充细节"},
                },
                "required": ["symptom_type", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_menstrual_period",
            "description": "记录一次月经的开始日期与经量，自动计算周期。",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "flow_level": {
                        "type": "integer",
                        "minimum": 1, "maximum": 5,
                        "description": "经量 1（极少）-5（极多）",
                    },
                },
                "required": ["start_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assess_pcos_risk",
            "description": (
                "基于已收集的症状，运行【确定性规则评分】给出初步『需要关注』的提示。"
                "注意：这不是诊断，只输出关注等级与建议就医，禁止据此宣称用户患病。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "irregular_cycle": {"type": "boolean", "description": "月经周期是否长期不规律/稀发"},
                    "hyperandrogen_signs": {"type": "boolean", "description": "是否有痤疮/多毛/脱发等高雄表现"},
                    "metabolic_signs": {"type": "boolean", "description": "是否有血糖偏高/胰岛素抵抗/体重明显增加"},
                },
                "required": ["irregular_cycle", "hyperandrogen_signs", "metabolic_signs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_pcos_knowledge",
            "description": (
                "在【指南来源的本地知识库】中检索 PCOS 相关问题的循证答案，"
                "用于知识答疑，避免模型凭空生成不准确的医学内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "用户的医学/健康问题"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_clinic_checklist",
            "description": "根据用户最关心的问题与已记录的症状，生成一份『就诊小抄』。",
            "parameters": {
                "type": "object",
                "properties": {
                    "main_concern": {"type": "string", "description": "用户本次就诊最想解决的问题"},
                },
                "required": ["main_concern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_lab_report",
            "description": (
                "【多模态】解析用户上传的化验单/B 超报告图片，抽取结构化指标"
                "（如性激素六项、空腹胰岛素、卵巢多囊样改变等）。需用户显式授权。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_ref": {"type": "string", "description": "已授权上传的图片引用 ID"},
                },
                "required": ["image_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_crisis_support",
            "description": (
                "当识别到自伤念头、剧烈腹痛/大量出血、突发视力模糊严重头痛等危险信号时，"
                "【强制】触发危机干预：返回心理援助热线/急诊引导，并停止常规闲聊。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "signal": {
                        "type": "string",
                        "enum": ["self_harm", "acute_physical", "severe_other"],
                        "description": "危险信号类别",
                    },
                },
                "required": ["signal"],
            },
        },
    },
]


# name -> 可调用实现（在 __init__ 中装配，避免循环导入）
TOOL_IMPLEMENTATIONS: dict[str, Callable[..., dict[str, Any]]] = {}


def register(name: str, fn: Callable[..., dict[str, Any]]) -> None:
    TOOL_IMPLEMENTATIONS[name] = fn


def dispatch(name: str, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """执行某个工具；context 携带 user_id、档案等运行期信息。"""
    impl = TOOL_IMPLEMENTATIONS.get(name)
    if impl is None:
        return {"error": f"unknown tool: {name}"}
    return impl(arguments, context)
