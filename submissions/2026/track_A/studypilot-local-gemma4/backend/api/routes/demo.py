"""Routes available only when the isolated demonstration mode is enabled."""

from __future__ import annotations

from datetime import date, time
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.runtime import (
    AppRuntime,
    IdempotencyKeyHeader,
    get_runtime,
    get_trace_id,
)
from backend.contracts.demo import (
    DemoCalibrationGroup,
    DemoResetRequest,
    DemoScenarioResponse,
)
from backend.contracts.calibration_tools import CalibrationSubject, CalibrationTaskType
from backend.contracts.evening import EveningResponse
from backend.errors import NotFoundError


router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


SCHOOL_BRIEF_TEXT = """【模拟情景：初一开学第六周·多科忙碌周一】
语文（明早检查）：阅读《朝花夕拾》15页并摘录两处，完成一份作文提纲。
数学（明早检查）：完成有理数混合运算12题，订正课堂错题2题。
英语（明早检查）：Unit 2词汇20个，背诵课文一段，完成练习册2页。
历史（周五提交）：完成“中国早期人类”时间轴5个节点。
地理（明早检查）：完成经纬网练习8题，订正课堂小测。
生物（周三检查）：标注显微镜结构图，预习下一课。
道德与法治（周五提交）：整理“中学生活”课堂笔记一页。"""

CHILD_REPORT_TEXT = (
    "今天我知道的作业都在这里：语文《朝花夕拾》在学校读了5页，还剩10页和两处摘录，作文提纲还没做；"
    "数学12题已经做完前6题，错题还没订正；英语练习册做完1页，词汇和课文背诵都没做；"
    "历史时间轴完成了一半；生物结构图和预习没做；道法笔记整理了一半。"
    "我最想先做数学，语文阅读和英语背诵最不想碰。"
    "我说完了，没有其他作业。"
)

WEEKLY_CALIBRATION_TEXT = (
    "本周可核对观察：最近三次数学书面作业分别用时28、30、29分钟；"
    "最近三次语文阅读分别用时18、20、19分钟；两次英语背诵分别用时14、15分钟，开始前都需要提醒一次；"
    "两次地理读图任务分别用时14、15分钟；20:30以后开始背诵类任务时明显更慢。"
    "以上只作为本周观察，请先生成建议，由家长确认后再更新画像。"
)

SCENARIO = DemoScenarioResponse(
    scenario_id="grade7-busy-monday-v2",
    label="初一开学第六周 · 多科忙碌周一",
    planning_date=date(2026, 10, 12),
    start_time=time(19, 30),
    sleep_time=time(22, 20),
    school_brief_text=SCHOOL_BRIEF_TEXT,
    child_report_text=CHILD_REPORT_TEXT,
    weekly_calibration_text=WEEKLY_CALIBRATION_TEXT,
    weekly_calibration_groups=(
        DemoCalibrationGroup(
            subject=CalibrationSubject.MATHEMATICS,
            task_type=CalibrationTaskType.WRITTEN,
            conservative_minutes=30,
        ),
        DemoCalibrationGroup(
            subject=CalibrationSubject.CHINESE,
            task_type=CalibrationTaskType.READING,
            conservative_minutes=20,
        ),
        DemoCalibrationGroup(
            subject=CalibrationSubject.ENGLISH,
            task_type=CalibrationTaskType.RECITATION,
            conservative_minutes=15,
        ),
        DemoCalibrationGroup(
            subject=CalibrationSubject.GEOGRAPHY,
            task_type=CalibrationTaskType.MAP_READING,
            conservative_minutes=15,
        ),
    ),
)


def _require_demo(runtime: AppRuntime) -> None:
    if not runtime.settings.demo_mode:
        raise NotFoundError("demo_mode", "disabled")


@router.get("/scenario", response_model=DemoScenarioResponse)
def get_demo_scenario(
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
) -> DemoScenarioResponse:
    _require_demo(runtime)
    return SCENARIO


@router.post("/evenings/today/reset", response_model=EveningResponse)
def reset_demo_evening(
    body: DemoResetRequest,
    idempotency_key: IdempotencyKeyHeader,
    runtime: Annotated[AppRuntime, Depends(get_runtime)],
    trace_id: Annotated[str, Depends(get_trace_id)],
) -> EveningResponse:
    _require_demo(runtime)
    return runtime.evening_service.reset_demo_today(
        expected_session_id=body.expected_session_id,
        planning_date=SCENARIO.planning_date,
        start_time=SCENARIO.start_time,
        sleep_time=SCENARIO.sleep_time,
        caller_idempotency_key=idempotency_key,
        trace_id=trace_id,
    )
