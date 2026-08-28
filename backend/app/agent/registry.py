"""Tool registry for agent tool execution.

The registry is a dispatcher that routes tool calls to the right client.
When the agent needs to execute a tool, it calls registry.execute_tool(name, input).
The registry looks up the handler and delegates to it.
"""

from app.clients.web_search_client import WebSearchClient
from app.utils.calculator import calculate_roi
from app.agent.tools import format_tool_error, format_roi_result
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Registry mapping tool names to implementations.

    Provides a single dispatch point for all agent tool execution.
    Handles routing, error handling, and result formatting.
    """

    def __init__(self):
        """Initialize registry with tool clients."""
        self.web_search_client = WebSearchClient()

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

            if tool_name == "web_search":
                return self._execute_web_search(tool_input)
            elif tool_name == "keepa_query":
                return self._execute_keepa_query(tool_input)
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

    def _execute_web_search(self, tool_input: dict) -> dict:
        """Execute web search tool.

        Args:
            tool_input: Dict with 'query' and optional 'limit'

        Returns:
            Search results or error
        """
        query = tool_input.get("query")
        limit = tool_input.get("limit", 10)

        if not query:
            return format_tool_error("web_search", "Missing required parameter: query")

        return self.web_search_client.search(query, limit)

    def _execute_keepa_query(self, tool_input: dict) -> dict:
        """Execute Keepa query tool.

        Args:
            tool_input: Dict with 'asin' and optional 'include_history'

        Returns:
            Keepa data or error (not yet implemented)

        Note:
            Implemented in Phase 3 when Keepa client is ready.
        """
        asin = tool_input.get("asin")
        if not asin:
            return format_tool_error("keepa_query", "Missing required parameter: asin")

        # TODO: Implement Keepa client in Phase 3
        return format_tool_error(
            "keepa_query", "Keepa integration coming in Phase 3"
        )

    def _execute_calculate_roi(self, tool_input: dict) -> dict:
        """Execute ROI calculation tool.

        Args:
            tool_input: Dict with 'selling_price' and 'cost_price'

        Returns:
            ROI calculation or error
        """
        selling_price = tool_input.get("selling_price")
        cost_price = tool_input.get("cost_price")

        if selling_price is None or cost_price is None:
            return format_tool_error(
                "calculate_roi", "Missing required parameters: selling_price, cost_price"
            )

        try:
            roi = calculate_roi(selling_price, cost_price)
            return format_roi_result(selling_price, cost_price, roi)
        except ValueError as e:
            return format_tool_error("calculate_roi", str(e))