"""Typed domain errors used at persistence and API boundaries."""

from __future__ import annotations


class StudyPilotError(Exception):
    """Base class for expected StudyPilot domain failures."""


class NotFoundError(StudyPilotError):
    def __init__(self, entity: str, entity_id: str) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} missing: {entity_id}")


class VersionConflictError(StudyPilotError):
    def __init__(
        self,
        entity: str,
        entity_id: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        self.entity = entity
        self.entity_id = entity_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"{entity} version conflict for {entity_id}: "
            f"expected {expected_version}, found {actual_version}"
        )


class IdempotencyConflictError(StudyPilotError):
    def __init__(self, operation: str, idempotency_key: str) -> None:
        self.operation = operation
        self.idempotency_key = idempotency_key
        super().__init__(
            f"idempotency key conflict for operation {operation}: {idempotency_key}"
        )


class InvalidTransitionError(StudyPilotError):
    def __init__(self, current_stage: str, requested_stage: str) -> None:
        self.current_stage = current_stage
        self.requested_stage = requested_stage
        super().__init__(
            f"invalid transition from {current_stage} to {requested_stage}"
        )


class DraftDigestMismatchError(StudyPilotError):
    def __init__(self, draft_id: str) -> None:
        self.draft_id = draft_id
        super().__init__("draft digest does not match stored draft")


class ProfileProposalInvalidError(StudyPilotError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("profile proposal failed deterministic validation")


class CommitCommandInvalidError(StudyPilotError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__("profile commit command failed deterministic validation")
