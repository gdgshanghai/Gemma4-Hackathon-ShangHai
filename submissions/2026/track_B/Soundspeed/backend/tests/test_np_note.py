"""NP Pipeline 单元测试。"""
import json

import pytest

from backend.pipelines.np_note import (
    NPInput,
    NPParseError,
    _parse_llm_output,
    _build_user_message,
    _build_system_prompt,
)


def test_parse_valid_json():
    output = _parse_llm_output('{"take_id": 1, "category": "issue", "content": "灯光有问题"}')
    assert output.take_id == 1
    assert output.category == "issue"
    assert output.content == "灯光有问题"


def test_parse_default_category():
    output = _parse_llm_output('{"take_id": 2, "content": "test"}')
    assert output.category == "note"
    assert output.content == "test"


def test_parse_markdown_fenced():
    output = _parse_llm_output('```json\n{"take_id": 3, "category": "keep", "content": ""}\n```')
    assert output.take_id == 3
    assert output.category == "keep"
    assert output.content == ""


def test_parse_empty_raises():
    try:
        _parse_llm_output("")
        assert False, "should raise"
    except NPParseError:
        pass


def test_parse_invalid_json_raises():
    try:
        _parse_llm_output("not json")
        assert False, "should raise"
    except NPParseError:
        pass


def test_parse_invalid_category_raises():
    try:
        _parse_llm_output('{"take_id": 1, "category": "invalid"}')
        assert False, "should raise"
    except NPParseError:
        pass


def test_parse_take_id_not_int_raises():
    try:
        _parse_llm_output('{"take_id": "abc", "category": "note"}')
        assert False, "should raise"
    except NPParseError:
        pass


def test_build_user_message_full_scene_shot_take():
    """4.H：当前活跃 take + 历史 take 都渲染成完整 场/镜/次，不再暴露 DB 内部 id 当主键。"""
    input_data = NPInput(
        raw_text="飞机声",
        parsed_category="note",
        current_scene_id=1,
        current_take_id=5,
        take_context=[
            {"take_id": 3, "scene_code": "Scene_1", "shot": "Shot1", "take_number": 1, "summary": "正常"},
            {"take_id": 4, "scene_code": "Scene_1", "shot": "Shot1", "take_number": 2, "summary": "有噪音"},
        ],
        ts=1000.0,
        current_scene_code="Scene_1",
        current_shot="Shot1",
        current_take_number=3,
    )
    msg = _build_user_message(input_data)
    assert "飞机声" in msg
    # 当前活跃 take 渲染成 场/镜/次（第3条），不是裸 DB id
    assert "Scene_1/Shot1/第3条" in msg
    assert "活跃 take ID: 5" not in msg
    # 历史 take 带 shot（per-shot 语义），仍保留 take_id 供模型回引
    assert "Scene_1/Shot1/第1条" in msg
    assert "take_id=3" in msg
    assert "正常" in msg


def test_build_user_message_no_active_take():
    """4.H：无活跃录制时显式注明，历史 take 仍带完整 场/镜/次。"""
    input_data = NPInput(
        raw_text="上一条有什么问题",
        parsed_category="note",
        current_scene_id=1,
        current_take_id=None,
        take_context=[
            {"take_id": 3, "scene_code": "Scene_1", "shot": "Shot1", "take_number": 1, "summary": ""},
        ],
        ts=1000.0,
        current_scene_code="Scene_1",
        current_shot=None,
        current_take_number=None,
    )
    msg = _build_user_message(input_data)
    assert "无活跃录制" in msg
    assert "上一条有什么问题" in msg
    assert "Scene_1/Shot1/第1条" in msg


def test_system_prompt_not_empty():
    prompt = _build_system_prompt()
    assert len(prompt) > 50
    assert "take_id" in prompt


def test_system_prompt_per_shot_semantics():
    """4.H：编号规则对齐 per-shot——「第N条」指当前场当前镜的第 N 条，跨镜/跨场需显式。"""
    prompt = _build_system_prompt()
    assert "当前镜" in prompt
    assert "跨镜" in prompt or "跨场" in prompt


# ---------------------------------------------------------------------------
# 语音 NP runner（4.J-4）：run_np_voice —— 场镜次上下文 + 音频哨兵 → infer_voice → 解析。
# ---------------------------------------------------------------------------


