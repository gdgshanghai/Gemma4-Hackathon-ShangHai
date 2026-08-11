from __future__ import annotations

import pytest

from backend.config import load_settings
from backend.orchestration.lm_studio import (
    LMStudioClient,
    ModelProtocolError,
    ModelUnavailableError,
)
from scripts.lm_studio_preflight import run_preflight


pytestmark = pytest.mark.real_lm


def test_real_exact_loaded_model_completes_native_two_turn_fc() -> None:
    settings = load_settings()
    client = LMStudioClient.from_settings(settings)

    evidence = run_preflight(client)

    assert evidence["configured_model"] == "gemma-4-26b-a4b-it"
    assert evidence["model_state"] == "loaded"
    assert "tool_use" in evidence["capabilities"]
    assert evidence["first_finish_reason"] == "tool_calls"
    assert evidence["tool_name"] == "get_planning_context"
    assert evidence["tool_call_id"]
    assert evidence["second_finish_reason"] == "stop"
    assert evidence["provenance"] == "real_lm_native_fc"


def test_real_max_tokens_boundary_is_reported_as_truncation() -> None:
    client = LMStudioClient.from_settings(load_settings())

    with pytest.raises(ModelProtocolError) as raised:
        client.chat_completion(
            [
                {
                    "role": "user",
                    "content": (
                        "Synthetic test only. Write a detailed numbered list of exactly "
                        "one hundred different study tips."
                    ),
                }
            ],
            [],
            "none",
            max_tokens=1,
        )

    assert raised.value.code == "model_output_truncated"


def test_closed_local_port_returns_clean_unavailable_error() -> None:
    client = LMStudioClient(
        "http://127.0.0.1:1/v1",
        "gemma-4-26b-a4b-it",
        timeout=1.0,
    )

    with pytest.raises(ModelUnavailableError) as raised:
        client.get_model_metadata()

    assert raised.value.code in {"model_connection_refused", "model_timeout"}
    assert "127.0.0.1" not in str(raised.value)
