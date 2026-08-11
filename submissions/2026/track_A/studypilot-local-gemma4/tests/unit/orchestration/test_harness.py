from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import AwareDatetime, Field, ValidationError

from backend.config import load_settings
from backend.contracts.models import StrictModel
from backend.orchestration.harness import (
    HarnessError,
    HarnessRequest,
    NativeFunctionCallingHarness,
)
from backend.orchestration.lm_studio import (
    LMStudioClient,
    ModelConfigurationError,
)
from backend.orchestration.tool_registry import (
    ToolDefinition,
    ToolExecutionContext,
    ToolKind,
    ToolRegistry,
    WorkflowPhase,
)
from backend.storage.database import connect_database, run_migrations
from backend.storage.run_traces import RunTraceRepository


MODEL = "gemma-4-26b-a4b-it"
BASE_URL = "http://127.0.0.1:1234/v1"


class ProbeArgs(StrictModel):
    value: int = Field(ge=0)


class NestedJsonProbe(StrictModel):
    label: str = Field(min_length=1)


class JsonBoundaryArgs(StrictModel):
    items: tuple[NestedJsonProbe, ...] = Field(min_length=1)
    observed_at: AwareDatetime


def _tool_response(
    *,
    call_id: str = "call-1",
    name: str = "get_planning_context",
    arguments: str = '{"value":1}',
    content: str | None = None,
    extra_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    calls = [
        {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        }
    ]
    calls.extend(extra_calls or [])
    return {
        "id": f"chat-{call_id}",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": calls,
                },
            }
        ],
    }


def _text_response(content: str = "已读取上下文。") -> dict[str, Any]:
    return {
        "id": "chat-final",
        "model": MODEL,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }


class QueueTransport:
    def __init__(self, items: list[dict[str, Any] | Exception]) -> None:
        self.items = list(items)
        self.payloads: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.payloads.append(json.loads(request.content))
        if not self.items:
            raise AssertionError("unexpected ninth model request")
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return httpx.Response(200, json=item)


def _request(
    phase: WorkflowPhase = WorkflowPhase.CONTEXT_READ,
    *,
    trace_id: str = "trace-1",
    idempotency_key: str | None = None,
    finish_after_valid_write: bool = False,
) -> HarnessRequest:
    return HarnessRequest(
        messages=[{"role": "user", "content": "Use the trusted workflow tool."}],
        workflow_phase=phase,
        actor="child-1",
        role="child",
        session_id="session-1",
        expected_version=2,
        trace_id=trace_id,
        idempotency_key=idempotency_key,
        max_tokens=128,
        finish_after_valid_write=finish_after_valid_write,
    )


def _build(
    tmp_path: Path,
    items: list[dict[str, Any] | Exception],
    *,
    name: str = "get_planning_context",
    kind: ToolKind = ToolKind.READ,
    handler: Callable[[ProbeArgs, ToolExecutionContext], Any] | None = None,
) -> tuple[
    NativeFunctionCallingHarness,
    QueueTransport,
    RunTraceRepository,
    list[tuple[ProbeArgs, ToolExecutionContext]],
]:
    calls: list[tuple[ProbeArgs, ToolExecutionContext]] = []

    def default_handler(
        arguments: ProbeArgs, context: ToolExecutionContext
    ) -> dict[str, Any]:
        calls.append((arguments, context))
        return {"ok": True, "value": arguments.value}

    actual_handler = handler or default_handler
    definition = ToolDefinition(
        name=name,
        description="读取可信规划上下文",
        argument_model=ProbeArgs,
        kind=kind,
        handler=actual_handler,
    )
    queue = QueueTransport(items)
    client = LMStudioClient(
        BASE_URL,
        MODEL,
        transport=httpx.MockTransport(queue),
    )
    database_path = tmp_path / "harness.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = RunTraceRepository(database_path)
    harness = NativeFunctionCallingHarness(
        client=client,
        registry=ToolRegistry([definition]),
        trace_repository=repository,
    )
    return harness, queue, repository, calls


