"""Automatic outlet assignment.

The customer never picks an outlet. Given a delivery point and the dishes in the cart, the
system picks one:

1. Eligible outlets are open and have the point inside their own delivery radius. A point
   exactly on the boundary is covered.
2. Eligible outlets are ranked by distance, then by id, so ties are stable.
3. The nearest eligible outlet that can supply every dish in the cart wins.
4. If the nearest cannot but a farther one can, the order is rerouted and says so.
5. If no eligible outlet can supply everything, the nearest is reported with the missing dishes.
6. If no outlet covers the point, it is not serviceable.

The ranking and the decision are pure functions. Only `assign_outlet` touches the database.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MenuItem, Outlet, OutletItem
from app.services.geo import haversine_km

SERVICEABLE = "serviceable"
UNAVAILABLE_ITEMS = "unavailable_items"
NOT_SERVICEABLE = "not_serviceable"


@dataclass(frozen=True)
class Candidate:
    outlet: Outlet
    distance_km: float


@dataclass
class Decision:
    status: str
    chosen: Candidate | None = None
    rerouted_from: Outlet | None = None
    # Dishes the chosen outlet cannot supply. Empty when status is "serviceable".
    unavailable_item_ids: list[int] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    missing_by_outlet: dict[int, list[int]] = field(default_factory=dict)

    def to_json(self) -> dict:
        """The record stored on an order, so support can see why this outlet was chosen."""
        if self.status == SERVICEABLE and self.chosen is not None:
            reason = "nearest open outlet whose delivery radius covers the address"
            if self.rerouted_from is not None:
                reason = (
                    f"{self.rerouted_from.name} could not supply every dish, "
                    "so the nearest outlet that could was chosen"
                )
        elif self.status == UNAVAILABLE_ITEMS:
            reason = "no covering outlet can supply every dish"
        else:
            reason = "no open outlet delivers to this address"
        return {
            "chosen": self.chosen.outlet.name if self.status == SERVICEABLE and self.chosen else None,
            "reason": reason,
            "candidates": [
                {
                    "outlet": c.outlet.name,
                    "distance_km": round(c.distance_km, 2),
                    "missing_item_ids": self.missing_by_outlet.get(c.outlet.id, []),
                }
                for c in self.candidates
            ],
        }


def rank_candidates(outlets: Iterable[Outlet], latitude: float, longitude: float) -> list[Candidate]:
    """Open outlets that cover the point, nearest first, ties broken by id."""
    found = []
    for outlet in outlets:
        if not outlet.is_open:
            continue
        distance = haversine_km(latitude, longitude, outlet.latitude, outlet.longitude)
        if distance <= outlet.delivery_radius_km:
            found.append(Candidate(outlet, distance))
    return sorted(found, key=lambda c: (c.distance_km, c.outlet.id))


def decide(
    candidates: list[Candidate],
    wanted_item_ids: Iterable[int],
    supplied_by_outlet: Mapping[int, set[int]],
) -> Decision:
    """Choose among ranked candidates. `supplied_by_outlet` maps outlet id to the dish ids it can serve now."""
    if not candidates:
        return Decision(status=NOT_SERVICEABLE)

    wanted = set(wanted_item_ids)
    missing = {
        c.outlet.id: sorted(wanted - supplied_by_outlet.get(c.outlet.id, set())) for c in candidates
    }

    for candidate in candidates:
        if not missing[candidate.outlet.id]:
            nearest = candidates[0]
            return Decision(
                status=SERVICEABLE,
                chosen=candidate,
                rerouted_from=None if candidate is nearest else nearest.outlet,
                candidates=candidates,
                missing_by_outlet=missing,
            )

    nearest = candidates[0]
    return Decision(
        status=UNAVAILABLE_ITEMS,
        chosen=nearest,
        unavailable_item_ids=missing[nearest.outlet.id],
        candidates=candidates,
        missing_by_outlet=missing,
    )


def provisional_eta_minutes(outlet: Outlet, distance_km: float, minutes_per_km: float) -> int:
    """A first estimate shown before an order exists: the outlet's minimum prep plus travel."""
    return outlet.min_prep_minutes + math.ceil(distance_km * minutes_per_km)


def supplied_item_ids(db: Session, outlet_ids: Iterable[int], item_ids: Iterable[int]) -> dict[int, set[int]]:
    """Dishes each outlet can serve now: listed, not paused, and still active on the menu."""
    outlet_ids, item_ids = list(outlet_ids), list(item_ids)
    supplied: dict[int, set[int]] = {outlet_id: set() for outlet_id in outlet_ids}
    if not outlet_ids or not item_ids:
        return supplied
    rows = db.execute(
        select(OutletItem.outlet_id, OutletItem.item_id)
        .join(MenuItem, MenuItem.id == OutletItem.item_id)
        .where(
            OutletItem.outlet_id.in_(outlet_ids),
            OutletItem.item_id.in_(item_ids),
            OutletItem.is_available.is_(True),
            MenuItem.is_active.is_(True),
        )
    )
    for outlet_id, item_id in rows:
        supplied[outlet_id].add(item_id)
    return supplied


def assign_outlet(db: Session, latitude: float, longitude: float, item_ids: Iterable[int]) -> Decision:
    wanted = set(item_ids)
    candidates = rank_candidates(db.scalars(select(Outlet)), latitude, longitude)
    supplied = supplied_item_ids(db, [c.outlet.id for c in candidates], wanted)
    return decide(candidates, wanted, supplied)
