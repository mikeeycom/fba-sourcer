"""Keepa API client for Amazon product sales and price data."""

import json
import time

import httpx

from app.config import settings
from app.utils.exceptions import APIError
from app.utils.logger import get_logger

logger = get_logger(__name__)

KEEPA_BASE_URL = "https://api.keepa.com"
KEEPA_DOMAIN_UK = 2  # Keepa domain ID for amazon.co.uk

# Indices into Keepa's "stats.current" / "stats.avgNN" arrays (Keepa CSV Types).
# See: https://keepa.com/#!discuss/t/product-object/116
STAT_IDX_AMAZON_PRICE = 0
STAT_IDX_NEW_FBA_PRICE = 10
STAT_IDX_COUNT_NEW = 11
STAT_IDX_RATING = 16

# Keepa uses negative sentinels (-1, -2) for "no data available" in stats
# arrays. Any negative value should be treated as missing data.

# Keepa's token bucket can refill as slowly as 1 token/minute depending on
# plan. Retrying a just-failed ASIN immediately is guaranteed to fail again,
# so failures are cached for this long before a retry is allowed.
FAILURE_COOLDOWN_SECONDS = 90

# Fixed "OA" (online arbitrage) sourcing filters for the Product Finder
# search - Michael's manual Keepa filter checklist, encoded as constants
# rather than exposed as tool params, so the agent can't loosen them.
FINDER_MAX_SALES_RANK = 50_000
FINDER_MIN_BUYBOX_PRICE_PENCE = 700  # £7.00
# Amazon itself out of stock most of the time (i.e. little/no direct Amazon
# competition on the listing). Default threshold - not confirmed against
# Keepa's own "tick the out of stock box" UI preset, tune after live results.
FINDER_MIN_AMAZON_OOS_PCT = 80
FINDER_MIN_OFFER_COUNT_365D_AVG = 2
# Negative = a drop. -1 means "offer count fell by at least 1% over 90 days".
FINDER_MAX_OFFER_COUNT_90D_DELTA_PCT = -1
FINDER_MIN_MONTHLY_SOLD = 50
FINDER_MIN_RATING = 40  # Keepa's rating scale is x10 (40 == 4.0 stars)

# Keepa root category IDs for amazon.co.uk (domain=2), looked up live via
# Keepa's /category endpoint - not guessed.
CATEGORY_MAP = {
    "baby products": "59624031",
    "beauty": "117332031",
    "computers and accessories": "340831031",
    "diy and tools": "79903031",
    "grocery": "340834031",
    "health and personal care": "65801031",
    "pet supplies": "340840031",
    "toys and games": "468292",
}


