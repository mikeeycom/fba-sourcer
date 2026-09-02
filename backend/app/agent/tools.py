"""Tool definitions and schemas for the agent.

Tools define what the Claude agent can do. Each tool has:
- name: Unique identifier
- description: What the tool does
- input_schema: What parameters it accepts (JSON schema)
"""


def get_tool_schemas() -> list[dict]:
    """Get all available tool schemas for Claude.

    Returns:
        List of tool definition dicts in Claude's format
    """
    return [
        find_products_tool(),
        keepa_query_tool(),
        sp_api_fees_tool(),
        calculate_roi_tool(),
        submit_leads_tool(),
    ]


def find_products_tool() -> dict:
    """Tool to search Keepa's Product Finder for candidate ASINs.

    Returns real Amazon ASINs that already pass Michael's fixed sourcing
    filters (sales rank, buy box price, offer count, rating, monthly
    sales) - not raw web search results.
    """
    return {
        "name": "find_products",
        "description": """Search for candidate products in a category.

Returns real Amazon ASINs that already meet the sourcing criteria (sales
rank, buy box price, offer count, rating, monthly sales) - these are
pre-filtered, not raw search results. Use keepa_query on each ASIN
returned to get full product details before deciding whether it's a lead.

Use this first, before keepa_query, to find candidates.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Product category to search within",
                    "enum": [
                        "baby products",
                        "beauty",
                        "computers and accessories",
                        "diy and tools",
                        "grocery",
                        "health and personal care",
                        "pet supplies",
                        "toys and games",
                    ],
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of candidate ASINs to return (default: 20, max: 50)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["category"],
        },
    }


def keepa_query_tool() -> dict:
    """Tool to query Keepa for product data.

    Returns sales rank, price history, and monthly sales estimates for Amazon products.
    """
    return {
        "name": "keepa_query",
        "description": """Query Keepa for Amazon product sales and price data.

Given an ASIN (Amazon product ID), returns:
- Current and historical prices
- Estimated monthly sales
- Buy Box history
- Sales rank trends

Use this to validate products meet the 50+ sales/month and 20%+ ROI criteria.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "asin": {
                    "type": "string",
                    "description": """Amazon Standard Identification Number.
                    Example: 'B0C9Z7X8K2' (10 alphanumeric characters)""",
                    "pattern": "^[A-Z0-9]{10}$",
                },
                "include_history": {
                    "type": "boolean",
                    "description": "Include full price history (default: false)",
                    "default": False,
                },
            },
            "required": ["asin"],
        },
    }


def sp_api_fees_tool() -> dict:
    """Tool to get Amazon's real fee estimate for a product.

    Calls Amazon's own Product Fees API (Selling Partner API) - the same
    source SellerAmp and other sourcing tools use for accurate numbers.
    """
    return {
        "name": "get_fba_fees",
        "description": """Get Amazon's real fee estimate for a product (referral fee +
FBA fulfillment fee), straight from Amazon's own Product Fees API.

Call this AFTER keepa_query has confirmed sales volume, using the ASIN and
current price. Pass the returned total_fees into calculate_roi's fees
parameter so ROI reflects what Amazon actually charges, not just a raw
markup - this is what fixes the "ROI looks too good" problem naive
calculations have.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "asin": {
                    "type": "string",
                    "description": """Amazon Standard Identification Number.
                    Example: 'B0C9Z7X8K2' (10 alphanumeric characters)""",
                    "pattern": "^[A-Z0-9]{10}$",
                },
                "price": {
                    "type": "number",
                    "description": "Price to estimate fees at - use the current "
                    "Amazon selling price from keepa_query",
                    "minimum": 0,
                },
            },
            "required": ["asin", "price"],
        },
    }


def calculate_roi_tool() -> dict:
    """Tool to calculate ROI for a product.

    Calculation: (selling_price - cost - fees) / cost.
    """
    return {
        "name": "calculate_roi",
        "description": """Calculate ROI (Return on Investment) percentage for a product.

Given selling price, cost price, and (optionally) Amazon's fees, returns ROI
as a decimal. Example: ROI of 0.2 means 20% profit margin.

ALWAYS call get_fba_fees first and pass its total_fees here when possible -
without fees, the ROI is naive and will look much higher than what you'd
actually make, since it ignores what Amazon takes off the sale. Only omit
fees if get_fba_fees genuinely couldn't get a result for this product.

Use this to verify products meet the 20%+ ROI requirement.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "selling_price": {
                    "type": "number",
                    "description": "Price the product sells for (in GBP)",
                    "minimum": 0,
                },
                "cost_price": {
                    "type": "number",
                    "description": "Cost to source/acquire the product (in GBP)",
                    "minimum": 0.01,
                },
                "fees": {
                    "type": "number",
                    "description": "Total Amazon fees for this sale (GBP), from "
                    "get_fba_fees's total_fees. Omit or pass 0 only if fee data "
                    "isn't available - the resulting ROI will then be optimistic.",
                    "minimum": 0,
                    "default": 0,
                },
            },
            "required": ["selling_price", "cost_price"],
        },
    }


