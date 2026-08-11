from __future__ import annotations

from typing import Any

import pytest
from pydantic import Field

from backend.contracts.calibration_tools import ExtractCalibrationEvidenceArgs
from backend.contracts.evening import SaveIntakeDraftArguments
from backend.contracts.models import StrictModel
from backend.orchestration.tool_registry import (
    PHASE_TOOL_NAMES,
    READ_ONLY_TOOL_NAMES,
    WORKFLOW_TOOL_NAMES,
    ToolDefinition,
    ToolExecutionContext,
    ToolKind,
    ToolRegistry,
    ToolRegistryError,
    WorkflowPhase,
    derive_write_idempotency_key,
)


class ProbeArgs(StrictModel):
    topic: str = Field(min_length=1)


def _handler(arguments: StrictModel, context: ToolExecutionContext) -> dict[str, Any]:
    return {"topic": arguments.model_dump()["topic"], "trace_id": context.trace_id}


def _definition(
    name: str, *, kind: ToolKind | None = None, argument_model: type[StrictModel] = ProbeArgs
) -> ToolDefinition:
    expected_kind = (
        ToolKind.READ if name in READ_ONLY_TOOL_NAMES else ToolKind.WRITE
    )
    return ToolDefinition(
        name=name,
        description="读取规划上下文",
        argument_model=argument_model,
        kind=kind or expected_kind,
        handler=_handler,
    )


def test_exact_workflow_tool_name_set_and_read_only_classification() -> None:
    assert WORKFLOW_TOOL_NAMES == (
        "save_intake_draft",
        "compare_school_brief",
        "confirm_task_inventory",
        "get_planning_context",
        "build_feasible_candidates",
        "commit_plan",
        "extract_calibration_evidence",
        "close_evening",
    )
    assert READ_ONLY_TOOL_NAMES == frozenset(
        {
            "compare_school_brief",
            "get_planning_context",
            "build_feasible_candidates",
        }
    )


def test_expose_is_deterministic_and_rejects_unknown_names() -> None:
    definitions = [_definition(name) for name in reversed(WORKFLOW_TOOL_NAMES)]
    registry = ToolRegistry(definitions)

    exposed = registry.expose(
        ["build_feasible_candidates", "compare_school_brief"]
    )

    assert tuple(item.name for item in exposed) == (
        "compare_school_brief",
        "build_feasible_candidates",
    )
    with pytest.raises(ToolRegistryError) as raised:
        registry.expose(["not_a_workflow_tool"])
    assert raised.value.code == "unknown_tool"


def test_generated_openai_schema_is_strict_and_typed() -> None:
    definition = _definition("get_planning_context")

    schema = definition.openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "get_planning_context"
    parameters = schema["function"]["parameters"]
    assert parameters["type"] == "object"
    assert parameters["additionalProperties"] is False
    assert parameters["required"] == ["topic"]
    assert parameters["properties"]["topic"]["type"] == "string"


def test_generated_openai_schema_inlines_nested_model_contract() -> None:
    definition = _definition(
        "extract_calibration_evidence",
        argument_model=ExtractCalibrationEvidenceArgs,
    )

    parameters = definition.openai_schema()["function"]["parameters"]
    evidence_group = parameters["properties"]["duration_groups"]["items"]

    assert "$defs" not in parameters
    assert "$ref" not in evidence_group
    assert evidence_group["additionalProperties"] is False
    assert evidence_group["required"] == ["subject", "task_type", "minutes"]
    assert evidence_group["properties"]["subject"]["enum"] == [
        "chinese",
        "mathematics",
        "english",
        "civics",
        "history",
        "geography",
        "biology",
    ]


def test_generated_openai_schema_gives_optional_values_a_concrete_type() -> None:
    definition = _definition(
        "save_intake_draft",
        argument_model=SaveIntakeDraftArguments,
    )

    parameters = definition.openai_schema()["function"]["parameters"]
    task = parameters["properties"]["tasks"]["items"]

    assert task["properties"]["child_estimate_minutes"]["type"] == "integer"
    assert task["properties"]["subject"]["type"] == "string"
    assert "anyOf" not in task["properties"]["child_estimate_minutes"]
    assert "child_estimate_minutes" not in task["required"]


