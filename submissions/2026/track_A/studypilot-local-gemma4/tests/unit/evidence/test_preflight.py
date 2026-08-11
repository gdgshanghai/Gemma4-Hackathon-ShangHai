from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.orchestration.lm_studio import LMStudioClient
from scripts.lm_studio_preflight import PreflightFailure, run_preflight


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"


def _metadata(*, loaded: bool = True, tool_use: bool = True) -> dict[str, Any]:
    return {
        "data": [
            {
                "id": MODEL,
                "state": "loaded" if loaded else "not-loaded",
                "capabilities": ["tool_use"] if tool_use else ["vision"],
                "quantization": "Q4_K_M",
            }
        ]
    }


def _first_turn() -> dict[str, Any]:
    return {
        "id": "chat-first",
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "probe-call-1",
                            "type": "function",
                            "function": {
                                "name": "get_planning_context",
                                "arguments": '{"probe":"native_function_calling"}',
                            },
                        }
                    ],
                },
            }
        ],
    }


def _second_turn(content: str | None = "Native function calling works.") -> dict[str, Any]:
    return {
        "id": "chat-second",
        "model": MODEL,
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }


def _client(items: list[dict[str, Any]]) -> tuple[LMStudioClient, list[dict[str, Any]]]:
    queue = list(items)
    payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            payloads.append(json.loads(request.content))
        return httpx.Response(200, json=queue.pop(0))

    return (
        LMStudioClient(BASE_URL, MODEL, transport=httpx.MockTransport(handler)),
        payloads,
    )


def test_injected_transport_writes_sanitized_synthetic_provenance(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "first-real-fc.json"
    client, payloads = _client([_metadata(), _first_turn(), _second_turn()])

    evidence = run_preflight(client, evidence_path=evidence_path)

    assert evidence["provenance"] == "synthetic_transport"
    assert evidence["configured_model"] == MODEL
    assert evidence["model_state"] == "loaded"
    assert evidence["capabilities"] == ["tool_use"]
    assert evidence["first_finish_reason"] == "tool_calls"
    assert evidence["first_content_empty"] is True
    assert evidence["tool_name"] == "get_planning_context"
    assert evidence["tool_call_id"] == "probe-call-1"
    assert evidence["validated_args"] == {"probe": "native_function_calling"}
    assert evidence["second_finish_reason"] == "stop"
    assert len(evidence["first_request_sha256"]) == 64
    assert len(evidence["second_response_sha256"]) == 64
    assert json.loads(evidence_path.read_text("utf-8")) == evidence
    assert [payload["tool_choice"] for payload in payloads] == ["required", "none"]
    assert [payload["max_tokens"] for payload in payloads] == [1024, 1024]
    assert payloads[1]["messages"][-2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "probe-call-1",
                "type": "function",
                "function": {
                    "name": "get_planning_context",
                    "arguments": '{"probe":"native_function_calling"}',
                },
            }
        ],
    }
    assert payloads[1]["messages"][-1]["tool_call_id"] == "probe-call-1"


@pytest.mark.parametrize(
    "items",
    [
        [_metadata(loaded=False)],
        [_metadata(tool_use=False)],
        [_metadata(), _second_turn("skipped tool")],
        [_metadata(), _first_turn(), _second_turn("")],
        [_metadata(), _first_turn(), _second_turn(None)],
    ],
)
def test_missing_or_invalid_metadata_or_turn_cannot_emit_success_provenance(
    tmp_path: Path,
    items: list[dict[str, Any]],
) -> None:
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text('{"provenance":"real_lm_native_fc"}', "utf-8")
    client, _ = _client(items)

    with pytest.raises(PreflightFailure):
        run_preflight(client, evidence_path=evidence_path)

    assert not evidence_path.exists()
