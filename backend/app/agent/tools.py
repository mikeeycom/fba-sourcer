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
        web_search_tool(),
        keepa_query_tool(),
        sp_api_fees_tool(),
        calculate_roi_tool(),
        submit_leads_tool(),
    ]


def web_search_tool() -> dict:
    """Tool to search the web for products.

    Returns products from major retailers (Amazon, eBay excluded for manual review).
    """
    return {
        "name": "web_search",
        "description": """Search the web for products in a category.

Searches major UK retailers for products. Excludes eBay, Vinted, Qogita, and Eany.
Returns product information including title, URL, estimated price, and the
matching Amazon ASIN for that product. Always use the ASIN provided in the
result to call keepa_query - never guess or construct an ASIN yourself.

Use this to find products that might meet FBA criteria.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": """Search query. Example: 'kitchen gadgets under £30' or
                    'electronics retailers UK' or 'home improvement products'""",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return (default: 10, max: 20)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
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

    Simple calculation: (selling_price - cost) / cost.
    """
    return {
        "name": "calculate_roi",
        "description": """Calculate ROI (Return on Investment) percentage for a product.

Given selling price and cost price, returns ROI as a decimal.
Example: ROI of 0.2 means 20% profit margin.

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


def format_web_search_result(title: str, url: str, price: str, source: str, asin: str) -> dict:
    """Format a web search result for the agent.

    Args:
        title: Product title
        url: Source URL
        price: Estimated price
        source: Retailer name
        asin: Matching Amazon ASIN for this product, used to run keepa_query.
            Without this, the agent has no real ASIN to look up and will
            invent one - always require it rather than making it optional.

    Returns:
        Formatted result dict
    """
    return {
        "success": True,
        "title": title,
        "url": url,
        "price": price,
        "source": source,
        "asin": asin,
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


def format_roi_result(selling_price: float, cost_price: float, roi: float) -> dict:
    """Format an ROI calculation result for the agent.

    Args:
        selling_price: Selling price in GBP
        cost_price: Cost price in GBP
        roi: ROI as decimal (0.2 = 20%)

    Returns:
        Formatted result dict
    """
    return {
        "success": True,
        "selling_price": selling_price,
        "cost_price": cost_price,
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