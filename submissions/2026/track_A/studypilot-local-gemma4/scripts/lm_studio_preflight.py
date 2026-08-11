"""Verify a real two-turn native Function Calling exchange with LM Studio."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import load_settings  # noqa: E402
from backend.contracts.models import StrictModel  # noqa: E402
from backend.orchestration.lm_studio import (  # noqa: E402
    LMStudioClient,
    LMStudioError,
)
from backend.orchestration.tool_registry import (  # noqa: E402
    ToolDefinition,
    ToolExecutionContext,
    ToolKind,
)


PREFLIGHT_FIRST_MAX_TOKENS = 1024
PREFLIGHT_SECOND_MAX_TOKENS = 1024


class PreflightProbeArgs(StrictModel):
    probe: Literal["native_function_calling"]


class PreflightFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _unused_probe_handler(
    arguments: PreflightProbeArgs, context: ToolExecutionContext
) -> dict[str, Any]:
    raise RuntimeError("preflight validates the call without executing a handler")


def run_preflight(
    client: LMStudioClient,
    *,
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    target = Path(evidence_path) if evidence_path is not None else None
    if target is not None:
        target.unlink(missing_ok=True)
    try:
        metadata_started = time.monotonic_ns()
        metadata = client.get_model_metadata()
        metadata_latency = latency_ms(metadata_started)

        definition = ToolDefinition(
            name="get_planning_context",
            description="\u8bfb\u53d6\u5408\u6210\u89c4\u5212\u4e0a\u4e0b\u6587\u4ee5\u9a8c\u8bc1\u539f\u751f\u5de5\u5177\u8c03\u7528",
            argument_model=PreflightProbeArgs,
            kind=ToolKind.READ,
            handler=_unused_probe_handler,
        )
        tools = [definition.openai_schema()]
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    "Call get_planning_context exactly once with "
                    '{"probe":"native_function_calling"}. Do not answer first.'
                ),
            }
        ]
        first_request = _chat_payload(
            client, messages, tools, "required", PREFLIGHT_FIRST_MAX_TOKENS
        )
        first_started = time.monotonic_ns()
        first = client.chat_completion(
            messages,
            tools,
            "required",
            max_tokens=PREFLIGHT_FIRST_MAX_TOKENS,
        )
        first_latency = latency_ms(first_started)
        if first.choice.finish_reason != "tool_calls" or len(first.choice.tool_calls) != 1:
            raise PreflightFailure("first_turn_missing_native_tool_call")
        call = first.choice.tool_calls[0]
        if call.function.name != definition.name:
            raise PreflightFailure("first_turn_wrong_tool")
        try:
            decoded_args = json.loads(call.function.arguments)
            if not isinstance(decoded_args, dict):
                raise TypeError
            validated = definition.argument_model.model_validate(decoded_args)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise PreflightFailure("first_turn_invalid_arguments") from error
        validated_args = validated.model_dump(mode="json")
        tool_result = {
            "ok": True,
            "probe": "native_function_calling",
        }
        tool_result_json = canonical_json(tool_result)
        second_messages = [
            *messages,
            first.choice.assistant_message(),
            {
                "role": "tool",
                "tool_call_id": call.id,
                "name": definition.name,
                "content": tool_result_json,
            },
        ]
        second_request = _chat_payload(
            client, second_messages, tools, "none", PREFLIGHT_SECOND_MAX_TOKENS
        )
        second_started = time.monotonic_ns()
        second = client.chat_completion(
            second_messages,
            tools,
            "none",
            max_tokens=PREFLIGHT_SECOND_MAX_TOKENS,
        )
        second_latency = latency_ms(second_started)
        if second.choice.tool_calls:
            raise PreflightFailure("second_turn_unexpected_tool_call")
        if second.choice.content is None or not second.choice.content.strip():
            raise PreflightFailure("second_turn_missing_text")

        evidence = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "configured_model": client.model_id,
            "model_state": metadata.state,
            "quantization": metadata.quantization,
            "capabilities": list(metadata.capabilities),
            "first_request_sha256": sha256_json(first_request),
            "first_response_sha256": sha256_json(first.raw_response),
            "first_finish_reason": first.choice.finish_reason,
            "first_content_empty": first.choice.content in {None, ""},
            "tool_name": call.function.name,
            "tool_call_id": call.id,
            "validated_args": validated_args,
            "tool_result_sha256": hashlib.sha256(
                tool_result_json.encode("utf-8")
            ).hexdigest(),
            "second_request_sha256": sha256_json(second_request),
            "second_response_sha256": sha256_json(second.raw_response),
            "second_finish_reason": second.choice.finish_reason,
            "second_content_sha256": hashlib.sha256(
                second.choice.content.encode("utf-8")
            ).hexdigest(),
            "latencies_ms": {
                "metadata": metadata_latency,
                "first_turn": first_latency,
                "second_turn": second_latency,
            },
            "provenance": client.evidence_provenance,
        }
    except PreflightFailure:
        raise
    except LMStudioError as error:
        raise PreflightFailure(error.code) from error
    except Exception as error:
        raise PreflightFailure("preflight_protocol_failure") from error

    if target is not None:
        write_evidence(target, evidence)
    return evidence


def _chat_payload(
    client: LMStudioClient,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: Literal["none", "auto", "required"],
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": client.model_id,
        "messages": messages,
        "tools": tools,
        "tool_choice": tool_choice,
        "max_tokens": max_tokens,
    }


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )


def sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def write_evidence(path: Path, evidence: Mapping[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(dict(evidence), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def latency_ms(start_ns: int) -> int:
    return max((time.monotonic_ns() - start_ns) // 1_000_000, 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    arguments = parser.parse_args()
    if arguments.evidence is not None:
        arguments.evidence.unlink(missing_ok=True)
    try:
        settings = load_settings()
        client = LMStudioClient.from_settings(settings)
        evidence = run_preflight(client, evidence_path=arguments.evidence)
    except (LMStudioError, PreflightFailure) as error:
        code = getattr(error, "code", "preflight_failed")
        print(f"LM Studio preflight: FAIL ({code})")
        return 1
    print(
        "LM Studio preflight: PASS "
        f"model={evidence['configured_model']} "
        f"tool={evidence['tool_name']} turns=2"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