def test_required_single_tool_empty_content_two_turn_success_and_correlation(
    tmp_path: Path,
) -> None:
    harness, queue, repository, calls = _build(
        tmp_path, [_tool_response(content=""), _text_response()]
    )

    result = harness.run(_request())

    assert len(queue.payloads[0]["tools"]) == 1
    assert queue.payloads[0]["tools"][0]["function"]["name"] == (
        "get_planning_context"
    )
    assert queue.payloads[0]["tool_choice"] == "required"
    assert queue.payloads[1]["tool_choice"] == "auto"
    assert queue.payloads[1]["messages"][-2] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "get_planning_context",
                    "arguments": '{"value":1}',
                },
            }
        ],
    }
    assert queue.payloads[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "name": "get_planning_context",
        "content": '{"ok":true,"value":1}',
    }
    assert result.final_content == "已读取上下文。"
    assert result.finish_reason == "stop"
    assert result.model_calls == 2
    assert result.handler_executions == 1
    assert result.cache_hits == 0
    assert result.schema_repair_used is False
    assert calls[0][1].idempotency_key is None
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "completed"
    assert stored.trace.model_calls == 2
    assert [event.event_kind for event in stored.events] == ["llm", "tool", "llm"]


def test_finish_after_valid_write_completes_without_narration_call(
    tmp_path: Path,
) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [_tool_response(content="", name="commit_plan")],
        name="commit_plan",
        kind=ToolKind.WRITE,
    )

    result = harness.run(
        _request(
            WorkflowPhase.PLAN_COMMIT,
            idempotency_key="caller-key",
            finish_after_valid_write=True,
        )
    )

    assert len(queue.payloads) == 1
    assert result.final_content == ""
    assert result.finish_reason == "tool_calls"
    assert result.model_calls == 1
    assert result.handler_executions == 1
    assert len(calls) == 1
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "completed"
    assert [event.event_kind for event in stored.events] == ["llm", "tool"]


def test_json_mode_strict_tuple_argument_boundary_preserves_python_strictness(
    tmp_path: Path,
) -> None:
    raw_arguments = (
        '{"items":[{"label":"first"}],'
        '"observed_at":"2026-07-01T12:00:00Z"}'
    )
    with pytest.raises(ValidationError):
        JsonBoundaryArgs.model_validate(json.loads(raw_arguments))

    captured: list[JsonBoundaryArgs] = []

    def handler(
        arguments: JsonBoundaryArgs,
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        captured.append(arguments)
        return {"ok": True, "count": len(arguments.items)}

    definition = ToolDefinition(
        name="get_planning_context",
        description="Read a nested JSON boundary probe.",
        argument_model=JsonBoundaryArgs,
        kind=ToolKind.READ,
        handler=handler,
    )
    queue = QueueTransport(
        [
            _tool_response(arguments=raw_arguments, content=""),
            _text_response("Nested JSON accepted."),
        ]
    )
    database_path = tmp_path / "json-boundary.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    harness = NativeFunctionCallingHarness(
        client=LMStudioClient(
            BASE_URL,
            MODEL,
            transport=httpx.MockTransport(queue),
        ),
        registry=ToolRegistry([definition]),
        trace_repository=RunTraceRepository(database_path),
    )

    result = harness.run(_request())

    assert result.handler_executions == 1
    assert captured == [
        JsonBoundaryArgs(
            items=(NestedJsonProbe(label="first"),),
            observed_at=datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        )
    ]
    assert queue.payloads[1]["tool_choice"] == "auto"


def test_final_narration_exposes_no_tools_and_sends_none(tmp_path: Path) -> None:
    queue = QueueTransport([_text_response("最终叙述")])
    database_path = tmp_path / "narration.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    harness = NativeFunctionCallingHarness(
        client=LMStudioClient(
            BASE_URL, MODEL, transport=httpx.MockTransport(queue)
        ),
        registry=ToolRegistry([]),
        trace_repository=RunTraceRepository(database_path),
    )

    result = harness.run(_request(WorkflowPhase.FINAL_NARRATION))

    assert queue.payloads[0]["tools"] == []
    assert queue.payloads[0]["tool_choice"] == "none"
    assert result.final_content == "最终叙述"
    assert result.handler_executions == 0


