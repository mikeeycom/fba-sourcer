"""Utility functions for calculating ROI and profit margins."""


def calculate_roi(selling_price: float, cost_price: float) -> float:
    """Calculate ROI (Return on Investment) percentage.

    ROI = (selling_price - cost_price) / cost_price

    Example:
        Selling £100, cost £80 → ROI = 0.25 (25%)

    Args:
        selling_price: Price product sells for (GBP)
        cost_price: Cost to acquire product (GBP)

    Returns:
        ROI as decimal (0.2 = 20%, 0.5 = 50%)

    Raises:
        ValueError: If inputs are invalid
    """
    if not isinstance(selling_price, (int, float)) or not isinstance(
        cost_price, (int, float)
    ):
        raise ValueError("Prices must be numbers")

    if cost_price <= 0:
        raise ValueError("Cost price must be greater than 0")

    if selling_price < 0:
        raise ValueError("Selling price cannot be negative")

    roi = (selling_price - cost_price) / cost_price
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