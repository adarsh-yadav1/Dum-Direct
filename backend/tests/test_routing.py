import pytest

from app.models import MenuItem, OutletItem
from app.services.geo import haversine_km
from app.services.routing import (
    NOT_SERVICEABLE,
    SERVICEABLE,
    UNAVAILABLE_ITEMS,
    assign_outlet,
    decide,
    provisional_eta_minutes,
    rank_candidates,
)
from tests.factories import make_item, make_outlet

# One degree of latitude is about 111.19 km, so these offsets give known distances.
DEG_PER_KM = 1 / 111.19


def north_of(outlet, km):
    return outlet.latitude + km * DEG_PER_KM, outlet.longitude


def test_point_inside_radius_is_eligible(session):
    outlet = make_outlet(session, delivery_radius_km=5)
    lat, lng = north_of(outlet, 4.9)
    assert [c.outlet.id for c in rank_candidates([outlet], lat, lng)] == [outlet.id]


def test_point_outside_radius_is_not_eligible(session):
    outlet = make_outlet(session, delivery_radius_km=5)
    lat, lng = north_of(outlet, 5.1)
    assert rank_candidates([outlet], lat, lng) == []


def test_point_exactly_on_the_boundary_is_covered(session):
    outlet = make_outlet(session, delivery_radius_km=5)
    lat, lng = north_of(outlet, 5.0)
    # Make the radius exactly the measured distance, whatever the floating point rounding.
    outlet.delivery_radius_km = haversine_km(lat, lng, outlet.latitude, outlet.longitude)
    assert len(rank_candidates([outlet], lat, lng)) == 1


def test_each_outlet_uses_its_own_radius(session):
    small = make_outlet(session, name="Small", delivery_radius_km=2, latitude=17.40)
    large = make_outlet(session, name="Large", delivery_radius_km=8, latitude=17.40, longitude=78.30)
    lat, lng = north_of(small, 4)
    assert [c.outlet.name for c in rank_candidates([small, large], lat, lng)] == ["Large"]


def test_closed_outlet_is_skipped(session):
    outlet = make_outlet(session, is_open=False)
    assert rank_candidates([outlet], outlet.latitude, outlet.longitude) == []


def test_nearest_comes_first_and_ties_break_by_id(session):
    far = make_outlet(session, name="Far", latitude=17.47)
    near = make_outlet(session, name="Near", latitude=17.462)
    twin_a = make_outlet(session, name="Twin A", latitude=17.50, longitude=78.40)
    twin_b = make_outlet(session, name="Twin B", latitude=17.50, longitude=78.40)
    ranked = rank_candidates([far, near], 17.46, 78.365)
    assert [c.outlet.name for c in ranked] == ["Near", "Far"]
    ranked = rank_candidates([twin_b, twin_a], 17.50, 78.40)
    assert [c.outlet.name for c in ranked] == ["Twin A", "Twin B"]


def _two_outlets(session):
    near = make_outlet(session, name="Near", latitude=17.46, longitude=78.365)
    far = make_outlet(session, name="Far", latitude=17.48, longitude=78.365)
    return near, far


def test_nearest_outlet_wins_when_it_can_supply_everything(session):
    near, far = _two_outlets(session)
    candidates = rank_candidates([near, far], 17.46, 78.365)
    decision = decide(candidates, {1, 2}, {near.id: {1, 2}, far.id: {1, 2}})
    assert decision.status == SERVICEABLE
    assert decision.chosen.outlet.id == near.id
    assert decision.rerouted_from is None


def test_reroutes_to_a_farther_outlet_that_has_every_dish(session):
    near, far = _two_outlets(session)
    candidates = rank_candidates([near, far], 17.46, 78.365)
    decision = decide(candidates, {1, 2}, {near.id: {1}, far.id: {1, 2}})
    assert decision.status == SERVICEABLE
    assert decision.chosen.outlet.id == far.id
    assert decision.rerouted_from.id == near.id
    assert "could not supply" in decision.to_json()["reason"]


def test_when_nobody_can_supply_the_nearest_is_reported_with_missing_dishes(session):
    near, far = _two_outlets(session)
    candidates = rank_candidates([near, far], 17.46, 78.365)
    decision = decide(candidates, {1, 2, 3}, {near.id: {1}, far.id: {2}})
    assert decision.status == UNAVAILABLE_ITEMS
    assert decision.chosen.outlet.id == near.id
    assert decision.unavailable_item_ids == [2, 3]
    assert decision.to_json()["chosen"] is None


def test_empty_cart_is_served_by_the_nearest(session):
    near, far = _two_outlets(session)
    decision = decide(rank_candidates([near, far], 17.46, 78.365), [], {})
    assert decision.status == SERVICEABLE and decision.chosen.outlet.id == near.id


def test_no_candidates_is_not_serviceable():
    decision = decide([], {1}, {})
    assert decision.status == NOT_SERVICEABLE and decision.chosen is None
    assert decision.to_json()["candidates"] == []


def test_decision_json_lists_candidates_with_distances_and_missing_dishes(session):
    near, far = _two_outlets(session)
    decision = decide(rank_candidates([near, far], 17.46, 78.365), {1}, {near.id: set(), far.id: {1}})
    record = decision.to_json()
    assert record["chosen"] == "Far"
    assert [c["outlet"] for c in record["candidates"]] == ["Near", "Far"]
    assert record["candidates"][0]["missing_item_ids"] == [1]
    assert record["candidates"][0]["distance_km"] == 0.0
    assert record["candidates"][1]["distance_km"] == pytest.approx(2.22, abs=0.01)


def test_provisional_eta_adds_travel_time_rounded_up(session):
    outlet = make_outlet(session, min_prep_minutes=20)
    assert provisional_eta_minutes(outlet, 0.0, 3.0) == 20
    assert provisional_eta_minutes(outlet, 3.1, 3.0) == 30


# --- database wrapper: which dishes count as supplied -------------------------------------


def _item_id(session, name):
    variant = make_item(session, name)
    return variant.item_id


def test_paused_unlisted_and_inactive_dishes_are_not_supplied(session):
    outlet = make_outlet(session)
    ok, paused, unlisted, inactive = (_item_id(session, n) for n in ["Ok", "Paused", "Unlisted", "Inactive"])
    session.add_all(
        [
            OutletItem(outlet_id=outlet.id, item_id=ok, is_available=True),
            OutletItem(outlet_id=outlet.id, item_id=paused, is_available=False),
            OutletItem(outlet_id=outlet.id, item_id=inactive, is_available=True),
        ]
    )
    session.get(MenuItem, inactive).is_active = False
    session.flush()

    decision = assign_outlet(session, outlet.latitude, outlet.longitude, [ok, paused, unlisted, inactive])
    assert decision.status == UNAVAILABLE_ITEMS
    assert decision.unavailable_item_ids == sorted([paused, unlisted, inactive])


def test_assign_outlet_with_a_clean_cart(session):
    outlet = make_outlet(session)
    item = _item_id(session, "Ok")
    session.add(OutletItem(outlet_id=outlet.id, item_id=item, is_available=True))
    session.flush()
    decision = assign_outlet(session, outlet.latitude, outlet.longitude, [item])
    assert decision.status == SERVICEABLE and decision.chosen.outlet.id == outlet.id
