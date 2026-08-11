"""Bounded, traced native Function Calling state machine."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, ValidationError

from backend.contracts.models import HarnessTrace, StrictModel
from backend.orchestration.lm_studio import (
    ChatCompletionResult,
    LMStudioClient,
    LMStudioError,
    ParsedChatChoice,
    ToolChoice,
)
from backend.orchestration.tool_registry import (
    ToolDefinition,
    ToolExecutionContext,
    ToolKind,
    ToolRegistry,
    WorkflowPhase,
    derive_write_idempotency_key,
)
from backend.storage.run_traces import RunTraceRepository


HARNESS_VERSION = "native-fc-v1"
MAX_TOOL_ROUNDS = 8


class HarnessError(RuntimeError):
    def __init__(self, code: str, trace_id: str) -> None:
        self.code = code
        self.trace_id = trace_id
        super().__init__(code)


class _FrozenStrictModel(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        frozen=True,
    )


class HarnessRequest(_FrozenStrictModel):
    messages: list[dict[str, Any]]
    workflow_phase: WorkflowPhase
    actor: str = Field(min_length=1)
    role: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    expected_version: int = Field(ge=0)
    trace_id: str = Field(min_length=1)
    idempotency_key: str | None = None
    max_tokens: int | None = Field(default=None, ge=1)
    finish_after_valid_write: bool = False


class ToolCallRecord(_FrozenStrictModel):
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    cache_hit: bool
    handler_executed: bool


class HarnessResult(_FrozenStrictModel):
    trace_id: str
    final_content: str
    finish_reason: str
    tool_call_records: tuple[ToolCallRecord, ...]
    model_calls: int
    handler_executions: int
    cache_hits: int
    schema_repair_used: bool


@dataclass(slots=True)
class _RunState:
    model_calls: int = 0
    tool_rounds: int = 0
    handler_executions: int = 0
    cache_hits: int = 0
    schema_repair_used: bool = False
    invalid_calls: int = 0
    valid_tool_succeeded: bool = False
    seen_call_ids: set[str] = field(default_factory=set)
    read_occurrences: dict[str, int] = field(default_factory=dict)
    read_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    write_cache: dict[str, tuple[str, dict[str, Any]]] = field(default_factory=dict)
    records: list[ToolCallRecord] = field(default_factory=list)


class NativeFunctionCallingHarness:
    def __init__(
        self,
        *,
        client: LMStudioClient,
        registry: ToolRegistry,
        trace_repository: RunTraceRepository,
    ) -> None:
        self.client = client
        self.registry = registry
        self.trace_repository = trace_repository

    def run(self, request: HarnessRequest) -> HarnessResult:
        started_at = _now()
        caller_hash = (
            hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest()
            if request.idempotency_key is not None
            else None
        )
        self.trace_repository.start_trace(
            HarnessTrace(
                id=request.trace_id,
                trace_id=request.trace_id,
                session_id=request.session_id,
                workflow_phase=request.workflow_phase.value,
                actor=request.actor,
                role=request.role,
                expected_version=request.expected_version,
                caller_idempotency_sha256=caller_hash,
                harness_version=HARNESS_VERSION,
                status="started",
                final_error_code=None,
                started_at=started_at,
                completed_at=None,
                model_calls=0,
                tool_rounds=0,
                handler_executions=0,
                cache_hits=0,
                schema_repair_used=False,
            )
        )
        state = _RunState()
        try:
            result = self._run_started(request, state)
        except HarnessError as error:
            self._finalize(request.trace_id, state, "failed", error.code)
            raise
        except Exception as error:
            wrapped = HarnessError("harness_internal_error", request.trace_id)
            self._finalize(request.trace_id, state, "failed", wrapped.code)
            raise wrapped from error
        self._finalize(request.trace_id, state, "completed", None)
        return result

    def _run_started(
        self, request: HarnessRequest, state: _RunState
    ) -> HarnessResult:
        exposed = self.registry.expose_phase(request.workflow_phase)
        if exposed and exposed[0].kind is ToolKind.WRITE and not request.idempotency_key:
            raise HarnessError("missing_idempotency_key", request.trace_id)
        messages = [dict(message) for message in request.messages]
        tools = [definition.openai_schema() for definition in exposed]

        if not exposed:
            response, llm_run_id = self._model_call(
                request, state, messages, tools, "none"
            )
            choice = response.choice
            if choice.tool_calls:
                state.tool_rounds += 1
                self._reject_response_calls(
                    request,
                    state,
                    llm_run_id,
                    choice,
                    code="disallowed_tool",
                    fallback_name=choice.tool_calls[0].function.name,
                )
            return self._final_result(request, state, choice)

        definition = exposed[0]
        tool_choice: ToolChoice = "required"
        while True:
            response, llm_run_id = self._model_call(
                request, state, messages, tools, tool_choice
            )
            choice = response.choice
            if not choice.tool_calls:
                if not state.valid_tool_succeeded:
                    raise HarnessError("required_tool_not_called", request.trace_id)
                return self._final_result(request, state, choice)

            state.tool_rounds += 1
            if len(choice.tool_calls) != 1:
                self._reject_response_calls(
                    request,
                    state,
                    llm_run_id,
                    choice,
                    code="multiple_tool_calls",
                    fallback_name=definition.name,
                )
            call = choice.tool_calls[0]
            if call.id in state.seen_call_ids:
                self._reject_call(
                    request,
                    state,
                    llm_run_id,
                    call.id,
                    call.function.name,
                    {"arguments_sha256": _sha256_text(call.function.arguments)},
                    "duplicate_tool_call_id",
                )
            state.seen_call_ids.add(call.id)
            if call.function.name != definition.name:
                self._reject_call(
                    request,
                    state,
                    llm_run_id,
                    call.id,
                    call.function.name,
                    {"arguments_sha256": _sha256_text(call.function.arguments)},
                    "disallowed_tool",
                )

            try:
                arguments, validated_arguments = _validate_arguments(
                    definition, call.function.arguments
                )
            except (
                json.JSONDecodeError,
                TypeError,
                ValidationError,
                ValueError,
            ) as error:
                self._handle_invalid_arguments(
                    request,
                    state,
                    llm_run_id,
                    definition,
                    choice,
                    messages,
                    error,
                )
                if state.tool_rounds >= MAX_TOOL_ROUNDS:
                    raise HarnessError("tool_loop_limit", request.trace_id)
                tool_choice = "required"
                continue

            canonical_arguments = _canonical_object(arguments)
            result = self._execute_valid_call(
                request,
                state,
                llm_run_id,
                definition,
                call.id,
                arguments,
                validated_arguments,
                canonical_arguments,
            )
            state.valid_tool_succeeded = True
            messages.append(choice.assistant_message())
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": definition.name,
                    "content": _canonical_object(result),
                }
            )
            if request.finish_after_valid_write and definition.kind is ToolKind.WRITE:
                return HarnessResult(
                    trace_id=request.trace_id,
                    final_content=choice.content or "",
                    finish_reason=choice.finish_reason,
                    tool_call_records=tuple(state.records),
                    model_calls=state.model_calls,
                    handler_executions=state.handler_executions,
                    cache_hits=state.cache_hits,
                    schema_repair_used=state.schema_repair_used,
                )
            if state.tool_rounds >= MAX_TOOL_ROUNDS:
                raise HarnessError("tool_loop_limit", request.trace_id)
            tool_choice = "auto"

    def _model_call(
        self,
        request: HarnessRequest,
        state: _RunState,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: ToolChoice,
    ) -> tuple[ChatCompletionResult, str]:
        sequence = state.model_calls + 1
        run_id = f"{request.trace_id}:llm:{sequence}"
        request_payload: dict[str, Any] = {
            "model": self.client.model_id,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        if request.max_tokens is not None:
            request_payload["max_tokens"] = request.max_tokens
        request_hash = hashlib.sha256(
            _canonical_object(request_payload).encode("utf-8")
        ).hexdigest()
        generation_parameters: dict[str, Any] = {
            "tool_choice": tool_choice,
            "exposed_tools": [
                tool["function"]["name"] for tool in tools
            ],
        }
        if request.max_tokens is not None:
            generation_parameters["max_tokens"] = request.max_tokens
        started_at = _now()
        self.trace_repository.start_llm_run(
            trace_id=request.trace_id,
            run_id=run_id,
            session_id=request.session_id,
            model=self.client.model_id,
            request_sha256=request_hash,
            generation_parameters=generation_parameters,
            started_at=started_at,
        )
        state.model_calls += 1
        clock_start = time.monotonic_ns()
        try:
            response = self.client.chat_completion(
                messages,
                tools,
                tool_choice,
                max_tokens=request.max_tokens,
            )
        except LMStudioError as error:
            completed_at = _now()
            self.trace_repository.fail_llm_run(
                run_id,
                error_code=error.code,
                completed_at=completed_at,
                latency_ms=_latency_ms(clock_start),
            )
            raise HarnessError(error.code, request.trace_id) from error
        self.trace_repository.complete_llm_run(
            run_id,
            response=response.raw_response,
            finish_reason=response.choice.finish_reason,
            completed_at=_now(),
            latency_ms=_latency_ms(clock_start),
        )
        return response, run_id

    def _handle_invalid_arguments(
        self,
        request: HarnessRequest,
        state: _RunState,
        llm_run_id: str,
        definition: ToolDefinition[Any],
        choice: ParsedChatChoice,
        messages: list[dict[str, Any]],
        validation_error: json.JSONDecodeError | TypeError | ValidationError | ValueError,
    ) -> None:
        call = choice.tool_calls[0]
        state.invalid_calls += 1
        exhausted = state.invalid_calls > 1
        code = (
            "tool_schema_repair_exhausted" if exhausted else "tool_schema_invalid"
        )
        tool_error = {
            "ok": False,
            "error": {
                "code": code,
                "message": "Tool arguments failed strict schema validation.",
                "issues": _sanitized_validation_issues(validation_error),
            },
        }
        run_id, started, clock_start = self._start_tool_attempt(
            request,
            state,
            llm_run_id,
            call.id,
            definition.name,
            {"arguments_sha256": _sha256_text(call.function.arguments)},
            cache_hit=False,
            handler_executed=False,
        )
        self.trace_repository.fail_tool_run(
            run_id,
            error_code=code,
            result=tool_error,
            completed_at=_now(),
            latency_ms=_latency_ms(clock_start),
        )
        state.records.append(
            ToolCallRecord(
                call_id=call.id,
                tool_name=definition.name,
                arguments={"arguments_sha256": _sha256_text(call.function.arguments)},
                result=tool_error,
                cache_hit=False,
                handler_executed=False,
            )
        )
        del started
        if exhausted:
            raise HarnessError(code, request.trace_id)
        state.schema_repair_used = True
        messages.append(choice.assistant_message())
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "name": definition.name,
                "content": _canonical_object(tool_error),
            }
        )

    def _execute_valid_call(
        self,
        request: HarnessRequest,
        state: _RunState,
        llm_run_id: str,
        definition: ToolDefinition[Any],
        call_id: str,
        arguments: dict[str, Any],
        validated_arguments: StrictModel,
        canonical_arguments: str,
    ) -> dict[str, Any]:
        fingerprint = _fingerprint(
            definition.name,
            request.session_id,
            request.expected_version,
            canonical_arguments,
        )
        cache_hit = False
        handler_executed = False
        cached_result: dict[str, Any] | None = None
        hidden_key: str | None = None

        if definition.kind is ToolKind.READ:
            occurrence = state.read_occurrences.get(fingerprint, 0) + 1
            state.read_occurrences[fingerprint] = occurrence
            if occurrence == 2:
                cache_hit = True
                cached_result = state.read_cache[fingerprint]
            elif occurrence >= 3:
                self._reject_call(
                    request,
                    state,
                    llm_run_id,
                    call_id,
                    definition.name,
                    arguments,
                    "repeated_read_limit",
                )
        else:
            assert request.idempotency_key is not None
            hidden_key = derive_write_idempotency_key(
                request.idempotency_key,
                request.workflow_phase,
                definition.name,
            )
            previous = state.write_cache.get(hidden_key)
            if previous is not None:
                previous_arguments, previous_result = previous
                if previous_arguments != canonical_arguments:
                    self._reject_call(
                        request,
                        state,
                        llm_run_id,
                        call_id,
                        definition.name,
                        arguments,
                        "idempotency_conflict",
                    )
                cache_hit = True
                cached_result = previous_result

        handler_executed = not cache_hit
        run_id, _, clock_start = self._start_tool_attempt(
            request,
            state,
            llm_run_id,
            call_id,
            definition.name,
            arguments,
            cache_hit=cache_hit,
            handler_executed=handler_executed,
        )
        if cache_hit:
            state.cache_hits += 1
            assert cached_result is not None
            result = _copy_object(cached_result)
        else:
            state.handler_executions += 1
            context = ToolExecutionContext(
                session_id=request.session_id,
                actor=request.actor,
                role=request.role,
                expected_version=request.expected_version,
                trace_id=request.trace_id,
                idempotency_key=hidden_key,
            )
            try:
                raw_result = definition.handler(validated_arguments, context)
            except Exception as error:
                self.trace_repository.fail_tool_run(
                    run_id,
                    error_code="tool_handler_failed",
                    completed_at=_now(),
                    latency_ms=_latency_ms(clock_start),
                )
                raise HarnessError("tool_handler_failed", request.trace_id) from error
            if not isinstance(raw_result, Mapping):
                self.trace_repository.fail_tool_run(
                    run_id,
                    error_code="tool_result_not_object",
                    completed_at=_now(),
                    latency_ms=_latency_ms(clock_start),
                )
                raise HarnessError("tool_result_not_object", request.trace_id)
            try:
                result = _copy_object(dict(raw_result))
            except (TypeError, ValueError) as error:
                self.trace_repository.fail_tool_run(
                    run_id,
                    error_code="tool_result_not_serializable",
                    completed_at=_now(),
                    latency_ms=_latency_ms(clock_start),
                )
                raise HarnessError("tool_result_not_serializable", request.trace_id) from error
            if definition.kind is ToolKind.READ:
                state.read_cache[fingerprint] = _copy_object(result)
            else:
                assert hidden_key is not None
                state.write_cache[hidden_key] = (
                    canonical_arguments,
                    _copy_object(result),
                )

        self.trace_repository.complete_tool_run(
            run_id,
            result=result,
            completed_at=_now(),
            latency_ms=_latency_ms(clock_start),
        )
        state.records.append(
            ToolCallRecord(
                call_id=call_id,
                tool_name=definition.name,
                arguments=arguments,
                result=result,
                cache_hit=cache_hit,
                handler_executed=handler_executed,
            )
        )
        return result

    def _reject_response_calls(
        self,
        request: HarnessRequest,
        state: _RunState,
        llm_run_id: str,
        choice: ParsedChatChoice,
        *,
        code: str,
        fallback_name: str,
    ) -> None:
        ids = [call.id for call in choice.tool_calls]
        call_id = ids[0] if len(ids) == 1 else f"multiple-{_sha256_text('|'.join(ids))[:16]}"
        self._reject_call(
            request,
            state,
            llm_run_id,
            call_id,
            fallback_name,
            {"call_count": len(ids), "call_ids_sha256": _sha256_text("|".join(ids))},
            code,
        )

    def _reject_call(
        self,
        request: HarnessRequest,
        state: _RunState,
        llm_run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        code: str,
    ) -> None:
        run_id, _, clock_start = self._start_tool_attempt(
            request,
            state,
            llm_run_id,
            call_id,
            tool_name,
            arguments,
            cache_hit=False,
            handler_executed=False,
        )
        self.trace_repository.fail_tool_run(
            run_id,
            error_code=code,
            completed_at=_now(),
            latency_ms=_latency_ms(clock_start),
        )
        state.records.append(
            ToolCallRecord(
                call_id=call_id,
                tool_name=tool_name,
                arguments=arguments,
                result=None,
                cache_hit=False,
                handler_executed=False,
            )
        )
        raise HarnessError(code, request.trace_id)

    def _start_tool_attempt(
        self,
        request: HarnessRequest,
        state: _RunState,
        llm_run_id: str,
        call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        cache_hit: bool,
        handler_executed: bool,
    ) -> tuple[str, datetime, int]:
        run_id = f"{request.trace_id}:tool:{len(state.records) + 1}"
        started_at = _now()
        clock_start = time.monotonic_ns()
        self.trace_repository.start_tool_run(
            trace_id=request.trace_id,
            run_id=run_id,
            session_id=request.session_id,
            llm_run_id=llm_run_id,
            tool_name=tool_name,
            call_id=call_id,
            arguments=arguments,
            cache_hit=cache_hit,
            handler_executed=handler_executed,
            started_at=started_at,
        )
        return run_id, started_at, clock_start

    def _final_result(
        self,
        request: HarnessRequest,
        state: _RunState,
        choice: ParsedChatChoice,
    ) -> HarnessResult:
        if choice.content is None or not choice.content.strip():
            raise HarnessError("empty_final_content", request.trace_id)
        return HarnessResult(
            trace_id=request.trace_id,
            final_content=choice.content,
            finish_reason=choice.finish_reason,
            tool_call_records=tuple(state.records),
            model_calls=state.model_calls,
            handler_executions=state.handler_executions,
            cache_hits=state.cache_hits,
            schema_repair_used=state.schema_repair_used,
        )

    def _finalize(
        self,
        trace_id: str,
        state: _RunState,
        status: Literal["completed", "failed"],
        error_code: str | None,
    ) -> None:
        self.trace_repository.finalize_trace(
            trace_id,
            status=status,
            final_error_code=error_code,
            completed_at=_now(),
            model_calls=state.model_calls,
            tool_rounds=state.tool_rounds,
            handler_executions=state.handler_executions,
            cache_hits=state.cache_hits,
            schema_repair_used=state.schema_repair_used,
        )


def _validate_arguments(
    definition: ToolDefinition[Any], raw_arguments: str
) -> tuple[dict[str, Any], StrictModel]:
    decoded = json.loads(raw_arguments)
    if not isinstance(decoded, dict):
        raise TypeError("tool arguments must decode to an object")
    validated = definition.argument_model.model_validate_json(raw_arguments)
    return validated.model_dump(mode="json"), validated


def _sanitized_validation_issues(
    error: json.JSONDecodeError | TypeError | ValidationError | ValueError,
) -> list[dict[str, Any]]:
    if isinstance(error, ValidationError):
        return [
            {
                "location": list(issue["loc"]),
                "type": str(issue["type"]),
            }
            for issue in error.errors(include_url=False)
        ]
    return [
        {
            "location": ["arguments"],
            "type": (
                "json_invalid"
                if isinstance(error, json.JSONDecodeError)
                else "value_error"
            ),
        }
    ]


def _fingerprint(
    tool_name: str,
    session_id: str,
    expected_version: int,
    canonical_arguments: str,
) -> str:
    material = {
        "tool_name": tool_name,
        "session_id": session_id,
        "expected_version": expected_version,
        "arguments": json.loads(canonical_arguments),
    }
    return hashlib.sha256(_canonical_object(material).encode("utf-8")).hexdigest()


def _canonical_object(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        allow_nan=False,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _copy_object(value: Mapping[str, Any]) -> dict[str, Any]:
    decoded = json.loads(_canonical_object(value))
    if not isinstance(decoded, dict):
        raise TypeError("tool result must be a JSON object")
    return decoded


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _latency_ms(start_ns: int) -> int:
    return max((time.monotonic_ns() - start_ns) // 1_000_000, 0)
