from __future__ import annotations

import pytest

from backend.contracts.family import CalibrationState, PendingKind
from backend.domain.workflow import allowed_actions, validate_calibration_transition
from backend.errors import InvalidTransitionError


EXPECTED_ACTIONS = {
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

LEGAL_TRANSITIONS = {
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


@pytest.mark.parametrize(("state", "expected"), EXPECTED_ACTIONS.items())
def test_allowed_actions_are_exact(
    state: CalibrationState,
    expected: tuple[str, ...],
) -> None:
    assert allowed_actions(state) == expected


def test_pending_kind_does_not_change_explicit_retry_action() -> None:
    assert allowed_actions(
        CalibrationState.MODEL_UNAVAILABLE,
        PendingKind.MODEL_RETRY,
    ) == (
        "retry_last_turn",
        "use_simplified_calibration",
        "abandon_profile_patch",
    )


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (current, requested)
        for current in CalibrationState
        for requested in CalibrationState
        if (current, requested) in LEGAL_TRANSITIONS
    ],
)
def test_every_legal_calibration_transition_is_accepted(
    current: CalibrationState,
    requested: CalibrationState,
) -> None:
    assert validate_calibration_transition(current, requested) is None


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        (current, requested)
        for current in CalibrationState
        for requested in CalibrationState
        if (current, requested) not in LEGAL_TRANSITIONS
    ],
)
def test_every_illegal_calibration_transition_is_rejected(
    current: CalibrationState,
    requested: CalibrationState,
) -> None:
    with pytest.raises(InvalidTransitionError) as error:
        validate_calibration_transition(current, requested)
    assert error.value.current_stage == current.value
    assert error.value.requested_stage == requested.value


def test_needs_confirmation_self_transition_is_the_only_revision_path() -> None:
    validate_calibration_transition(
        CalibrationState.NEEDS_CONFIRMATION,
        CalibrationState.NEEDS_CONFIRMATION,
    )
    for state in CalibrationState:
        if state is CalibrationState.NEEDS_CONFIRMATION:
            continue
        with pytest.raises(InvalidTransitionError):
            validate_calibration_transition(state, state)
