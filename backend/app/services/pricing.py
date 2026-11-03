"""Price arithmetic. All amounts are integer paise (1 rupee = 100 paise).

Every menu price includes 5% GST (assumption A5), so tax is never added on top:
it is the part of the total that is already tax, shown on the bill.
"""

GST_PERCENT = 5


def gst_included_paise(total_paise: int) -> int:
    """GST contained in a GST-inclusive total: total * 5 / 105, rounded half up.

    Pure integer arithmetic, so there is no floating-point error:
    floor(total * 5 / 105 + 1/2) = floor((total * 10 + 105) / 210).
    """
    if total_paise < 0:
        raise ValueError("total_paise must not be negative")
    divisor = 100 + GST_PERCENT
    return (total_paise * GST_PERCENT * 2 + divisor) // (divisor * 2)