def _voice_tool_call(arguments: dict) -> dict:
    return {
        "id": "call_voice_stub",
        "type": "function",
        "function": {
            "name": "structure_note",
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


class _FakeVoiceLLM:
    """记录 infer_voice_tool 收到的 messages/audio/task_type，并回固定 tool_call。"""

    def __init__(self, arguments: dict) -> None:
        self._arguments = arguments
        self.seen: dict = {}

    async def infer_voice_tool(
        self, messages, audio, task_type, priority=None, timeout=None  # noqa: ANN001
    ) -> dict:
        self.seen.update(
            messages=messages, audio=audio, task_type=task_type, priority=priority
        )
        return _voice_tool_call(self._arguments)


def _voice_input() -> NPInput:
    return NPInput(
        raw_text="",  # 语音路径无文字，正文由模型从音频听
        parsed_category="note",
        current_scene_id=5,
        current_take_id=None,
        take_context=[
            {"take_id": 103, "scene_code": "Scene_1", "shot": "Shot1", "take_number": 3, "summary": ""}
        ],
        ts=123.0,
        current_scene_code="Scene_1",
        current_shot="Shot1",
        current_take_number=None,
    )


@pytest.mark.asyncio
async def test_run_np_voice_parses_output_and_threads_audio() -> None:
    """run_np_voice：组装场镜次 + 音频哨兵 → infer_voice_tool（透传 audio + note_struct）→
    解析 tool_calls[0] → NPOutput（语音也走 forced tool-call）。"""
    from backend.llm.multimodal import AUDIO_SENTINEL  # noqa: PLC0415
    from backend.pipelines.np_note import NPOutput, run_np_voice  # noqa: PLC0415

    fake = _FakeVoiceLLM({"take_id": 103, "category": "keep", "content": "结尾好"})
    out = await run_np_voice(_voice_input(), b"WAVBYTES", fake)  # type: ignore[arg-type]

    assert out == NPOutput(take_id=103, category="keep", content="结尾好")
    assert fake.seen["audio"] == b"WAVBYTES"
    assert fake.seen["task_type"] == "note_struct"

    # user content 为 list，含音频哨兵（multimodal 通道）+ 场镜次文本
    user_msg = fake.seen["messages"][-1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    sentinels = [
        c.get("image_url", {}).get("url")
        for c in user_msg["content"]
        if c.get("type") == "image_url"
    ]
    assert AUDIO_SENTINEL in sentinels
    text_blocks = " ".join(
        c.get("text", "") for c in user_msg["content"] if c.get("type") == "text"
    )
    assert "Scene_1" in text_blocks and "Shot1" in text_blocks


@pytest.mark.asyncio
async def test_run_np_voice_parse_error_propagates() -> None:
    """tool_call.arguments 非法 JSON → NPParseError 上抛（4.I 失败分类对语音同样生效）。"""
    from backend.pipelines.np_note import run_np_voice  # noqa: PLC0415

    class _BadVoice:
        async def infer_voice_tool(self, messages, audio, task_type, priority=None, timeout=None):  # noqa: ANN001
            return {"type": "function", "function": {"name": "structure_note", "arguments": "{not json"}}

    with pytest.raises(NPParseError):
        await run_np_voice(_voice_input(), b"x", _BadVoice())  # type: ignore[arg-type]


def test_voice_system_prompt_mentions_listening() -> None:
    """语音 system prompt 须提示模型「听音频」——否则模型不知道要转写语音。"""
    from backend.pipelines.np_note import _build_voice_system_prompt  # noqa: PLC0415

    prompt = _build_voice_system_prompt()
    assert "音频" in prompt or "语音" in prompt
    assert "take_id" in prompt


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_real_voice_np_smoke() -> None:
    """4.J-5 真模型语音 NP smoke（默认 skip）。

    走产品化路径：run_np_voice → LLMService.infer_voice → 多模态 GemmaClient → 真 Gemma 4 + mmproj。
    需 SOUNDSPEED_SMOKE_VOICE_WAV 指向一段中文语音 WAV，且 mmproj 可解析（本地/cache）。
    手测实证（2026-06-05）：「第三条结尾很好可以用」+ Scene_1/Shot1/take101-103 →
    {take_id:103, keep, '结尾很好，可以用'}，16k/48k 一致，RSS ~6.7GB。
    """
    import os  # noqa: PLC0415

    wav_path = os.environ.get("SOUNDSPEED_SMOKE_VOICE_WAV")
    if not wav_path or not os.path.exists(wav_path):
        pytest.skip("SOUNDSPEED_SMOKE_VOICE_WAV 未设置或文件不存在，跳过语音 smoke")

    from backend.llm.service import (  # noqa: PLC0415
        _reset_service,
        get_service,
        resolve_mmproj_path,
    )
    from backend.pipelines.np_note import run_np_voice  # noqa: PLC0415

    if resolve_mmproj_path(download=False) is None:
        pytest.skip("mmproj 未缓存，跳过语音 smoke")

    inp = NPInput(
        raw_text="",
        parsed_category="note",
        current_scene_id=5,
        current_take_id=None,
        take_context=[
            {"take_id": 103, "scene_code": "Scene_1", "shot": "Shot1", "take_number": 3, "summary": ""}
        ],
        ts=1.0,
        current_scene_code="Scene_1",
        current_shot="Shot1",
        current_take_number=None,
    )

    _reset_service()
    svc = get_service()
    try:
        with open(wav_path, "rb") as f:
            audio = f.read()
        out = await run_np_voice(inp, audio, svc, timeout=120.0)  # type: ignore[arg-type]
        assert isinstance(out.take_id, int)
        assert out.category in ("note", "issue", "keep", "ng", "pass")
        assert isinstance(out.content, str) and out.content.strip()
    finally:
        await svc.aclose()
        _reset_service()
