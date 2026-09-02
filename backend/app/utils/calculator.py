"""Utility functions for calculating ROI and profit margins."""


def calculate_roi(selling_price: float, cost_price: float, fees: float = 0.0) -> float:
    """Calculate ROI (Return on Investment) percentage.

    ROI = (selling_price - cost_price - fees) / cost_price

    fees defaults to 0 for backward compatibility, but omitting it gives an
    overly optimistic ROI - Amazon takes a real cut (referral fee + FBA
    fulfillment fee) that isn't in the raw price/cost numbers. Pass the
    total_fees from get_fba_fees whenever it's available.

    Example:
        Selling £30, cost £12, no fees → ROI = 1.5 (150%, looks great)
        Selling £30, cost £12, £9 fees → ROI = 0.75 (75%, the real number)

    Args:
        selling_price: Price product sells for (GBP)
        cost_price: Cost to acquire product (GBP)
        fees: Total Amazon fees for this sale (GBP), from get_fba_fees.
            Defaults to 0 if fee data isn't available - the result will
            then be a naive, optimistic ROI rather than a real one.

    Returns:
        ROI as decimal (0.2 = 20%, 0.5 = 50%)

    Raises:
        ValueError: If inputs are invalid
    """
    if (
        not isinstance(selling_price, (int, float))
        or not isinstance(cost_price, (int, float))
        or not isinstance(fees, (int, float))
    ):
        raise ValueError("Prices and fees must be numbers")

    if cost_price <= 0:
        raise ValueError("Cost price must be greater than 0")

    if selling_price < 0:
        raise ValueError("Selling price cannot be negative")

    if fees < 0:
        raise ValueError("Fees cannot be negative")

    roi = (selling_price - cost_price - fees) / cost_price
    return round(roi, 4)


def calculate_profit(selling_price: float, cost_price: float) -> float:
    """Calculate profit amount.

    Profit = selling_price - cost_price

    Args:
        selling_price: Price product sells for (GBP)
        cost_price: Cost to acquire product (GBP)

    Returns:
        Profit amount (GBP)

    Raises:
        ValueError: If inputs are invalid
    """
    if not isinstance(selling_price, (int, float)) or not isinstance(
        cost_price, (int, float)
    ):
        raise ValueError("Prices must be numbers")

    if cost_price < 0 or selling_price < 0:
        raise ValueError("Prices cannot be negative")

    return round(selling_price - cost_price, 2)