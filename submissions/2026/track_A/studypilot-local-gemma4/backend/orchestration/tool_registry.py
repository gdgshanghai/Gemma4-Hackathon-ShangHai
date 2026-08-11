"""Strict native-tool definitions and trusted workflow exposure policy."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import ConfigDict, Field

from backend.contracts.models import StrictModel


WORKFLOW_TOOL_NAMES = (
    "save_intake_draft",
    "compare_school_brief",
    "confirm_task_inventory",
    "get_planning_context",
    "build_feasible_candidates",
    "commit_plan",
    "extract_calibration_evidence",
    "close_evening",
)

READ_ONLY_TOOL_NAMES = frozenset(
    {
        "compare_school_brief",
        "get_planning_context",
        "build_feasible_candidates",
    }
)

_TRUSTED_CONTEXT_FIELDS = frozenset(
    {
        "session_id",
        "actor",
        "role",
        "expected_version",
        "trace_id",
        "idempotency_key",
    }
)


def _inline_local_schema_references(schema: dict[str, Any]) -> dict[str, Any]:
    definitions = schema.pop("$defs", {})

    def inline(value: Any) -> Any:
        if isinstance(value, list):
            return [inline(item) for item in value]
        if not isinstance(value, dict):
            return value
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            definition_name = reference.removeprefix("#/$defs/")
            resolved = deepcopy(definitions[definition_name])
            resolved.update({key: item for key, item in value.items() if key != "$ref"})
            return inline(resolved)
        return {key: inline(item) for key, item in value.items()}

    return inline(schema)


def _simplify_nullable_unions(schema: dict[str, Any]) -> dict[str, Any]:
    def simplify(value: Any) -> Any:
        if isinstance(value, list):
            return [simplify(item) for item in value]
        if not isinstance(value, dict):
            return value
        alternatives = value.get("anyOf")
        if isinstance(alternatives, list):
            concrete = [item for item in alternatives if item.get("type") != "null"]
            has_null = any(item.get("type") == "null" for item in alternatives)
            if has_null and len(concrete) == 1:
                merged = simplify(deepcopy(concrete[0]))
                merged.update(
                    {
                        key: simplify(item)
                        for key, item in value.items()
                        if key != "anyOf"
                    }
                )
                return merged
        return {key: simplify(item) for key, item in value.items()}

    return simplify(schema)


class ToolKind(StrEnum):
    READ = "read"
    WRITE = "write"


class WorkflowPhase(StrEnum):
    INTAKE_SAVE = "intake_save"
    COVERAGE_COMPARE = "coverage_compare"
    INVENTORY_CONFIRM = "inventory_confirm"
    CONTEXT_READ = "context_read"
    CANDIDATES_BUILD = "candidates_build"
    PLAN_COMMIT = "plan_commit"
    PROFILE_PROPOSE = "profile_propose"
    PROFILE_COMMIT = "profile_commit"
    EVENING_CLOSE = "evening_close"
    FINAL_NARRATION = "final_narration"


PHASE_TOOL_NAMES: dict[WorkflowPhase, str | None] = {
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


class ToolRegistryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ToolExecutionContext(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        frozen=True,
    )

    session_id: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    role: str = Field(min_length=1)
    expected_version: int = Field(ge=0)
    trace_id: str = Field(min_length=1)
    idempotency_key: str | None = None


ArgumentsT = TypeVar("ArgumentsT", bound=StrictModel)
ToolHandler = Callable[[ArgumentsT, ToolExecutionContext], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition(Generic[ArgumentsT]):
    name: str
    description: str
    argument_model: type[ArgumentsT]
    kind: ToolKind
    handler: ToolHandler[ArgumentsT]

    def __post_init__(self) -> None:
        try:
            is_strict_model = issubclass(self.argument_model, StrictModel)
        except TypeError:
            is_strict_model = False
        if not is_strict_model:
            raise TypeError("argument_model must inherit StrictModel")
        if self.argument_model.model_config.get("extra") != "forbid" or not (
            self.argument_model.model_config.get("strict")
        ):
            raise TypeError("argument_model must be a strict StrictModel")
        if _TRUSTED_CONTEXT_FIELDS & self.argument_model.model_fields.keys():
            raise ValueError("model arguments cannot contain trusted context fields")
        if not self.name or not self.description:
            raise ValueError("tool name and description must be non-empty")
        if not callable(self.handler):
            raise TypeError("tool handler must be callable")

    def openai_schema(self) -> dict[str, Any]:
        parameters = _simplify_nullable_unions(
            _inline_local_schema_references(
                deepcopy(self.argument_model.model_json_schema())
            )
        )
        parameters["additionalProperties"] = False
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


class ToolRegistry:
    def __init__(self, definitions: Sequence[ToolDefinition[Any]]) -> None:
        self._definitions: dict[str, ToolDefinition[Any]] = {}
        for definition in definitions:
            if definition.name not in WORKFLOW_TOOL_NAMES:
                raise ToolRegistryError("unknown_tool")
            if definition.name in self._definitions:
                raise ToolRegistryError("duplicate_tool_registration")
            expected = (
                ToolKind.READ
                if definition.name in READ_ONLY_TOOL_NAMES
                else ToolKind.WRITE
            )
            if definition.kind is not expected:
                raise ValueError("tool read/write classification is fixed")
            self._definitions[definition.name] = definition

    def expose(self, allowed_names: Sequence[str]) -> tuple[ToolDefinition[Any], ...]:
        requested = set(allowed_names)
        unknown = requested - set(WORKFLOW_TOOL_NAMES)
        if unknown:
            raise ToolRegistryError("unknown_tool")
        unregistered = requested - self._definitions.keys()
        if unregistered:
            raise ToolRegistryError("unregistered_tool")
        return tuple(
            self._definitions[name]
            for name in WORKFLOW_TOOL_NAMES
            if name in requested
        )

    def expose_phase(
        self, phase: WorkflowPhase
    ) -> tuple[ToolDefinition[Any], ...]:
        name = PHASE_TOOL_NAMES[phase]
        return () if name is None else self.expose([name])

    def resolve(
        self,
        name: str,
        *,
        allowed_names: Sequence[str],
    ) -> ToolDefinition[Any]:
        exposed = self.expose(allowed_names)
        for definition in exposed:
            if definition.name == name:
                return definition
        raise ToolRegistryError("disallowed_tool")


def derive_write_idempotency_key(
    caller_key: str,
    phase: WorkflowPhase,
    tool_name: str,
) -> str:
    if not caller_key:
        raise ValueError("caller idempotency key must be non-empty")
    legacy_profile_commit = (
        phase is WorkflowPhase.PROFILE_COMMIT
        and tool_name == "commit_profile_patch"
    )
    if not legacy_profile_commit and PHASE_TOOL_NAMES.get(phase) != tool_name:
        raise ValueError("tool does not match workflow phase")
    material = f"studypilot-v13\0{caller_key}\0{phase.value}\0{tool_name}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
