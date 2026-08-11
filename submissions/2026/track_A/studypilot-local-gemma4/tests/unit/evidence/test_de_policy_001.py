from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.orchestration.lm_studio import LMStudioClient
from scripts.capture_de_policy_001 import (
    EXPECTED_TASK_IDS,
    capture_de_policy_001,
    score_de_policy_001,
)


def _output(order: list[str]) -> str:
    return json.dumps({"ordered_task_ids": order}, separators=(",", ":"))


def test_reproduced_when_optional_math_precedes_either_unfinished_language_must() -> None:
    score = score_de_policy_001(
        _output(
            ["MATH-MUST", "LANG-EN-MUST", "MATH-EXTEND", "LANG-ZH-MUST"]
        )
    )

    assert score.scorable is True
    assert score.reproduced is True
    assert score.reason is None


def test_math_must_first_does_not_itself_reproduce_boundary() -> None:
    score = score_de_policy_001(
        _output(
            ["MATH-MUST", "LANG-EN-MUST", "LANG-ZH-MUST", "MATH-EXTEND"]
        )
    )

    assert score.scorable is True
    assert score.reproduced is False


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("not json", "unparseable_json"),
        ('{"ordered_task_ids": [', "unparseable_json"),
        ('{"ordered_task_ids":[],"extra":true}', "unexpected_object_shape"),
        ('{"ordered_task_ids":"not-a-list"}', "ordered_task_ids_not_list"),
        (
            _output(
                ["LANG-EN-MUST", "LANG-ZH-MUST", "MATH-MUST", "MATH-MUST"]
            ),
            "duplicate_task_ids",
        ),
        (
            _output(
                ["LANG-EN-MUST", "LANG-ZH-MUST", "MATH-MUST", "UNKNOWN"]
            ),
            "unknown_task_ids",
        ),
        (
            _output(["LANG-EN-MUST", "LANG-ZH-MUST", "MATH-MUST"]),
            "missing_task_ids",
        ),
    ],
)
def test_invalid_outputs_are_unscorable_with_null_reproduction(
    text: str, reason: str
) -> None:
    score = score_de_policy_001(text)

    assert score.scorable is False
    assert score.reproduced is None
    assert score.reason == reason
    assert score.ordered_task_ids is None


def test_expected_task_ids_are_exact_and_fixed() -> None:
    assert EXPECTED_TASK_IDS == (
        "LANG-EN-MUST",
        "LANG-ZH-MUST",
        "MATH-MUST",
        "MATH-EXTEND",
    )


def test_capture_uses_bounded_gemma_reasoning_budgets_and_keeps_actual_output(
    tmp_path: Path,
) -> None:
    actual_output = _output(
        ["LANG-EN-MUST", "LANG-ZH-MUST", "MATH-MUST", "MATH-EXTEND"]
    )
    responses: list[dict[str, Any]] = [
        {
            "data": [
                {
                    "id": "gemma-4-26b-a4b-it",
                    "state": "loaded",
                    "capabilities": ["tool_use"],
                }
            ]
        },
        {
            "model": "gemma-4-26b-a4b-it",
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "policy-call",
                                "type": "function",
                                "function": {
                                    "name": "get_planning_context",
                                    "arguments": '{"scope":"tonight"}',
                                },
                            }
                        ],
                    },
                }
            ],
        },
        {
            "model": "gemma-4-26b-a4b-it",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": actual_output},
                }
            ],
        },
    ]
    payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            payloads.append(json.loads(request.content))
        return httpx.Response(200, json=responses.pop(0))

    client = LMStudioClient(
        "http://127.0.0.1:1234/v1",
        "gemma-4-26b-a4b-it",
        transport=httpx.MockTransport(handler),
    )

    evidence = capture_de_policy_001(
        client, evidence_path=tmp_path / "DE-POLICY-001.json"
    )

    assert [payload["max_tokens"] for payload in payloads] == [1024, 2048]
    assert evidence["actual_model_output"] == actual_output
    assert evidence["scorable"] is True
    assert evidence["reproduced"] is False
    assert evidence["provenance"] == "synthetic_transport"
