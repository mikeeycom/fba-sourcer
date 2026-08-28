"""Web search client for finding products.

Currently uses mocked data for development.
TODO: Integrate real search API (Google Custom Search, Bing, etc) in Phase 4.
"""

from app.agent.tools import format_web_search_result, format_tool_error
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchClient:
    """Client for searching the web for products.

    Searches major UK retailers for products matching a query.
    Excludes eBay, Vinted, Qogita, Eany (manual review only).
    """

    def search(self, query: str, limit: int = 10) -> dict:
        """Search for products on the web.

        Args:
            query: Search query (e.g., 'kitchen gadgets under £30')
            limit: Max results to return (default: 10, max: 20)

        Returns:
            Dict with success flag and results list
        """
        try:
            limit = min(limit, 20)  # Cap at 20
            logger.info("Web search", extra={"query": query, "limit": limit})

            # For now, return mocked results
            # TODO: Integrate real search API
            results = self._mock_search(query, limit)

            logger.info(
                "Web search complete",
                extra={"query": query, "result_count": len(results)},
            )

            return {
                "success": True,
                "results": results,
                "query": query,
                "count": len(results),
            }

        except Exception as e:
            logger.error("Web search failed", extra={"query": query, "error": str(e)})
            return format_tool_error("web_search", str(e))

    def _mock_search(self, query: str, limit: int) -> list[dict]:
        """Return mocked search results for development.

        In production, this would call a real search API.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of product dicts with title, url, price, source
        """
        # Mock products from various UK retailers
        mock_products = [
            format_web_search_result(
                title="Premium Kitchen Gadget Set - 12 Piece",
                url="https://johnlewis.com/product/KG12345",
                price="£24.99",
                source="John Lewis",
            ),
            format_web_search_result(
                title="Multi-function Food Processor 800W",
                url="https://currys.co.uk/product/FP67890",
                price="£34.99",
                source="Currys",
            ),
            format_web_search_result(
                title="Stainless Steel Mixing Bowls Set of 3",
                url="https://lakeland.co.uk/product/MB54321",
                price="£18.99",
                source="Lakeland",
            ),
            format_web_search_result(
                title="Silicone Baking Mat Set Non-stick",
                url="https://johnlewis.com/product/BM98765",
                price="£12.99",
                source="John Lewis",
            ),
            format_web_search_result(
                title="Bamboo Utensil Holder Organizer",
                url="https://amazon.co.uk/product/UH11111",
                price="£15.99",
                source="Amazon",
            ),
            format_web_search_result(
                title="Digital Cooking Thermometer with Probe",
                url="https://screwfix.com/product/CT22222",
                price="£19.99",
                source="Screwfix",
            ),
            format_web_search_result(
                title="Microwave Steamer Cooker Basket",
                url="https://tesco.com/product/MC33333",
                price="£9.99",
                source="Tesco",
            ),
            format_web_search_result(
                title="Ceramic Non-Stick Frying Pan 28cm",
                url="https://johnlewis.com/product/FP44444",
                price="£29.99",
                source="John Lewis",
            ),
            format_web_search_result(
                title="Silicone Spatula Set Heat Resistant",
                url="https://lakeland.co.uk/product/SP55555",
                price="£14.99",
                source="Lakeland",
            ),
            format_web_search_result(
                title="Wooden Cutting Board Set of 4",
                url="https://currys.co.uk/product/CB66666",
                price="£22.99",
                source="Currys",
            ),
            format_web_search_result(
                title="Stainless Steel Measuring Spoons",
                url="https://amazon.co.uk/product/MS77777",
                price="£8.99",
                source="Amazon",
            ),
            format_web_search_result(
                title="Glass Mixing Bowl Set with Lids",
                url="https://tesco.com/product/MB88888",
                price="£16.99",
                source="Tesco",
            ),
        ]

        # Return up to limit results
        return mock_products[:limit]