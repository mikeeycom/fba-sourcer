"""Amazon SP-API client for real Product Fees data (referral + FBA fulfillment fees).

Keepa gives us price/sales history but not fee calculations - this client
fills that gap using Amazon's own Selling Partner API (SP-API) Product Fees
endpoint, so ROI can be calculated net of what Amazon actually charges.
"""

import time

import httpx

from app.config import settings
from app.utils.exceptions import APIError
from app.utils.logger import get_logger

logger = get_logger(__name__)

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

# Covers UK/EU/IN marketplaces. Amazon has moved marketplace groupings
# between regional SP-API endpoints before - verify against current docs
# if requests start failing with an unexpected 4xx.
SP_API_BASE_URL_EU = "https://sellingpartnerapi-eu.amazon.com"

# Well-known constant for amazon.co.uk, same precedent as KeepaClient's
# KEEPA_DOMAIN_UK - this codebase is UK-only for now.
MARKETPLACE_ID_UK = "A1F83G8C2ARO7P"

FEES_API_PATH = "/products/fees/v0/items/{asin}/feesEstimate"

# LWA access tokens are valid ~3600s. Refresh this many seconds early to
# absorb clock skew and in-flight request latency, rather than cutting it
# exactly to zero.
TOKEN_EXPIRY_BUFFER_SECONDS = 300

# SP-API's fees endpoint allows 1 request/second with a burst of 2 - far
# less punishing than Keepa's 1 token/minute, but a short cooldown still
# avoids hammering a transient 429/500 immediately.
FAILURE_COOLDOWN_SECONDS = 60