def test_untyped_dict_contract_is_rejected() -> None:
    with pytest.raises(TypeError, match="StrictModel"):
        ToolDefinition(
            name="get_planning_context",
            description="读取规划上下文",
            argument_model=dict,  # type: ignore[arg-type]
            kind=ToolKind.READ,
            handler=_handler,
        )


def test_registered_but_disallowed_tool_cannot_be_resolved() -> None:
    registry = ToolRegistry(
        [_definition("get_planning_context"), _definition("compare_school_brief")]
    )

    assert registry.resolve(
        "get_planning_context", allowed_names=["get_planning_context"]
    ).name == "get_planning_context"
    with pytest.raises(ToolRegistryError) as raised:
        registry.resolve(
            "compare_school_brief", allowed_names=["get_planning_context"]
        )
    assert raised.value.code == "disallowed_tool"


def test_fixed_phase_mapping_and_final_narration_exposes_none() -> None:
    assert PHASE_TOOL_NAMES == {
        WorkflowPhase.INTAKE_SAVE: "save_intake_draft",
        WorkflowPhase.COVERAGE_COMPARE: "compare_school_brief",
        WorkflowPhase.INVENTORY_CONFIRM: "confirm_task_inventory",
        WorkflowPhase.CONTEXT_READ: "get_planning_context",
        WorkflowPhase.CANDIDATES_BUILD: "build_feasible_candidates",
        WorkflowPhase.PLAN_COMMIT: "commit_plan",
        WorkflowPhase.PROFILE_PROPOSE: "extract_calibration_evidence",
        WorkflowPhase.PROFILE_COMMIT: None,
        WorkflowPhase.EVENING_CLOSE: "close_evening",
        WorkflowPhase.FINAL_NARRATION: None,
    }
    registry = ToolRegistry([_definition(name) for name in WORKFLOW_TOOL_NAMES])

    for phase, expected_name in PHASE_TOOL_NAMES.items():
        exposed = registry.expose_phase(phase)
        assert tuple(item.name for item in exposed) == (
            () if expected_name is None else (expected_name,)
        )


@pytest.mark.parametrize(
    "reserved_name",
    [
        "session_id",
        "actor",
        "role",
        "expected_version",
        "trace_id",
        "idempotency_key",
    ],
)
def test_trusted_context_fields_cannot_be_model_arguments(
    reserved_name: str,
) -> None:
    DynamicArgs = type(
        "DynamicArgs",
        (StrictModel,),
        {"__annotations__": {reserved_name: str}},
    )

    with pytest.raises(ValueError, match="trusted context"):
        _definition("get_planning_context", argument_model=DynamicArgs)


def test_execution_context_is_strict_immutable_and_write_key_is_stable_hidden() -> None:
    first = derive_write_idempotency_key(
        "caller-http-key", WorkflowPhase.PLAN_COMMIT, "commit_plan"
    )
    second = derive_write_idempotency_key(
        "caller-http-key", WorkflowPhase.PLAN_COMMIT, "commit_plan"
    )
    other = derive_write_idempotency_key(
        "caller-http-key", WorkflowPhase.PROFILE_COMMIT, "commit_profile_patch"
    )
    context = ToolExecutionContext(
        session_id="session-1",
        actor="parent-1",
        role="parent",
        expected_version=3,
        trace_id="trace-1",
        idempotency_key=first,
    )

    assert first == second
    assert len(first) == 64
    assert first != other
    assert "caller-http-key" not in first
    with pytest.raises(Exception, match="frozen"):
        context.expected_version = 4


def test_registry_rejects_wrong_fixed_read_write_kind() -> None:
    with pytest.raises(ValueError, match="classification"):
        ToolRegistry([_definition("commit_plan", kind=ToolKind.READ)])