class KeepaClient:
    """Client for querying Keepa's Amazon product data API.

    Keepa tracks Amazon price and sales-rank history, and provides an
    estimated monthly sold units figure ("monthlySold") for eligible products.

    Caches results in memory for the life of the process: successful
    lookups are cached indefinitely (product data doesn't change fast
    enough to matter here), and failures are cached for a cooldown window
    so a rate-limited ASIN isn't retried before tokens could plausibly
    have refilled.
    """

    def __init__(self, api_key: str = None, timeout: float = 15.0):
        """Initialize Keepa client.

        Args:
            api_key: Keepa API key. If None, uses KEEPA_API_KEY from env
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or settings.keepa_api_key
        if not self.api_key:
            raise ValueError("KEEPA_API_KEY not set in environment")

        self.timeout = timeout
        self._result_cache: dict[str, dict] = {}
        self._failure_cooldown: dict[str, float] = {}
        logger.info("Keepa client initialized")

    def query_product(self, asin: str, include_history: bool = False) -> dict:
        """Query Keepa for a product's sales and price data, using the cache.

        Serves a cached result if this ASIN succeeded before. If it failed
        recently, refuses to retry until the cooldown window has passed
        rather than wasting a call that's certain to hit the rate limit
        again.

        Args:
            asin: Amazon Standard Identification Number
            include_history: Whether to request full price/rank history arrays

        Returns:
            Dict with asin, title, monthly_sales, current_price, avg_price, rating

        Raises:
            APIError: If the Keepa request fails, the ASIN isn't found, or
                this ASIN is still in its post-failure cooldown window
        """
        if asin in self._result_cache:
            logger.info("Keepa cache hit", extra={"asin": asin})
            return self._result_cache[asin]

        failed_at = self._failure_cooldown.get(asin)
        if failed_at is not None:
            elapsed = time.time() - failed_at
            if elapsed < FAILURE_COOLDOWN_SECONDS:
                remaining = round(FAILURE_COOLDOWN_SECONDS - elapsed)
                logger.warning(
                    "Keepa cooldown active, skipping call",
                    extra={"asin": asin, "remaining_seconds": remaining},
                )
                raise APIError(
                    f"ASIN {asin} failed recently and is on cooldown for "
                    f"{remaining}s. Do not retry it. If you already have "
                    "some validated leads, proceed with submit_leads using "
                    "those, even if fewer than 5-7, rather than searching "
                    "for more."
                )
            # Cooldown has passed - clear it and allow a fresh attempt.
            del self._failure_cooldown[asin]

        try:
            result = self._query_product_uncached(asin, include_history)
            self._result_cache[asin] = result
            return result
        except APIError:
            self._failure_cooldown[asin] = time.time()
            raise

    def find_products(self, category: str, limit: int = 20) -> list[str]:
        """Search Keepa's Product Finder for candidate ASINs.

        Applies Michael's fixed "OA" sourcing filters (sales rank, buy box
        price, offer count, rating, monthly sales - see the FINDER_*
        constants) within the given category. Unlike query_product, this
        isn't cached - it's a fresh search each call, not a per-ASIN lookup.

        Args:
            category: One of the keys in CATEGORY_MAP
            limit: Max ASINs to return (capped at 50, Keepa's page size)

        Returns:
            List of ASIN strings matching all the fixed filter criteria

        Raises:
            APIError: If the category is unrecognized or the Keepa request fails
        """
        category_id = CATEGORY_MAP.get(category)
        if category_id is None:
            raise APIError(
                f"Unknown category: {category!r}. Must be one of: "
                f"{', '.join(CATEGORY_MAP)}"
            )

        limit = min(limit, 50)
        # No perPage/page sent - Keepa enforces a minimum page size of 50
        # (smaller values 400), so we just take Keepa's default-sized page
        # and trim to `limit` ourselves after the fact.
        selection = {
            "current_SALES_lte": FINDER_MAX_SALES_RANK,
            "current_BUY_BOX_SHIPPING_gte": FINDER_MIN_BUYBOX_PRICE_PENCE,
            "outOfStockPercentage90_gte": FINDER_MIN_AMAZON_OOS_PCT,
            "rootCategory": [category_id],
            "avg365_COUNT_NEW_gte": FINDER_MIN_OFFER_COUNT_365D_AVG,
            "deltaPercent90_COUNT_NEW_lte": FINDER_MAX_OFFER_COUNT_90D_DELTA_PCT,
            "monthlySold_gte": FINDER_MIN_MONTHLY_SOLD,
            "current_RATING_gte": FINDER_MIN_RATING,
            "productType": ["0"],  # standard products only
        }

        start_time = time.time()
        params = {
            "key": self.api_key,
            "domain": KEEPA_DOMAIN_UK,
            "selection": json.dumps(selection),
        }

        try:
            logger.info("Keepa product finder call", extra={"category": category})

            response = httpx.get(
                f"{KEEPA_BASE_URL}/query", params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000
            asins = data.get("asinList") or []

            logger.info(
                "Keepa product finder success",
                extra={
                    "category": category,
                    "latency_ms": latency_ms,
                    "result_count": len(asins),
                    "tokens_left": data.get("tokensLeft"),
                },
            )

            return asins[:limit]

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Keepa product finder timeout",
                extra={"category": category, "latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"Keepa API timeout: {str(e)}") from e

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Keepa product finder error",
                extra={
                    "category": category,
                    "latency_ms": latency_ms,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise APIError(f"Keepa API error: {str(e)}") from e

        except httpx.RequestError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Keepa product finder connection error",
                extra={"category": category, "latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"Keepa API connection error: {str(e)}") from e

    def _query_product_uncached(self, asin: str, include_history: bool = False) -> dict:
        """Query Keepa's /product endpoint directly, bypassing the cache.

        Args:
            asin: Amazon Standard Identification Number
            include_history: Whether to request full price/rank history arrays

        Returns:
            Dict with asin, title, monthly_sales, current_price, avg_price, rating

        Raises:
            APIError: If the Keepa request fails or the ASIN isn't found
        """
        start_time = time.time()

        params = {
            "key": self.api_key,
            "domain": KEEPA_DOMAIN_UK,
            "asin": asin,
            "stats": 180,  # 180-day window used for average price stats
            "history": 1 if include_history else 0,
            # Required for Keepa to populate stats.buyBoxPrice - without this,
            # buy box fields are omitted entirely (not just empty).
            "buybox": 1,
        }

        try:
            logger.info("Keepa API call", extra={"asin": asin})

            response = httpx.get(
                f"{KEEPA_BASE_URL}/product", params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            products = data.get("products") or []
            if not products:
                logger.error(
                    "Keepa ASIN not found",
                    extra={"asin": asin, "latency_ms": latency_ms},
                )
                raise APIError(f"Keepa returned no data for ASIN: {asin}")

            result = self._parse_product(products[0])

            logger.info(
                "Keepa API success",
                extra={
                    "asin": asin,
                    "latency_ms": latency_ms,
                    "tokens_left": data.get("tokensLeft"),
                    "monthly_sales": result["monthly_sales"],
                },
            )

            return result

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Keepa API timeout",
                extra={"asin": asin, "latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"Keepa API timeout: {str(e)}") from e

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Keepa API error",
                extra={
                    "asin": asin,
                    "latency_ms": latency_ms,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise APIError(f"Keepa API error: {str(e)}") from e

        except httpx.RequestError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Keepa API connection error",
                extra={"asin": asin, "latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"Keepa API connection error: {str(e)}") from e

    def _parse_product(self, product: dict) -> dict:
        """Extract the fields we care about from a Keepa product object.

        Keepa prices are in pence (GBP domain) and ratings are scaled by 10.

        Args:
            product: Raw product dict from Keepa's response

        Returns:
            Dict with asin, title, monthly_sales, current_price, avg_price, rating
        """
        stats = product.get("stats") or {}
        current = stats.get("current") or []
        avg180 = stats.get("avg180") or []

        # Keepa provides a direct estimated monthly sold units for eligible
        # products. Falls back to 0 when Keepa has no estimate (new/low-data
        # listings) rather than guessing.
        monthly_sales = product.get("monthlySold") or 0

        return {
            "asin": product.get("asin"),
            "title": product.get("title"),
            "monthly_sales": monthly_sales,
            "current_price": self._extract_current_price(stats, current),
            "avg_price": self._extract_price(avg180),
            "rating": self._extract_rating(current),
        }

    def _extract_current_price(self, stats: dict, current: list) -> float | None:
        """Get the best available "what a buyer pays right now" price.

        Prefers stats.buyBoxPrice (the actual winning offer price), since
        that's the figure a real customer would pay. Falls back to the
        Amazon-sold price, then New FBA price, from the current stats array.
        Returns None if no live offer is available at all (e.g. a
        temporarily unqualified buy box / out of stock).

        Args:
            stats: The product's "stats" dict from Keepa
            current: stats.current array

        Returns:
            Price in GBP, or None if unavailable
        """
        buy_box_price = stats.get("buyBoxPrice")
        if buy_box_price is not None and buy_box_price >= 0:
            return round(buy_box_price / 100, 2)

        return self._extract_price(current)

    def _extract_price(self, price_stats: list) -> float | None:
        """Get the best available price from a Keepa stats array.

        Prefers the Amazon-sold price, falls back to New FBA price.
        Keepa returns a negative sentinel when no data is available, and
        prices in pence.

        Args:
            price_stats: A Keepa stats array (e.g. stats.current or stats.avg180)

        Returns:
            Price in GBP, or None if unavailable
        """
        if not price_stats:
            return None

        amazon_price = self._safe_index(price_stats, STAT_IDX_AMAZON_PRICE)
        if amazon_price is not None and amazon_price >= 0:
            return round(amazon_price / 100, 2)

        fba_price = self._safe_index(price_stats, STAT_IDX_NEW_FBA_PRICE)
        if fba_price is not None and fba_price >= 0:
            return round(fba_price / 100, 2)

        return None

    def _extract_rating(self, current: list) -> float | None:
        """Get product rating from Keepa's current stats array.

        Keepa scales ratings by 10 (e.g. 45 == 4.5 stars).

        Args:
            current: stats.current array

        Returns:
            Rating out of 5, or None if unavailable
        """
        rating = self._safe_index(current, STAT_IDX_RATING)
        if rating is None or rating < 0:
            return None
        return round(rating / 10, 1)

    @staticmethod
    def _safe_index(array: list, index: int):
        """Return array[index] or None if the index is out of bounds."""
        if index < len(array):
            return array[index]
        return None
