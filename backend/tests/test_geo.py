import math

import pytest

from app.services.geo import EARTH_RADIUS_KM, haversine_km


def test_distance_to_the_same_point_is_zero():
    assert haversine_km(17.46, 78.365, 17.46, 78.365) == 0.0


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_km(17.0, 78.0, 18.0, 78.0) == pytest.approx(111.19, abs=0.05)


def test_distance_is_symmetric():
    a = haversine_km(17.46, 78.365, 17.44, 78.348)
    b = haversine_km(17.44, 78.348, 17.46, 78.365)
    assert a == pytest.approx(b)


def test_kondapur_to_gachibowli_is_about_three_kilometres():
    # Illustrative outlet coordinates used by the seed data.
    assert haversine_km(17.46, 78.365, 17.44, 78.348) == pytest.approx(2.9, abs=0.1)


def test_longitude_degrees_shrink_towards_the_poles():
    at_equator = haversine_km(0.0, 0.0, 0.0, 1.0)
    at_60_north = haversine_km(60.0, 0.0, 60.0, 1.0)
    assert at_60_north == pytest.approx(at_equator / 2, rel=0.01)


def test_antipodal_points_do_not_crash():
    assert haversine_km(0.0, 0.0, 0.0, 180.0) == pytest.approx(math.pi * EARTH_RADIUS_KM)
