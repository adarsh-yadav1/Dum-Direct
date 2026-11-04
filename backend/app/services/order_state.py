"""The life of an order. One table says which moves are legal and who may make them.

    pending_payment -> new -> preparing -> ready -> handed_off -> completed
    pending_payment -> payment_failed          (a failed payment is final; the customer places a new order)
    new | preparing -> cancelled               (an order already ready or collected cannot be cancelled)

Payment moves are made by the payment service, kitchen moves by outlet staff. Nobody may skip
a stage or move backwards, so the board and the customer's tracker can never disagree.
"""

from app.models.enums import OrderStatus as S

# status -> the statuses it may move to
TRANSITIONS: dict[str, frozenset[str]] = {
    S.PENDING_PAYMENT: frozenset({S.NEW, S.PAYMENT_FAILED}),
    S.NEW: frozenset({S.PREPARING, S.CANCELLED}),
    S.PREPARING: frozenset({S.READY, S.CANCELLED}),
    S.READY: frozenset({S.HANDED_OFF}),
    S.HANDED_OFF: frozenset({S.COMPLETED}),
    S.PAYMENT_FAILED: frozenset(),
    S.COMPLETED: frozenset(),
    S.CANCELLED: frozenset(),
}

# Moves outlet staff may make from the board. Payment moves are never theirs.
KITCHEN_MOVES: frozenset[tuple[str, str]] = frozenset(
    {
        (S.NEW, S.PREPARING),
        (S.PREPARING, S.READY),
        (S.READY, S.HANDED_OFF),
        (S.HANDED_OFF, S.COMPLETED),
        (S.NEW, S.CANCELLED),
        (S.PREPARING, S.CANCELLED),
    }
)

# Orders the kitchen still has to deal with.
OPEN_STATUSES = frozenset({S.NEW, S.PREPARING, S.READY})


class IllegalTransition(Exception):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"An order that is {current} cannot become {target}.")
        self.current, self.target = current, target


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def check_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise IllegalTransition(current, target)


def can_kitchen_move(current: str, target: str) -> bool:
    return (current, target) in KITCHEN_MOVES
