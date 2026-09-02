"""Tool registry for agent tool execution.

The registry is a dispatcher that routes tool calls to the right client.
When the agent needs to execute a tool, it calls registry.execute_tool(name, input).
The registry looks up the handler and delegates to it.
"""

from app.agent.tools import (
    format_fee_result,
    format_find_products_result,
    format_keepa_result,
    format_roi_result,
    format_tool_error,
)
from app.clients.keepa_client import KeepaClient
from app.clients.sp_api_client import SpApiClient
from app.utils.calculator import calculate_roi
from app.utils.exceptions import APIError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Product titles that disqualify a candidate outright - checked in code,
# not left to the agent's judgment, since it's a hard house rule rather
# than something worth spending a tool call/reasoning step on. Covers
# trading card games broadly (any brand) and their accessories (sleeves,
# binders, toploaders, etc.), not just Pokemon-branded items.
EXCLUDED_TITLE_KEYWORDS = [
    "pokemon",
    "pokémon",
    "trading card",
    "tcg",
    "yu-gi-oh",
    "yugioh",
    "magic: the gathering",
    "magic the gathering",
    "mtg",
    "card sleeve",
    "toploader",
    "top loader",
    "card binder",
    "booster pack",
    "booster box",
    "elite trainer box",
]

# Hard cap on keepa_query calls per agent run. Keepa's token bucket can
# refill as slowly as 1 token/minute, so an unbounded agent loop could
# otherwise burn through an entire run's tokens - and future runs' - on a
# single overly-thorough search. Bumped from 8 -> 12: the checklist signals
# give the agent more legitimate reasons to reject a candidate, so it needs
# to check more of them to still land 5-7 leads.
MAX_KEEPA_CALLS_PER_RUN = 12

# Hard cap on find_products calls per agent run. Capped at 1, not because
# retries wouldn't be useful, but because a single find_products call costs
# roughly 15-20x what one keepa_query call does (confirmed via live testing -
# one search burned ~50 tokens vs ~3 for a per-ASIN lookup) from the SAME
# shared Keepa token bucket. A retry can silently starve the budget the
# agent needs to actually check the candidates it already has.
MAX_KEEPA_FINDER_CALLS_PER_RUN = 1

# Hard cap on get_fba_fees calls per agent run. Amazon's fee endpoint is
# far less restrictive than Keepa (1 request/second, not 1/minute), so
# this cap exists for consistency and to bound worst-case run latency -
# not because fee-lookup tokens are scarce like Keepa's.
MAX_SP_API_CALLS_PER_RUN = 10


