"""Pure calibration state-machine policy."""

from __future__ import annotations

from backend.contracts.family import CalibrationState, PendingKind
from backend.errors import InvalidTransitionError


_ACTIONS: dict[CalibrationState, tuple[str, ...]] = {
    CalibrationState.INPUT_SAVED: ("generate_profile_patch",),
    CalibrationState.MODEL_UNAVAILABLE: (
        "retry_last_turn",
        "use_simplified_calibration",
        "abandon_profile_patch",
    ),
    CalibrationState.RETRY_PENDING: ("generate_profile_patch",),
    CalibrationState.NEEDS_CONFIRMATION: (
        "commit_profile_patch",
        "revise_profile_patch",
        "abandon_profile_patch",
    ),
    CalibrationState.COMMITTED: ("start_calibration",),
    CalibrationState.ABANDONED: ("start_calibration",),
}

_TRANSITIONS = frozenset(
    {
        (CalibrationState.INPUT_SAVED, CalibrationState.NEEDS_CONFIRMATION),
        (CalibrationState.INPUT_SAVED, CalibrationState.MODEL_UNAVAILABLE),
        (CalibrationState.MODEL_UNAVAILABLE, CalibrationState.RETRY_PENDING),
        (CalibrationState.MODEL_UNAVAILABLE, CalibrationState.NEEDS_CONFIRMATION),
        (CalibrationState.MODEL_UNAVAILABLE, CalibrationState.ABANDONED),
        (CalibrationState.RETRY_PENDING, CalibrationState.NEEDS_CONFIRMATION),
        (CalibrationState.RETRY_PENDING, CalibrationState.MODEL_UNAVAILABLE),
        (CalibrationState.RETRY_PENDING, CalibrationState.COMMITTED),
        (CalibrationState.RETRY_PENDING, CalibrationState.ABANDONED),
        (CalibrationState.NEEDS_CONFIRMATION, CalibrationState.NEEDS_CONFIRMATION),
        (CalibrationState.NEEDS_CONFIRMATION, CalibrationState.MODEL_UNAVAILABLE),
        (CalibrationState.NEEDS_CONFIRMATION, CalibrationState.COMMITTED),
        (CalibrationState.NEEDS_CONFIRMATION, CalibrationState.ABANDONED),
    }
)


def allowed_actions(
    state: CalibrationState,
    pending_kind: PendingKind | None = None,
) -> tuple[str, ...]:
    """Return the exact parent actions exposed for a calibration state."""
    del pending_kind
    return _ACTIONS[state]


def validate_calibration_transition(
    current: CalibrationState,
    requested: CalibrationState,
) -> None:
    """Reject any transition outside the reviewed calibration graph."""
    if (current, requested) not in _TRANSITIONS:
        raise InvalidTransitionError(current.value, requested.value)