def test_schema_invalid_gets_one_required_repair_then_success(tmp_path: Path) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [
            _tool_response(call_id="bad", arguments='{ "value": "wrong" }'),
            _tool_response(call_id="fixed", arguments='{"value":2}'),
            _text_response("修复成功"),
        ],
    )

    result = harness.run(_request())

    assert [payload["tool_choice"] for payload in queue.payloads] == [
        "required",
        "required",
        "auto",
    ]
    repair_result = json.loads(queue.payloads[1]["messages"][-1]["content"])
    assert repair_result["ok"] is False
    assert repair_result["error"]["code"] == "tool_schema_invalid"
    assert queue.payloads[1]["messages"][-1]["tool_call_id"] == "bad"
    assert result.schema_repair_used is True
    assert result.handler_executions == 1
    assert len(calls) == 1
    stored = repository.get_trace("trace-1")
    assert stored.tool_runs[0].status == "failed"
    assert stored.tool_runs[0].result == repair_result


def test_schema_repair_reports_only_sanitized_locations_and_types(
    tmp_path: Path,
) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [
            _tool_response(
                call_id="bad",
                name="commit_plan",
                arguments='{ "value": "private text" }',
            ),
            _tool_response(
                call_id="fixed",
                name="commit_plan",
                arguments='{"value":2}',
            ),
        ],
        name="commit_plan",
        kind=ToolKind.WRITE,
    )

    result = harness.run(
        _request(
            WorkflowPhase.PLAN_COMMIT,
            idempotency_key="caller-key",
            finish_after_valid_write=True,
        )
    )

    repair_result = json.loads(queue.payloads[1]["messages"][-1]["content"])
    assert repair_result == {
        "error": {
            "code": "tool_schema_invalid",
            "issues": [{"location": ["value"], "type": "int_type"}],
            "message": "Tool arguments failed strict schema validation.",
        },
        "ok": False,
    }
    assert "private text" not in json.dumps(repair_result)
    assert result.model_calls == 2
    assert result.schema_repair_used is True
    assert len(calls) == 1
    assert repository.get_trace("trace-1").trace.status == "completed"


def test_second_invalid_call_stops_schema_repair_exhausted(tmp_path: Path) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [
            _tool_response(call_id="bad-1", arguments="not json"),
            _tool_response(call_id="bad-2", arguments='{"value":-1}'),
        ],
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "tool_schema_repair_exhausted"
    assert len(queue.payloads) == 2
    assert calls == []
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "failed"
    assert stored.trace.schema_repair_used is True
    assert [run.error_code for run in stored.tool_runs] == [
        "tool_schema_invalid",
        "tool_schema_repair_exhausted",
    ]


def test_read_occurrences_execute_cache_then_stop(tmp_path: Path) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [
            _tool_response(call_id="read-1"),
            _tool_response(call_id="read-2"),
            _tool_response(call_id="read-3"),
        ],
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "repeated_read_limit"
    assert len(calls) == 1
    assert len(queue.payloads) == 3
    stored = repository.get_trace("trace-1")
    assert stored.trace.cache_hits == 1
    assert [run.cache_hit for run in stored.tool_runs] == [False, True, False]
    assert [run.handler_executed for run in stored.tool_runs] == [True, False, False]


