import itertools

import pytest

from app.models.enums import OrderStatus
from app.services.order_state import (
    KITCHEN_MOVES,
    TRANSITIONS,
    IllegalTransition,
    can_kitchen_move,
    can_transition,
    check_transition,
)

ALL = [s.value for s in OrderStatus]
HAPPY_PATH = ["pending_payment", "new", "preparing", "ready", "handed_off", "completed"]


def test_every_status_has_an_entry():
    assert set(TRANSITIONS) == set(ALL)


def test_the_happy_path_is_legal_step_by_step():
    for current, target in itertools.pairwise(HAPPY_PATH):
        assert can_transition(current, target)


@pytest.mark.parametrize("final", ["completed", "cancelled", "payment_failed"])
def test_final_states_go_nowhere(final):
    assert not any(can_transition(final, other) for other in ALL)


def test_no_stage_can_be_skipped_or_reversed():
    for a, b in itertools.permutations(HAPPY_PATH, 2):
        legal = HAPPY_PATH.index(b) - HAPPY_PATH.index(a) == 1
        assert can_transition(a, b) is legal


@pytest.mark.parametrize("current", ["ready", "handed_off", "completed"])
def test_an_order_past_preparing_cannot_be_cancelled(current):
    assert not can_transition(current, "cancelled")


@pytest.mark.parametrize("current", ["new", "preparing"])
def test_early_orders_can_be_cancelled(current):
    assert can_transition(current, "cancelled")


def test_check_transition_raises_with_both_states():
    with pytest.raises(IllegalTransition) as caught:
        check_transition("new", "ready")
    assert "new" in str(caught.value) and "ready" in str(caught.value)


def test_kitchen_cannot_make_payment_moves():
    assert not can_kitchen_move("pending_payment", "new")
    assert not can_kitchen_move("pending_payment", "payment_failed")


def test_every_kitchen_move_is_a_legal_transition():
    assert all(can_transition(a, b) for a, b in KITCHEN_MOVES)
