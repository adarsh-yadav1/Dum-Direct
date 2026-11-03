from fractions import Fraction

import pytest

from app.services.pricing import gst_included_paise


@pytest.mark.parametrize(
    ("total_paise", "expected"),
    [
        (0, 0),
        (105, 5),  # Rs 1.05 contains exactly 5 paise of GST
        (105_000, 5_000),  # Rs 1,050 contains exactly Rs 50 of GST
        (118_000, 5_619),  # Rs 1,180: 5619.05 paise, rounds down
        (64_000, 3_048),  # Rs 640: 3047.62 paise, rounds up
    ],
)
def test_gst_component_of_known_totals(total_paise: int, expected: int):
    assert gst_included_paise(total_paise) == expected


def test_result_is_the_nearest_whole_paisa_for_every_small_total():
    for total in range(0, 20_001):
        exact = Fraction(total * 5, 105)
        assert abs(gst_included_paise(total) - exact) <= Fraction(1, 2)


def test_gst_never_exceeds_the_total():
    assert all(gst_included_paise(total) <= total for total in range(0, 2_000))


def test_negative_totals_are_rejected():
    with pytest.raises(ValueError):
        gst_included_paise(-1)