class ToolRegistry:
    """Registry mapping tool names to implementations.

    Provides a single dispatch point for all agent tool execution.
    Handles routing, error handling, and result formatting.
    """

    def __init__(self):
        """Initialize registry with tool clients.

        sp_api_client is deliberately NOT built here, unlike the others -
        it requires Amazon credentials that may not be configured yet, and
        building it eagerly would crash the whole app on startup even for
        users who never touch the fees tool. It's built lazily on first
        use instead - see _get_sp_api_client().
        """
        self.keepa_client = KeepaClient()
        self.sp_api_client = None
        self._keepa_call_count = 0
        self._keepa_finder_call_count = 0
        self._sp_api_call_count = 0

    def _get_sp_api_client(self) -> SpApiClient:
        """Lazily construct and cache the SP-API client on first use.

        Returns:
            The SpApiClient instance

        Raises:
            ValueError: If SP-API credentials aren't configured - this is
                caught by execute_tool's catch-all and turned into a
                normal tool error, not an app crash.
        """
        if self.sp_api_client is None:
            self.sp_api_client = SpApiClient()
        return self.sp_api_client

    def reset(self) -> None:
        """Reset per-run state. Call this at the start of each agent run.

        The registry itself is a long-lived singleton (one per app process),
        so per-run counters like the Keepa call cap must be explicitly reset
        rather than assumed fresh. Note this does NOT clear KeepaClient's or
        SpApiClient's caches - cached results/cooldowns (and SpApiClient's
        access token) are intentionally kept across runs, since re-fetching
        them every run wastes calls and adds latency for no benefit.
        """
        self._keepa_call_count = 0
        self._keepa_finder_call_count = 0
        self._sp_api_call_count = 0

    def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            Formatted result dict with success flag and data/error
        """
        try:
            logger.info(
                "Executing tool",
                extra={"tool": tool_name, "input_keys": list(tool_input.keys())},
            )

            if tool_name == "find_products":
                return self._execute_find_products(tool_input)
            elif tool_name == "keepa_query":
                return self._execute_keepa_query(tool_input)
            elif tool_name == "get_fba_fees":
                return self._execute_get_fba_fees(tool_input)
            elif tool_name == "calculate_roi":
                return self._execute_calculate_roi(tool_input)
            else:
                return format_tool_error(tool_name, f"Unknown tool: {tool_name}")

        except Exception as e:
            logger.error(
                "Tool execution failed",
                extra={"tool": tool_name, "error": str(e)},
            )
            return format_tool_error(tool_name, str(e))

    def _execute_find_products(self, tool_input: dict) -> dict:
        """Execute the Keepa Product Finder search tool.

        Args:
            tool_input: Dict with 'category' and optional 'limit'

        Returns:
            Candidate ASINs or error
        """
        category = tool_input.get("category")
        limit = tool_input.get("limit", 20)

        if not category:
            return format_tool_error("find_products", "Missing required parameter: category")

        if self._keepa_finder_call_count >= MAX_KEEPA_FINDER_CALLS_PER_RUN:
            logger.warning(
                "Keepa finder call budget exhausted for this run",
                extra={"category": category, "cap": MAX_KEEPA_FINDER_CALLS_PER_RUN},
            )
            return format_tool_error(
                "find_products",
                f"Product search budget for this run ({MAX_KEEPA_FINDER_CALLS_PER_RUN} "
                "calls) is exhausted. Work with the candidates already found.",
            )

        self._keepa_finder_call_count += 1

        try:
            asins = self.keepa_client.find_products(category, limit)
            return format_find_products_result(asins=asins, count=len(asins))
        except APIError as e:
            return format_tool_error("find_products", str(e))

    def _execute_keepa_query(self, tool_input: dict) -> dict:
        """Execute Keepa query tool.

        Args:
            tool_input: Dict with 'asin' and optional 'include_history'

        Returns:
            Keepa sales/price data or error
        """
        asin = tool_input.get("asin")
        if not asin:
            return format_tool_error("keepa_query", "Missing required parameter: asin")

        if self._keepa_call_count >= MAX_KEEPA_CALLS_PER_RUN:
            logger.warning(
                "Keepa call budget exhausted for this run",
                extra={"asin": asin, "cap": MAX_KEEPA_CALLS_PER_RUN},
            )
            return format_tool_error(
                "keepa_query",
                f"Keepa lookup budget for this search ({MAX_KEEPA_CALLS_PER_RUN} calls) "
                "is exhausted. Submit leads using only the products already validated, "
                "even if fewer than 5-7.",
            )

        include_history = tool_input.get("include_history", False)
        self._keepa_call_count += 1

        try:
            product = self.keepa_client.query_product(asin, include_history)

            if self._is_excluded_title(product["title"]):
                logger.info(
                    "Excluded product (trading cards/accessories)",
                    extra={"asin": asin, "title": product["title"]},
                )
                return format_tool_error(
                    "keepa_query",
                    f"'{product['title']}' is a trading card game product or "
                    "accessory (or similar) - these are excluded from sourcing. "
                    "Do not use this ASIN, check a different candidate instead.",
                )

            return format_keepa_result(
                asin=product["asin"],
                title=product["title"],
                monthly_sales=product["monthly_sales"],
                current_price=product["current_price"],
                avg_price=product["avg_price"],
                rating=product["rating"],
                offer_count_trend=product["offer_count_trend"],
                buy_box_top_seller_share_pct=product["buy_box_top_seller_share_pct"],
                buy_box_dominant_seller_warning=product["buy_box_dominant_seller_warning"],
                ean=product["ean"],
                brand=product["brand"],
                price_90d_low=product["price_90d_low"],
            )
        except APIError as e:
            return format_tool_error("keepa_query", str(e))

    def _execute_get_fba_fees(self, tool_input: dict) -> dict:
        """Execute the SP-API fees lookup tool.

        Args:
            tool_input: Dict with 'asin' and 'price'

        Returns:
            Fee estimate data or error
        """
        asin = tool_input.get("asin")
        price = tool_input.get("price")

        if not asin or price is None:
            return format_tool_error(
                "get_fba_fees", "Missing required parameters: asin, price"
            )

        if self._sp_api_call_count >= MAX_SP_API_CALLS_PER_RUN:
            logger.warning(
                "SP-API call budget exhausted for this run",
                extra={"asin": asin, "cap": MAX_SP_API_CALLS_PER_RUN},
            )
            return format_tool_error(
                "get_fba_fees",
                f"Fee lookup budget for this search ({MAX_SP_API_CALLS_PER_RUN} calls) "
                "is exhausted. Proceed with calculate_roi without the fees parameter "
                "for remaining products, or submit leads using only those already "
                "validated.",
            )

        self._sp_api_call_count += 1

        try:
            fees = self._get_sp_api_client().get_fees_estimate(asin, price)
            return format_fee_result(
                asin=fees["asin"],
                referral_fee=fees["referral_fee"],
                fulfillment_fee=fees["fulfillment_fee"],
                total_fees=fees["total_fees"],
            )
        except APIError as e:
            return format_tool_error("get_fba_fees", str(e))

    def _execute_calculate_roi(self, tool_input: dict) -> dict:
        """Execute ROI calculation tool.

        Args:
            tool_input: Dict with 'selling_price', 'cost_price', and
                optional 'fees'

        Returns:
            ROI calculation or error
        """
        selling_price = tool_input.get("selling_price")
        cost_price = tool_input.get("cost_price")
        fees = tool_input.get("fees", 0.0)

        if selling_price is None or cost_price is None:
            return format_tool_error(
                "calculate_roi", "Missing required parameters: selling_price, cost_price"
            )

        try:
            roi = calculate_roi(selling_price, cost_price, fees)
            return format_roi_result(selling_price, cost_price, roi, fees)
        except ValueError as e:
            return format_tool_error("calculate_roi", str(e))

    @staticmethod
    def _is_excluded_title(title: str | None) -> bool:
        """Check a product title against the hard exclusion list.

        Checked in code rather than left to the agent's judgment - it's a
        house rule, not something that needs a reasoning step each time.

        Args:
            title: Product title from Keepa, or None

        Returns:
            True if the title matches an excluded keyword
        """
        if not title:
            return False
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in EXCLUDED_TITLE_KEYWORDS)