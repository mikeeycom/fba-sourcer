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

        In production, this would call a real search API that also resolves
        each product to its matching Amazon ASIN (e.g. by UPC/EAN lookup).
        Until that exists (Phase 4), this mock uses real, verified UK ASINs
        so the rest of the pipeline (keepa_query, calculate_roi,
        submit_leads) can be exercised end-to-end without the agent having
        to invent ASIN data. Titles/prices/sources here are placeholders -
        only the ASINs are real.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of product dicts with title, url, price, source, asin
        """
        mock_products = [
            format_web_search_result(
                title="Kitchen Gadget - Candidate 1",
                url="https://johnlewis.com/product/CAND1",
                price="£18.99",
                source="John Lewis",
                asin="B07W5JKMNV",
            ),
            format_web_search_result(
                title="Kitchen Gadget - Candidate 2",
                url="https://currys.co.uk/product/CAND2",
                price="£22.99",
                source="Currys",
                asin="B0FL7QLH89",
            ),
            format_web_search_result(
                title="Kitchen Gadget - Candidate 3",
                url="https://lakeland.co.uk/product/CAND3",
                price="£14.99",
                source="Lakeland",
                asin="B0D2QWGF9S",
            ),
            format_web_search_result(
                title="Kitchen Gadget - Candidate 4",
                url="https://tesco.com/product/CAND4",
                price="£12.99",
                source="Tesco",
                asin="B0CTKR1941",
            ),
        ]

        # Return up to limit results
        return mock_products[:limit]