def submit_leads_tool() -> dict:
    """Tool for the agent to submit its final list of qualified leads.

    This is the agent's terminal action - calling it ends the research
    loop. Structured output avoids parsing free-text from the agent.
    """
    return {
        "name": "submit_leads",
        "description": """Submit your final list of 5-7 qualified FBA product leads.

Call this ONLY when each lead has been validated against both criteria:
- 50+ estimated monthly sales (confirmed via keepa_query)
- 20%+ ROI (confirmed via calculate_roi)

This ends your research and returns the leads to the user. Do not call
any other tool in the same turn as this one.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "leads": {
                    "type": "array",
                    "description": "5 to 7 qualified product leads",
                    "minItems": 5,
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "properties": {
                            "asin": {
                                "type": "string",
                                "description": "Amazon Standard Identification Number",
                            },
                            "title": {
                                "type": "string",
                                "description": "Product title",
                            },
                            "price": {
                                "type": "number",
                                "description": "Current Amazon selling price (GBP)",
                                "minimum": 0,
                            },
                            "cost": {
                                "type": "number",
                                "description": "Estimated sourcing cost (GBP)",
                                "minimum": 0,
                            },
                            "monthly_sales": {
                                "type": "integer",
                                "description": "Estimated monthly sales, from keepa_query",
                                "minimum": 0,
                            },
                            "roi": {
                                "type": "number",
                                "description": "ROI as a decimal (0.2 = 20%), from calculate_roi",
                                "minimum": 0,
                            },
                            "fees": {
                                "type": "number",
                                "description": "Total Amazon fees for this product (GBP), "
                                "from get_fba_fees. Include this whenever it was available "
                                "so the real fee-aware ROI is visible on the final lead.",
                                "minimum": 0,
                            },
                            "source_url": {
                                "type": "string",
                                "description": "URL where the product was sourced (optional)",
                            },
                        },
                        "required": [
                            "asin",
                            "title",
                            "price",
                            "cost",
                            "monthly_sales",
                            "roi",
                        ],
                    },
                },
            },
            "required": ["leads"],
        },
    }


# Tool input/output formats


def format_find_products_result(asins: list[str], count: int) -> dict:
    """Format a Product Finder search result for the agent.

    Args:
        asins: Candidate ASINs matching the sourcing filters
        count: Number of ASINs returned

    Returns:
        Formatted result dict
    """
    return {
        "success": True,
        "asins": asins,
        "count": count,
    }


def format_keepa_result(
    asin: str,
    monthly_sales: int,
    current_price: float,
    avg_price: float,
    rating: float = None,
) -> dict:
    """Format a Keepa query result for the agent.

    Args:
        asin: Amazon ASIN
        monthly_sales: Estimated monthly sales
        current_price: Current price in GBP
        avg_price: Average price from history
        rating: Product rating (optional)

    Returns:
        Formatted result dict
    """
    return {
        "success": True,
        "asin": asin,
        "monthly_sales": monthly_sales,
        "current_price": current_price,
        "avg_price": avg_price,
        "rating": rating,
    }


def format_fee_result(
    asin: str,
    referral_fee: float,
    fulfillment_fee: float,
    total_fees: float,
) -> dict:
    """Format an SP-API fee estimate result for the agent.

    Args:
        asin: Amazon ASIN
        referral_fee: Amazon's referral fee (percentage-of-price commission)
        fulfillment_fee: FBA fulfillment fee (pick/pack/ship cost)
        total_fees: Total of all fees - pass this into calculate_roi's fees param

    Returns:
        Formatted result dict
    """
    return {
        "success": True,
        "asin": asin,
        "referral_fee": referral_fee,
        "fulfillment_fee": fulfillment_fee,
        "total_fees": total_fees,
    }


def format_roi_result(
    selling_price: float, cost_price: float, roi: float, fees: float = 0.0
) -> dict:
    """Format an ROI calculation result for the agent.

    Args:
        selling_price: Selling price in GBP
        cost_price: Cost price in GBP
        roi: ROI as decimal (0.2 = 20%)
        fees: Amazon fees netted out of this ROI, if any

    Returns:
        Formatted result dict. Includes fees_included so it's visible at a
        glance (in logs, or to the agent) whether this ROI is a real,
        fee-aware number or a naive one.
    """
    return {
        "success": True,
        "selling_price": selling_price,
        "cost_price": cost_price,
        "fees": fees,
        "fees_included": fees > 0,
        "roi": roi,
        "roi_percent": f"{roi * 100:.1f}%",
    }


def format_tool_error(tool_name: str, error: str) -> dict:
    """Format a tool error for the agent.

    Args:
        tool_name: Name of the tool that failed
        error: Error message

    Returns:
        Formatted error dict
    """
    return {
        "success": False,
        "tool": tool_name,
        "error": error,
    }