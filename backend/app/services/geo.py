"""Distance between two points on the Earth's surface."""

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0088  # mean radius


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (straight-line) distance in kilometres between two coordinates.

    Delivery eligibility uses this straight-line distance, not road distance
    (assumption A3): no paid maps service is needed, at the cost of being optimistic
    where roads are indirect.
    """
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    # min() guards against a rounding error pushing a fraction above 1 for antipodal points.
    return 2 * EARTH_RADIUS_KM * asin(sqrt(min(1.0, a)))
