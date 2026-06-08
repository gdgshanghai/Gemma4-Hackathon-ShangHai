"""QP L3 真模型 e2e 验收（@pytest.mark.smoke + skipif(not GEMMA_MODEL_PATH)，未设则 skip）。

全链路：真权重跑完整 `run_qp_query`（场次目录注入 + 两步走循环 + executor 只读查询），
确认 hero 问题端到端答得对。底层假设 6/7 已由 Task 7.5 probe 钉死，本 task 是整合验收。

复用单一 service 实例跑多个 hero 问题，减少模型多次加载（llama.cpp Metal 退出期有已知
teardown 崩溃；结果在崩溃前产出，不影响断言）。跑法：
  GEMMA_MODEL_PATH=<gguf 路径> uv run pytest backend/tests/test_qp_smoke.py -q -s
"""
from __future__ import annotations

import os

import pytest

from backend.db.dal import DAL
from backend.llm.service import LLMService, _reset_service

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not os.environ.get("GEMMA_MODEL_PATH"),
        reason="GEMMA_MODEL_PATH 未设置，跳过真模型 e2e",
    ),
]


def _seed(tmp_path) -> DAL:
    """种一个场次：Scene_1（室内/日/客厅）+ 3 个 take + 2 角色剧本。"""
    dal = DAL(tmp_path / "qp_smoke.db")
    sid = dal.get_or_create_scene(
        "Scene_1", int_ext="室内", time_of_day="日", location="客厅"
    )[0]
    dal.start_take(sid, "", 1000.0)
    dal.start_take(sid, "", 1001.0)
    dal.start_take(sid, "", 1002.0)
    script_id = dal.insert_script(sid, "raw")
    dal.insert_script_line(script_id, 1, "李雷", "你好，韩梅梅。")
    dal.insert_script_line(script_id, 2, "韩梅梅", "好久不见，李雷。")
    return dal


@pytest.mark.asyncio
async def test_qp_hero_questions_end_to_end(tmp_path) -> None:
    """三个 hero 问题端到端：拍了多少条→3、在哪拍→客厅、几个角色→2。复用单一 service。"""
    from backend.pipelines.qp_query import run_qp_query

    _reset_service()
    service = LLMService()
    dal = _seed(tmp_path)
    try:
        a1 = await run_qp_query(
            text="第一场一共拍了多少条？", dal=dal, service=service, timeout=180.0
        )
        print("\n[Q1 count_takes]", repr(a1))

        a2 = await run_qp_query(
            text="第一场在哪拍的？", dal=dal, service=service, timeout=180.0
        )
        print("\n[Q2 get_scene_info]", repr(a2))

        a3 = await run_qp_query(
            text="第一场有几个角色？", dal=dal, service=service, timeout=180.0
        )
        print("\n[Q3 list_characters]", repr(a3))

        # hero 验收断言（多跳循环跑通 + 数据对）
        assert a1 and "3" in a1, f"Q1 期望含 '3'，实得：{a1!r}"
        assert a2 and "客厅" in a2, f"Q2 期望含 '客厅'，实得：{a2!r}"
        assert a3 and ("2" in a3 or "两" in a3), f"Q3 期望含 '2/两'，实得：{a3!r}"
    finally:
        await service.aclose()
        dal.close()
