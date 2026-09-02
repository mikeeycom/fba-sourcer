"""Pydantic models for request/response validation."""

from typing import Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    """Product representation."""

    asin: str = Field(..., description="Amazon Standard Identification Number")
    title: str = Field(..., description="Product title")
    price: float = Field(..., ge=0, description="Current price in GBP")
    cost: float = Field(..., ge=0, description="Sourcing cost in GBP")
    monthly_sales: int = Field(..., ge=0, description="Estimated monthly sales")
    roi: float = Field(..., ge=0, le=10, description="ROI as decimal (0.2 = 20%)")
    fees: Optional[float] = Field(
        None,
        ge=0,
        description="Estimated Amazon fees (referral + FBA fulfillment) netted "
        "out of roi. None if fee lookup wasn't available for this product - in "
        "that case roi is a naive, optimistic estimate rather than a real one.",
    )
    offer_count_trend: Optional[str] = Field(
        None,
        description="Whether new-offer competition is rising, stable, or "
        "falling ('increasing'/'stable'/'decreasing'). None if unavailable.",
    )
    price_floor_ok: Optional[bool] = Field(
        None,
        description="True if the price hasn't dropped below breakeven in the "
        "last 90 days. None if there wasn't enough price history to check.",
    )
    source_url: Optional[str] = Field(None, description="Source retailer URL")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "asin": "B123456789",
                "title": "Example Product",
                "price": 50.0,
                "cost": 30.0,
                "monthly_sales": 150,
                "roi": 0.67,
                "fees": 4.5,
                "offer_count_trend": "stable",
                "price_floor_ok": True,
                "source_url": "https://example.com/product",
            }
        }


class FindLeadsRequest(BaseModel):
    """Request to find leads in a category."""

    category: str = Field(..., description="Product category (e.g., 'electronics')")

    class Config:
        """Pydantic config."""

        json_schema_extra = {"example": {"category": "electronics"}}


class FindLeadsResponse(BaseModel):
    """Response with found leads."""

    success: bool = Field(..., description="Whether the search succeeded")
    leads: list[Product] = Field(default_factory=list, description="List of found leads")
    error: Optional[str] = Field(None, description="Error message if failed")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "success": True,
                "leads": [
                    {
                        "asin": "B123456789",
                        "title": "Example Product",
                        "price": 50.0,
                        "cost": 30.0,
                        "monthly_sales": 150,
                        "roi": 0.67,
                        "fees": 4.5,
                        "offer_count_trend": "stable",
                        "price_floor_ok": True,
                        "source_url": "https://example.com/product",
                    }
                ],
                "error": None,
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")

    class Config:
        """Pydantic config."""

        json_schema_extra = {"example": {"status": "healthy", "version": "0.1.0"}}