def test_write_repeat_executes_once_and_uses_stable_hidden_key(tmp_path: Path) -> None:
    harness, _, repository, calls = _build(
        tmp_path,
        [
            _tool_response(call_id="write-1", name="commit_plan"),
            _tool_response(call_id="write-2", name="commit_plan"),
            _text_response("计划已提交"),
        ],
        name="commit_plan",
        kind=ToolKind.WRITE,
    )

    result = harness.run(
        _request(WorkflowPhase.PLAN_COMMIT, idempotency_key="caller-key")
    )

    assert len(calls) == 1
    assert result.handler_executions == 1
    assert result.cache_hits == 1
    assert calls[0][1].idempotency_key is not None
    assert calls[0][1].idempotency_key != "caller-key"
    stored = repository.get_trace("trace-1")
    assert stored.trace.caller_idempotency_sha256 is not None
    assert [run.handler_executed for run in stored.tool_runs] == [True, False]


def test_disallowed_tool_call_fails_without_handler(tmp_path: Path) -> None:
    harness, _, repository, calls = _build(
        tmp_path,
        [_tool_response(name="compare_school_brief")],
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "disallowed_tool"
    assert calls == []
    assert repository.get_trace("trace-1").tool_runs[0].handler_executed is False


def test_multiple_calls_rejects_entire_response_before_execution(tmp_path: Path) -> None:
    second = {
        "id": "call-2",
        "type": "function",
        "function": {
            "name": "get_planning_context",
            "arguments": '{"value":2}',
        },
    }
    harness, _, repository, calls = _build(
        tmp_path, [_tool_response(extra_calls=[second])]
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "multiple_tool_calls"
    assert calls == []
    stored = repository.get_trace("trace-1")
    assert stored.trace.tool_rounds == 1
    assert len(stored.tool_runs) == 1
    assert stored.tool_runs[0].handler_executed is False


def test_required_stage_early_prose_is_explicit_failure(tmp_path: Path) -> None:
    harness, _, repository, calls = _build(tmp_path, [_text_response("I skipped it")])

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "required_tool_not_called"
    assert calls == []
    stored = repository.get_trace("trace-1")
    assert stored.trace.model_calls == 1
    assert stored.trace.tool_rounds == 0


def test_eighth_tool_round_stops_before_ninth_model_call(tmp_path: Path) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [
            _tool_response(call_id=f"write-{index}", name="commit_plan")
            for index in range(1, 9)
        ],
        name="commit_plan",
        kind=ToolKind.WRITE,
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(
            _request(WorkflowPhase.PLAN_COMMIT, idempotency_key="caller-key")
        )

    assert raised.value.code == "tool_loop_limit"
    assert len(queue.payloads) == 8
    assert len(calls) == 1
    stored = repository.get_trace("trace-1")
    assert stored.trace.model_calls == 8
    assert stored.trace.tool_rounds == 8
    assert stored.trace.handler_executions == 1
    assert stored.trace.cache_hits == 7
    assert len(stored.tool_runs) == 8


def test_missing_write_idempotency_key_has_zero_transport_calls(tmp_path: Path) -> None:
    harness, queue, repository, calls = _build(
        tmp_path,
        [_tool_response(name="commit_plan")],
        name="commit_plan",
        kind=ToolKind.WRITE,
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request(WorkflowPhase.PLAN_COMMIT))

    assert raised.value.code == "missing_idempotency_key"
    assert queue.payloads == []
    assert calls == []
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "failed"
    assert stored.trace.model_calls == 0
    assert stored.events == ()


def test_same_write_key_different_arguments_conflicts_before_second_handler(
    tmp_path: Path,
) -> None:
    harness, _, repository, calls = _build(
        tmp_path,
        [
            _tool_response(call_id="write-1", name="commit_plan", arguments='{"value":1}'),
            _tool_response(call_id="write-2", name="commit_plan", arguments='{"value":2}'),
        ],
        name="commit_plan",
        kind=ToolKind.WRITE,
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(
            _request(WorkflowPhase.PLAN_COMMIT, idempotency_key="same-caller-key")
        )

    assert raised.value.code == "idempotency_conflict"
    assert len(calls) == 1
    stored = repository.get_trace("trace-1")
    assert [run.handler_executed for run in stored.tool_runs] == [True, False]


@pytest.mark.parametrize(
    ("item", "expected_code"),
    [
        (httpx.ReadTimeout("slow"), "model_timeout"),
        ({"model": MODEL, "choices": []}, "missing_choice"),
    ],
)
def test_timeout_and_protocol_failure_finalize_trace_and_llm_run(
    tmp_path: Path,
    item: dict[str, Any] | Exception,
    expected_code: str,
) -> None:
    harness, _, repository, calls = _build(tmp_path, [item])

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == expected_code
    assert calls == []
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "failed"
    assert stored.trace.final_error_code == expected_code
    assert stored.trace.model_calls == 1
    assert stored.llm_runs[0].status == "failed"
    assert stored.llm_runs[0].error_code == expected_code


def test_duplicate_call_id_is_rejected_before_cached_repeat(tmp_path: Path) -> None:
    harness, _, repository, calls = _build(
        tmp_path, [_tool_response(call_id="same"), _tool_response(call_id="same")]
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "duplicate_tool_call_id"
    assert len(calls) == 1
    assert repository.get_trace("trace-1").tool_runs[-1].handler_executed is False


def test_non_object_tool_result_fails_without_synthesized_fallback(tmp_path: Path) -> None:
    handler_calls = 0

    def invalid_handler(
        arguments: ProbeArgs, context: ToolExecutionContext
    ) -> list[str]:
        nonlocal handler_calls
        handler_calls += 1
        return ["not", "an", "object"]

    harness, queue, repository, _ = _build(
        tmp_path, [_tool_response()], handler=invalid_handler
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "tool_result_not_object"
    assert handler_calls == 1
    assert len(queue.payloads) == 1
    stored = repository.get_trace("trace-1")
    assert stored.trace.handler_executions == 1
    assert stored.tool_runs[0].result is None


@pytest.mark.parametrize(
    "non_finite",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_non_finite_tool_result_fails_and_leaves_no_started_runs(
    tmp_path: Path, non_finite: float
) -> None:
    def non_finite_handler(
        arguments: ProbeArgs, context: ToolExecutionContext
    ) -> dict[str, float]:
        return {"value": non_finite}

    harness, _, repository, _ = _build(
        tmp_path, [_tool_response()], handler=non_finite_handler
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "tool_result_not_serializable"
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "failed"
    assert stored.trace.final_error_code == "tool_result_not_serializable"
    assert all(run.status != "started" for run in stored.llm_runs)
    assert all(run.status != "started" for run in stored.tool_runs)
    assert stored.tool_runs[0].status == "failed"
    assert stored.tool_runs[0].error_code == "tool_result_not_serializable"


def test_invalid_settings_url_fails_before_any_harness_trace(tmp_path: Path) -> None:
    database_path = tmp_path / "invalid-settings.db"
    run_migrations(database_path, backup_dir=tmp_path / "backups")
    repository = RunTraceRepository(database_path)
    settings = load_settings(
        project_root=tmp_path,
        environ={"V13_LM_STUDIO_BASE_URL": "http://127.0.0.1:99999/v1"},
    )

    with pytest.raises(ModelConfigurationError) as raised:
        LMStudioClient.from_settings(settings)

    assert raised.value.code == "invalid_model_base_url"
    with connect_database(repository.database_path) as connection:
        trace_count = connection.execute(
            "SELECT count(*) FROM harness_traces"
        ).fetchone()[0]
    assert trace_count == 0


def test_defensive_invalid_url_failure_finalizes_started_llm_run(
    tmp_path: Path,
) -> None:
    harness, _, repository, calls = _build(
        tmp_path, [httpx.InvalidURL("invalid URL from transport")]
    )

    with pytest.raises(HarnessError) as raised:
        harness.run(_request())

    assert raised.value.code == "invalid_model_base_url"
    assert calls == []
    stored = repository.get_trace("trace-1")
    assert stored.trace.status == "failed"
    assert stored.trace.final_error_code == "invalid_model_base_url"
    assert stored.llm_runs[0].status == "failed"
    assert stored.llm_runs[0].error_code == "invalid_model_base_url"
    assert all(run.status != "started" for run in stored.llm_runs)
