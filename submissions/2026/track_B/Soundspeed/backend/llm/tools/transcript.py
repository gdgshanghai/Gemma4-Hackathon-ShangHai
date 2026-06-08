"""QP 工具家（FC spec §3.3 预留）：5 个 build_*_tool() schema + build_qp_tools()。

executor（Task 5）也住本模块，与 schema 共置。本模块只 import 中性叶子，
DAL 仅 TYPE_CHECKING——避开 config→tools→pipeline→config 循环（D-QP-09）。
所有参数扁平标量（spec §4）：auto 跳的 FunctionGemma 字符串解析对扁平标量稳，
对嵌套数组截断崩溃。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.db.dal import DAL

# count_takes / get_scene_info / list_characters 的 scene_ref 参数说明同源（改文案只改一处）。
_SCENE_REF_DESC = "场次引用，如 '第3场' / '3' / 'Scene_3'"


def build_count_takes_tool() -> dict:
    """构造 count_takes OpenAI 风格 tool dict。

    Returns:
        type="function"，name="count_takes" 的工具字典。
    """
    return {
        "type": "function",
        "function": {
            "name": "count_takes",
            "description": "统计某场次已拍摄的 take 条数（已排除软删，可选按状态过滤）。问「第N场拍了多少条」用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_ref": {
                        "type": "string",
                        "description": _SCENE_REF_DESC,
                    },
                    "status": {
                        "type": "string",
                        "enum": ["keep", "ng", "pass", "tbd"],
                        "description": "可选状态过滤：keep/ng/pass/tbd，不填则统计全部",
                    },
                },
                "required": ["scene_ref"],
            },
        },
    }


def build_get_scene_info_tool() -> dict:
    """构造 get_scene_info OpenAI 风格 tool dict。

    Returns:
        type="function"，name="get_scene_info" 的工具字典。
    """
    return {
        "type": "function",
        "function": {
            "name": "get_scene_info",
            "description": "返回某场次的地点/内外景/时间/拍摄日期/角色数。问「第N场在哪拍」用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_ref": {
                        "type": "string",
                        "description": _SCENE_REF_DESC,
                    },
                },
                "required": ["scene_ref"],
            },
        },
    }


def build_list_characters_tool() -> dict:
    """构造 list_characters OpenAI 风格 tool dict。

    Returns:
        type="function"，name="list_characters" 的工具字典。
    """
    return {
        "type": "function",
        "function": {
            "name": "list_characters",
            "description": "返回某场次剧本里出现的角色清单。问「这场有几个角色/都有谁」用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "scene_ref": {
                        "type": "string",
                        "description": _SCENE_REF_DESC,
                    },
                },
                "required": ["scene_ref"],
            },
        },
    }


def build_search_script_lines_tool() -> dict:
    """构造 search_script_lines OpenAI 风格 tool dict。

    Returns:
        type="function"，name="search_script_lines" 的工具字典。
    """
    return {
        "type": "function",
        "function": {
            "name": "search_script_lines",
            "description": "按关键词全文检索剧本台词，返回匹配行。问「哪句台词提到X / 某句台词在第几行」用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要检索的台词关键词",
                    },
                    "scene_ref": {
                        "type": "string",
                        "description": "可选场次引用，限定检索范围；不填则全剧本检索",
                    },
                },
                "required": ["query"],
            },
        },
    }


def build_query_database_tool() -> dict:
    """构造 query_database OpenAI 风格 tool dict（万能笔）。

    Returns:
        type="function"，name="query_database" 的工具字典。
    """
    return {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "万能笔：当上面四个工具都覆盖不了时，写一条只读 SQL 直接查数据库。"
                "只允许 SELECT。主要表：scenes(scene_id,scene_code,location,int_ext,time_of_day,shoot_date)、"
                "takes(take_id,scene_id,shot,take_number,status,deleted_at)、"
                "script_lines(line_no,character,text,script_id)、scripts(script_id,scene_id)。"
                "软删行 deleted_at IS NOT NULL，统计 take 记得加 deleted_at IS NULL。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "一条只读 SELECT 语句（单句，不要分号分隔多句）",
                    },
                },
                "required": ["sql"],
            },
        },
    }


def build_qp_tools() -> list[dict]:
    """返回 QP 全部 5 个工具 schema（顺序固定，供 config.query_session 与测试用）。"""
    return [
        build_count_takes_tool(),
        build_get_scene_info_tool(),
        build_list_characters_tool(),
        build_search_script_lines_tool(),
        build_query_database_tool(),
    ]


# ---------------------------------------------------------------------------
# executor（spec §5.3：executor(args, dal) -> dict；DAL 读全走只读连接，D-QP-12）
# ---------------------------------------------------------------------------

_SCENE_NOT_FOUND = "找不到场次 {ref!r}，数据库里没有这一场（不要用相近场次顶替）。"


def count_takes_executor(args: dict, dal: "DAL") -> dict:
    ref = str(args.get("scene_ref") or "")  # 整数 7 → "7"，None/缺失 → ""
    status = args.get("status")
    scene_id = dal.resolve_scene_id(ref)
    if scene_id is None:
        return {"error": _SCENE_NOT_FOUND.format(ref=ref)}
    result: dict = {"scene_ref": ref, "count": dal.count_takes(scene_id, status=status)}
    if status is not None:
        result["status"] = status
    return result


def get_scene_info_executor(args: dict, dal: "DAL") -> dict:
    ref = str(args.get("scene_ref") or "")
    scene_id = dal.resolve_scene_id(ref)
    if scene_id is None:
        return {"error": _SCENE_NOT_FOUND.format(ref=ref)}
    info = dal.get_scene_info(scene_id)
    if info is None:
        return {"error": _SCENE_NOT_FOUND.format(ref=ref)}
    return info


def list_characters_executor(args: dict, dal: "DAL") -> dict:
    ref = str(args.get("scene_ref") or "")
    scene_id = dal.resolve_scene_id(ref)
    if scene_id is None:
        return {"error": _SCENE_NOT_FOUND.format(ref=ref)}
    chars = dal.list_characters(scene_id)
    return {"scene_ref": ref, "characters": chars, "count": len(chars)}


def search_script_lines_executor(args: dict, dal: "DAL") -> dict:
    query = str(args.get("query") or "")
    if not query.strip():
        return {"error": "query 不能为空"}
    ref = args.get("scene_ref")
    scene_id = None
    if ref:
        scene_id = dal.resolve_scene_id(str(ref))
        if scene_id is None:
            return {"error": _SCENE_NOT_FOUND.format(ref=ref)}
    try:
        matches = dal.search_script_lines(query, scene_id=scene_id)
    except Exception as exc:  # FTS 语法错误等，包成 error 让模型自纠
        return {"error": f"检索失败：{exc}"}
    return {"query": query, "matches": matches, "count": len(matches)}


def query_database_executor(args: dict, dal: "DAL") -> dict:
    sql = str(args.get("sql") or "")
    if not sql.strip():
        return {"error": "sql 为空"}
    return dal.query_readonly(sql)