class SpApiClient:
    """Client for Amazon's Selling Partner API Product Fees endpoint.

    Two layers of in-memory caching, both for the life of the process:
    - The LWA access token is a credential, not per-product data - it's
      refreshed automatically when close to expiry rather than on every
      call, since re-exchanging it every request wastes a round trip.
    - Fee estimates are cached per (asin, price) - not per asin alone,
      since referral fees scale with price and caching by ASIN only would
      silently serve a stale number for a different price. Failed lookups
      are cooled down for a short window rather than retried immediately.
    """

    def __init__(
        self,
        client_id: str = None,
        client_secret: str = None,
        refresh_token: str = None,
        timeout: float = 15.0,
    ):
        """Initialize SP-API client.

        Args:
            client_id: LWA client ID. If None, uses SP_API_CLIENT_ID from env
            client_secret: LWA client secret. If None, uses SP_API_CLIENT_SECRET
            refresh_token: LWA refresh token. If None, uses SP_API_REFRESH_TOKEN
            timeout: Request timeout in seconds
        """
        self.client_id = client_id or settings.sp_api_client_id
        self.client_secret = client_secret or settings.sp_api_client_secret
        self.refresh_token = refresh_token or settings.sp_api_refresh_token

        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError(
                "SP_API_CLIENT_ID, SP_API_CLIENT_SECRET, and SP_API_REFRESH_TOKEN "
                "must all be set in environment"
            )

        self.timeout = timeout
        self._result_cache: dict[str, dict] = {}
        self._failure_cooldown: dict[str, float] = {}
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        logger.info("SP-API client initialized")

    def get_fees_estimate(self, asin: str, price: float) -> dict:
        """Get Amazon's fee estimate for a product, using the cache.

        Serves a cached result if this exact (asin, price) succeeded
        before. If it failed recently, refuses to retry until the
        cooldown window has passed.

        Args:
            asin: Amazon Standard Identification Number
            price: Price to estimate fees at (GBP)

        Returns:
            Dict with asin, referral_fee, fulfillment_fee, total_fees

        Raises:
            APIError: If the request fails or this (asin, price) is on
                cooldown after a recent failure
        """
        cache_key = f"{asin}:{price}"

        if cache_key in self._result_cache:
            logger.info("SP-API fees cache hit", extra={"asin": asin, "price": price})
            return self._result_cache[cache_key]

        failed_at = self._failure_cooldown.get(cache_key)
        if failed_at is not None:
            elapsed = time.time() - failed_at
            if elapsed < FAILURE_COOLDOWN_SECONDS:
                remaining = round(FAILURE_COOLDOWN_SECONDS - elapsed)
                logger.warning(
                    "SP-API cooldown active, skipping call",
                    extra={"asin": asin, "price": price, "remaining_seconds": remaining},
                )
                raise APIError(
                    f"Fee estimate for ASIN {asin} at £{price} failed recently and "
                    f"is on cooldown for {remaining}s. Do not retry it. Proceed using "
                    "calculate_roi without the fees parameter for this product, or "
                    "submit leads using only those already validated."
                )
            # Cooldown has passed - clear it and allow a fresh attempt.
            del self._failure_cooldown[cache_key]

        try:
            result = self._get_fees_estimate_uncached(asin, price)
            self._result_cache[cache_key] = result
            return result
        except APIError:
            self._failure_cooldown[cache_key] = time.time()
            raise

    def _get_access_token(self) -> str:
        """Return a valid LWA access token, refreshing it if near expiry.

        Returns:
            A valid access token string

        Raises:
            APIError: If the token refresh request fails
        """
        if self._access_token is not None and time.time() < self._token_expires_at:
            return self._access_token

        return self._refresh_access_token_uncached()

    def _refresh_access_token_uncached(self) -> str:
        """Exchange the refresh token for a new LWA access token.

        Never logs access_token or refresh_token values - these are
        credentials, and the structured JSON logger would otherwise ship
        them to stdout/log aggregation unfiltered.

        Returns:
            The new access token string

        Raises:
            APIError: If the token exchange fails
        """
        start_time = time.time()

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            logger.info("SP-API LWA token refresh")

            # LWA's token endpoint expects form-encoded data, not JSON -
            # httpx does this automatically when passed via `data=`.
            response = httpx.post(LWA_TOKEN_URL, data=data, timeout=self.timeout)
            response.raise_for_status()
            token_data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            access_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in")
            if not access_token or not expires_in:
                logger.error(
                    "LWA token response missing expected fields",
                    extra={"latency_ms": latency_ms, "fields": list(token_data.keys())},
                )
                raise APIError("LWA token response missing access_token/expires_in")

            self._access_token = access_token
            self._token_expires_at = time.time() + expires_in - TOKEN_EXPIRY_BUFFER_SECONDS

            logger.info(
                "SP-API LWA token refresh success",
                extra={"latency_ms": latency_ms, "expires_in": expires_in},
            )

            return access_token

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "LWA token refresh timeout",
                extra={"latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"LWA token refresh timeout: {str(e)}") from e

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "LWA token refresh error",
                extra={
                    "latency_ms": latency_ms,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise APIError(f"LWA token refresh error: {str(e)}") from e

        except httpx.RequestError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "LWA token refresh connection error",
                extra={"latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"LWA token refresh connection error: {str(e)}") from e

    def _get_fees_estimate_uncached(self, asin: str, price: float) -> dict:
        """Call SP-API's Product Fees endpoint directly, bypassing the cache.

        Args:
            asin: Amazon Standard Identification Number
            price: Price to estimate fees at (GBP)

        Returns:
            Dict with asin, referral_fee, fulfillment_fee, total_fees

        Raises:
            APIError: If the request fails or Amazon reports a body-level
                failure (SP-API can return HTTP 200 with a failure status
                embedded in the response body)
        """
        start_time = time.time()

        access_token = self._get_access_token()

        url = f"{SP_API_BASE_URL_EU}{FEES_API_PATH.format(asin=asin)}"
        headers = {
            "x-amz-access-token": access_token,
            "content-type": "application/json",
        }
        body = {
            "FeesEstimateRequest": {
                "MarketplaceId": MARKETPLACE_ID_UK,
                "IsAmazonFulfilled": True,
                # Currency tied explicitly to MARKETPLACE_ID_UK - if this
                # client ever supports other marketplaces, both need to
                # change together.
                "PriceToEstimateFees": {
                    "ListingPrice": {"CurrencyCode": "GBP", "Amount": price}
                },
                "Identifier": asin,
            }
        }

        try:
            logger.info("SP-API fees call", extra={"asin": asin, "price": price})

            response = httpx.post(url, headers=headers, json=body, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            result = self._parse_fees_estimate(data)

            logger.info(
                "SP-API fees success",
                extra={
                    "asin": asin,
                    "price": price,
                    "latency_ms": latency_ms,
                    "total_fees": result["total_fees"],
                },
            )

            return result

        except httpx.TimeoutException as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "SP-API fees timeout",
                extra={"asin": asin, "price": price, "latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"SP-API fees timeout: {str(e)}") from e

        except httpx.HTTPStatusError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "SP-API fees error",
                extra={
                    "asin": asin,
                    "price": price,
                    "latency_ms": latency_ms,
                    "status_code": e.response.status_code,
                    "error": str(e),
                },
            )
            raise APIError(f"SP-API fees error: {str(e)}") from e

        except httpx.RequestError as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "SP-API fees connection error",
                extra={"asin": asin, "price": price, "latency_ms": latency_ms, "error": str(e)},
            )
            raise APIError(f"SP-API fees connection error: {str(e)}") from e

    def _parse_fees_estimate(self, data: dict) -> dict:
        """Extract fee fields from a Product Fees API response.

        SP-API's fees endpoint can return HTTP 200 with a body-level
        failure (Status != "Success") rather than an HTTP error status -
        this must be checked explicitly, not assumed from a 200 response.

        Args:
            data: Raw JSON response from the fees endpoint

        Returns:
            Dict with asin, referral_fee, fulfillment_fee, total_fees

        Raises:
            APIError: If the response reports a body-level failure
        """
        result = (data or {}).get("FeesEstimateResult") or {}
        status = result.get("Status")

        if status != "Success":
            error_list = result.get("FeesEstimateErrorList") or data.get("errors") or []
            raise APIError(f"SP-API fees estimate failed (status={status}): {error_list}")

        estimate = result.get("FeesEstimate") or {}
        identifier = result.get("FeesEstimateIdentifier") or {}

        total_fees = self._safe_amount(estimate.get("TotalFeesEstimate"))

        referral_fee = None
        fulfillment_fee = None
        for detail in estimate.get("FeeDetailList") or []:
            fee_type = detail.get("FeeType")
            amount = self._safe_amount(detail.get("FeeAmount"))
            if fee_type == "ReferralFee":
                referral_fee = amount
            elif fee_type == "FBAFees":
                fulfillment_fee = amount

        return {
            "asin": identifier.get("IdValue"),
            "referral_fee": referral_fee,
            "fulfillment_fee": fulfillment_fee,
            "total_fees": total_fees,
        }

    @staticmethod
    def _safe_amount(fee_amount: dict) -> float | None:
        """Extract a money Amount from a Fee-shaped dict, or None if absent."""
        if not fee_amount:
            return None
        amount = fee_amount.get("Amount")
        return float(amount) if amount is not None else None
