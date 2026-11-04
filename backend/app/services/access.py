"""Who may do what. Pure functions, so the rules are easy to read and to test.

Kitchen and manager accounts belong to one outlet and may only act on that outlet
(assumption A12). Admins act on every outlet. Customers have no outlet-side access;
they may only see their own orders.
"""

from app.models import Order, User
from app.models.enums import OUTLET_BOUND_ROLES, Role

_OUTLET_BOUND = {role.value for role in OUTLET_BOUND_ROLES}


def can_access_outlet(user: User, outlet_id: int) -> bool:
    """Read the outlet's orders and change their preparation stage, or pause its items."""
    if user.role == Role.ADMIN.value:
        return True
    return user.role in _OUTLET_BOUND and user.outlet_id == outlet_id


def can_override_estimate(user: User, outlet_id: int) -> bool:
    """Change a promised time. Kitchen staff cannot: the manager owns the promise."""
    if user.role == Role.ADMIN.value:
        return True
    return user.role == Role.MANAGER.value and user.outlet_id == outlet_id


def can_view_order(user: User, order: Order) -> bool:
    return order.user_id == user.id or can_access_outlet(user, order.outlet_id)
