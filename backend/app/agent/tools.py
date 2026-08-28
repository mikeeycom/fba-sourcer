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
        calculate_roi_tool(),
    ]


def web_search_tool() -> dict:
    """Tool to search the web for products.

    Returns products from major retailers (Amazon, eBay excluded for manual review).
    """
    return {
        "name": "web_search",
        "description": """Search the web for products in a category.

Searches major UK retailers for products. Excludes eBay, Vinted, Qogita, and Eany.
Returns product information including title, URL, and estimated price.

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


# Tool input/output formats


def format_web_search_result(title: str, url: str, price: str, source: str) -> dict:
    """Format a web search result for the agent.

    Args:
        title: Product title
        url: Source URL
        price: Estimated price
        source: Retailer name

    Returns:
        Formatted result dict
    """
    return {
        "success": True,
        "title": title,
        "url": url,
        "price": price,
        "source": source,
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