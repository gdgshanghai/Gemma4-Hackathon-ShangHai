"""build_app 启动逻辑测试。"""

import os

import pytest

from backend.core.session import SessionState
from backend.db.dal import DAL


def test_restore_active_scene_sets_session(tmp_dal: DAL) -> None:
    """启动恢复：DB 有活跃场 → session.scene_id 被设上（重启后 NP 有上下文，不再静默空上下文）。"""
    from backend.api.entrypoint import restore_active_scene  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_restore")
    tmp_dal.set_active_scene(scene_id)
    session = SessionState()
    assert session.scene_id is None

    restore_active_scene(tmp_dal, session)
    assert session.scene_id == scene_id


def test_restore_active_scene_no_active_is_noop(tmp_dal: DAL) -> None:
    """DB 无活跃场（空库）→ session.scene_id 保持 None，不乱设。"""
    from backend.api.entrypoint import restore_active_scene  # noqa: PLC0415

    session = SessionState()
    restore_active_scene(tmp_dal, session)
    assert session.scene_id is None


def test_restore_active_scene_does_not_restore_take(tmp_dal: DAL) -> None:
    """只恢复活跃场，不恢复活跃 take——录制进程已随重启消失，take_active 必须 False。"""
    from backend.api.entrypoint import restore_active_scene  # noqa: PLC0415

    scene_id = tmp_dal.create_scene("scene_restore2")
    tmp_dal.set_active_scene(scene_id)
    session = SessionState()

    restore_active_scene(tmp_dal, session)
    assert session.scene_id == scene_id
    assert session.take_active is False
    assert session.take_id is None


# ── 显存档位 SOUNDSPEED_PROFILE ─────────────────────────────────────────────────

_VRAM_KEYS = (
    "SOUNDSPEED_PROFILE",
    "SOUNDSPEED_LIVE_ASR",
    "SOUNDSPEED_DIARIZATION",
    "SOUNDSPEED_LLM_GPU_LAYERS",
)


@pytest.fixture
def _clean_vram_env():
    """快照并恢复显存档位相关 env，防止 setdefault 写入泄漏到其它测试。"""
    saved = {k: os.environ.get(k) for k in _VRAM_KEYS}
    for k in _VRAM_KEYS:
        os.environ.pop(k, None)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.mark.usefixtures("_clean_vram_env")
def test_vram_profile_import_gemma_gpu_recording_off() -> None:
    """import 档：录制关、Gemma 全 GPU。"""
    from backend.api.entrypoint import _apply_vram_profile  # noqa: PLC0415

    os.environ["SOUNDSPEED_PROFILE"] = "import"
    _apply_vram_profile()
    assert os.environ["SOUNDSPEED_LIVE_ASR"] == "0"
    assert os.environ["SOUNDSPEED_DIARIZATION"] == "0"
    assert os.environ["SOUNDSPEED_LLM_GPU_LAYERS"] == "-1"


@pytest.mark.usefixtures("_clean_vram_env")
def test_vram_profile_record_gemma_cpu_recording_on() -> None:
    """record 档：录制开、Gemma 退 CPU（让显存给 Whisper/Pyannote）。"""
    from backend.api.entrypoint import _apply_vram_profile  # noqa: PLC0415

    os.environ["SOUNDSPEED_PROFILE"] = "record"
    _apply_vram_profile()
    assert os.environ["SOUNDSPEED_LIVE_ASR"] == "1"
    assert os.environ["SOUNDSPEED_DIARIZATION"] == "1"
    assert os.environ["SOUNDSPEED_LLM_GPU_LAYERS"] == "0"


@pytest.mark.usefixtures("_clean_vram_env")
def test_vram_profile_individual_env_overrides_profile() -> None:
    """个别开关显式设置优先（setdefault 不覆盖）；未设的仍按档位补。"""
    from backend.api.entrypoint import _apply_vram_profile  # noqa: PLC0415

    os.environ["SOUNDSPEED_PROFILE"] = "import"
    os.environ["SOUNDSPEED_LLM_GPU_LAYERS"] = "30"  # 显式：部分 offload
    _apply_vram_profile()
    assert os.environ["SOUNDSPEED_LLM_GPU_LAYERS"] == "30"  # 档位不覆盖
    assert os.environ["SOUNDSPEED_LIVE_ASR"] == "0"  # 未显式者仍按档位


@pytest.mark.usefixtures("_clean_vram_env")
def test_vram_profile_unknown_is_noop() -> None:
    """未知档位 → 跳过，不设任何开关。"""
    from backend.api.entrypoint import _apply_vram_profile  # noqa: PLC0415

    os.environ["SOUNDSPEED_PROFILE"] = "bogus"
    _apply_vram_profile()
    assert "SOUNDSPEED_LIVE_ASR" not in os.environ
    assert "SOUNDSPEED_LLM_GPU_LAYERS" not in os.environ


@pytest.mark.usefixtures("_clean_vram_env")
def test_vram_profile_unset_is_noop() -> None:
    """不设 SOUNDSPEED_PROFILE → 行为不变（不设任何开关）。"""
    from backend.api.entrypoint import _apply_vram_profile  # noqa: PLC0415

    _apply_vram_profile()
    assert "SOUNDSPEED_LIVE_ASR" not in os.environ
    assert "SOUNDSPEED_DIARIZATION" not in os.environ
    assert "SOUNDSPEED_LLM_GPU_LAYERS" not in os.environ
