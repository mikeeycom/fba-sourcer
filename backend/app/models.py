"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field
from typing import Optional, Any


class Product(BaseModel):
    """Product representation."""

    asin: str = Field(..., description="Amazon Standard Identification Number")
    title: str = Field(..., description="Product title")
    price: float = Field(..., ge=0, description="Current price in GBP")
    cost: float = Field(..., ge=0, description="Sourcing cost in GBP")
    monthly_sales: int = Field(..., ge=0, description="Estimated monthly sales")
    roi: float = Field(..., ge=0, le=10, description="ROI as decimal (0.2 = 20%)")
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