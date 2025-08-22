"""Pricing fetcher component for eBay Finding API."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from statistics import mean, median
import httpx
from urllib.parse import urlencode

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# eBay Finding API endpoint
EBAY_FINDING_API_URL = "https://svcs.ebay.com/services/search/FindingService/v1"


class PricingFetcher:
    """Fetches sold pricing data from eBay Finding API."""

    def __init__(self):
        """Initialize the pricing fetcher."""
        self.app_id = settings.ebay_app_id
        self._validate_credentials()

    async def fetch_pricing(
        self, upc: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch pricing data for a UPC from eBay sold listings.

        Args:
            upc: The UPC barcode
            metadata: Optional metadata for enhanced searching

        Returns:
            Pricing information including average sold price
        """
        logger.info(f"Fetching pricing data for UPC: {upc}")

        pricing_result = {
            "upc": upc,
            "prices": [],
            "average_price": None,
            "median_price": None,
            "min_price": None,
            "max_price": None,
            "sample_size": 0,
            "currency": "USD",
            "confidence": "low",
            "search_method": None,
            "recommended_price": None,
        }

        # Try different search strategies
        search_strategies = [
            {"method": "upc", "keywords": upc},
        ]

        # Add artist/album search as fallback if metadata available
        if metadata:
            if metadata.get("artist_name") and metadata.get("title"):
                artist = metadata["artist_name"]
                album = metadata["title"]
                search_strategies.append(
                    {"method": "artist_album", "keywords": f"{artist} {album} CD"}
                )

            # Try with just album title
            if metadata.get("title"):
                search_strategies.append(
                    {"method": "album_only", "keywords": f'{metadata["title"]} CD'}
                )

        # Try each search strategy
        for strategy in search_strategies:
            logger.info(
                f"Trying search strategy: {strategy['method']} with keywords: {strategy['keywords']}"
            )

            sold_items = await self._search_completed_items(
                keywords=strategy["keywords"],
                category_id="176984",  # Music CDs category
            )

            if sold_items:
                pricing_result["search_method"] = strategy["method"]
                pricing_result = self._calculate_pricing_stats(
                    sold_items, pricing_result
                )

                # If we found good data, stop searching
                if pricing_result["sample_size"] >= 3:
                    break

        # Set confidence level based on sample size
        if pricing_result["sample_size"] >= 10:
            pricing_result["confidence"] = "high"
        elif pricing_result["sample_size"] >= 5:
            pricing_result["confidence"] = "medium"
        elif pricing_result["sample_size"] > 0:
            pricing_result["confidence"] = "low"
        else:
            pricing_result["confidence"] = "none"

        # Calculate recommended price
        pricing_result = self._calculate_recommended_price(pricing_result)

        avg_price_str = (
            f"{pricing_result['average_price']:.2f}"
            if pricing_result["average_price"]
            else "0.00"
        )
        logger.info(
            f"Pricing analysis complete for UPC {upc}: "
            f"Found {pricing_result['sample_size']} sold items, "
            f"avg price: ${avg_price_str}"
        )

        return pricing_result

    def _validate_credentials(self):
        """Validate eBay credentials and reload from Secret Manager if needed."""
        if not self.app_id and settings.environment.lower() == "production":
            logger.info("eBay App ID missing, attempting to load from Secret Manager")
            try:
                from src.utils.secrets_loader import get_secrets_loader

                loader = get_secrets_loader()
                new_app_id = loader.get_secret("EBAY_APP_ID")
                if new_app_id:
                    settings.ebay_app_id = new_app_id
                    self.app_id = new_app_id
                    logger.info("Successfully loaded eBay App ID from Secret Manager")
            except Exception as e:
                logger.error(f"Failed to load eBay App ID from Secret Manager: {e}")

    async def _search_completed_items(
        self, keywords: str, category_id: Optional[str] = None, retry_count: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search for completed (sold) items on eBay.

        Args:
            keywords: Search keywords
            category_id: Optional eBay category ID to filter results

        Returns:
            List of sold items with pricing information
        """
        params = {
            "OPERATION-NAME": "findCompletedItems",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": self.app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": keywords,
            "itemFilter(0).name": "SoldItemsOnly",
            "itemFilter(0).value": "true",
            "paginationInput.entriesPerPage": "100",
            "paginationInput.pageNumber": "1",
            "sortOrder": "EndTimeSoonest",
        }

        # Add category filter if specified
        if category_id:
            params["categoryId"] = category_id

        # Add condition filter for used items (most CDs are used)
        params["itemFilter(1).name"] = "Condition"
        params["itemFilter(1).value(0)"] = "Used"
        params["itemFilter(1).value(1)"] = "Very Good"
        params["itemFilter(1).value(2)"] = "Good"
        params["itemFilter(1).value(3)"] = "Acceptable"
        params["itemFilter(1).value(4)"] = "Like New"

        # Filter by date range (last 90 days for more relevant pricing)
        # Current date: August 15, 2025
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)  # Look back 90 days from today
        params["itemFilter(2).name"] = "EndTimeFrom"
        params["itemFilter(2).value"] = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        params["itemFilter(3).name"] = "EndTimeTo"
        params["itemFilter(3).value"] = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    EBAY_FINDING_API_URL, params=params, timeout=30.0
                )

                if response.status_code == 500 and retry_count < 2:
                    # Retry on 500 errors with exponential backoff
                    wait_time = (2**retry_count) * 3
                    logger.warning(
                        f"eBay Finding API 500 error, retrying in {wait_time} seconds (attempt {retry_count + 1}/2)"
                    )
                    await asyncio.sleep(wait_time)
                    return await self._search_completed_items(
                        keywords, category_id, retry_count + 1
                    )
                elif response.status_code != 200:
                    # Check if it's an auth issue and try to reload credentials
                    if response.status_code in [401, 403] and retry_count == 0:
                        logger.info("eBay API auth error, reloading credentials")
                        self._validate_credentials()
                        if self.app_id:
                            return await self._search_completed_items(
                                keywords, category_id, retry_count + 1
                            )
                    logger.error(f"eBay Finding API error: {response.status_code}")
                    return []

                data = response.json()

                # Check for API errors
                finding_response = data.get("findCompletedItemsResponse", [{}])[0]

                if finding_response.get("ack", ["Failure"])[0] != "Success":
                    error_msg = (
                        finding_response.get("errorMessage", [{}])[0]
                        .get("error", [{}])[0]
                        .get("message", ["Unknown error"])[0]
                    )
                    logger.error(f"eBay API error: {error_msg}")
                    return []

                # Extract items
                search_result = finding_response.get("searchResult", [{}])[0]
                items = search_result.get("item", [])

                # Parse sold items
                sold_items = []
                for item in items:
                    try:
                        # Extract price
                        selling_status = item.get("sellingStatus", [{}])[0]
                        current_price = selling_status.get("currentPrice", [{}])[0]
                        price_value = float(current_price.get("__value__", 0))
                        currency = current_price.get("@currencyId", "USD")

                        # Extract item details
                        item_info = {
                            "item_id": item.get("itemId", [""])[0],
                            "title": item.get("title", [""])[0],
                            "price": price_value,
                            "currency": currency,
                            "condition": item.get("condition", [{}])[0].get(
                                "conditionDisplayName", [""]
                            )[0],
                            "end_time": item.get("listingInfo", [{}])[0].get(
                                "endTime", [""]
                            )[0],
                            "listing_type": item.get("listingInfo", [{}])[0].get(
                                "listingType", [""]
                            )[0],
                            "url": item.get("viewItemURL", [""])[0],
                        }

                        # Only include items with valid prices
                        if price_value > 0:
                            sold_items.append(item_info)

                    except (KeyError, ValueError, IndexError) as e:
                        logger.debug(f"Error parsing item: {e}")
                        continue

                logger.info(
                    f"Found {len(sold_items)} sold items for keywords: {keywords}"
                )
                return sold_items

        except httpx.TimeoutException:
            logger.error(f"eBay Finding API timeout for keywords: {keywords}")
            return []
        except Exception as e:
            logger.error(f"Error searching eBay for keywords '{keywords}': {e}")
            return []

    def _calculate_pricing_stats(
        self, sold_items: List[Dict[str, Any]], pricing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate pricing statistics from sold items.

        Args:
            sold_items: List of sold items with prices
            pricing_result: Pricing result dictionary to update

        Returns:
            Updated pricing result with statistics
        """
        if not sold_items:
            return pricing_result

        # Extract prices
        prices = [item["price"] for item in sold_items if item["price"] > 0]

        if not prices:
            return pricing_result

        # Remove outliers (prices that are too high or too low)
        # Using IQR method
        if len(prices) >= 4:
            sorted_prices = sorted(prices)
            q1_index = len(sorted_prices) // 4
            q3_index = 3 * len(sorted_prices) // 4
            q1 = sorted_prices[q1_index]
            q3 = sorted_prices[q3_index]
            iqr = q3 - q1

            # Filter outliers
            lower_bound = max(1.0, q1 - 1.5 * iqr)  # Minimum $1
            upper_bound = min(100.0, q3 + 1.5 * iqr)  # Maximum $100 for CDs

            filtered_prices = [p for p in prices if lower_bound <= p <= upper_bound]

            # Use filtered prices if we still have enough data
            if len(filtered_prices) >= 3:
                prices = filtered_prices
                logger.debug(
                    f"Filtered outliers: kept {len(prices)} of {len(sold_items)} prices"
                )

        # Calculate statistics
        pricing_result["prices"] = prices
        pricing_result["sample_size"] = len(prices)
        pricing_result["average_price"] = mean(prices)
        pricing_result["median_price"] = median(prices)
        pricing_result["min_price"] = min(prices)
        pricing_result["max_price"] = max(prices)

        # Add sample of actual sold listings for reference
        pricing_result["sample_listings"] = [
            {
                "title": (
                    item["title"][:50] + "..."
                    if len(item["title"]) > 50
                    else item["title"]
                ),
                "price": item["price"],
                "condition": item["condition"],
                "end_time": item["end_time"],
                "url": item["url"],
            }
            for item in sold_items[:5]  # Keep top 5 as examples
        ]

        return pricing_result

    def _calculate_recommended_price(
        self, pricing_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate recommended listing price based on statistics.

        Args:
            pricing_result: Pricing result with statistics

        Returns:
            Updated pricing result with recommendation
        """
        if pricing_result["sample_size"] == 0:
            # No data - suggest a default price
            pricing_result["recommended_price"] = 9.99
            pricing_result["price_strategy"] = "default"
            pricing_result["recommendation_reason"] = (
                "No sold data found, using default price"
            )

        elif pricing_result["confidence"] == "high":
            # High confidence - use slightly below average for competitive pricing
            pricing_result["recommended_price"] = round(
                pricing_result["average_price"] * 0.95, 2
            )
            pricing_result["price_strategy"] = "competitive"
            pricing_result["recommendation_reason"] = (
                f"Based on {pricing_result['sample_size']} recent sales, priced competitively at 95% of average"
            )

        elif pricing_result["confidence"] == "medium":
            # Medium confidence - use median as it's more robust
            pricing_result["recommended_price"] = round(
                pricing_result["median_price"], 2
            )
            pricing_result["price_strategy"] = "median"
            pricing_result["recommendation_reason"] = (
                f"Based on {pricing_result['sample_size']} recent sales, using median price"
            )

        else:
            # Low confidence - be conservative
            if pricing_result["median_price"]:
                pricing_result["recommended_price"] = round(
                    pricing_result["median_price"] * 0.9, 2
                )
                pricing_result["price_strategy"] = "conservative"
                pricing_result["recommendation_reason"] = (
                    f"Limited data ({pricing_result['sample_size']} sales), using conservative pricing"
                )
            else:
                pricing_result["recommended_price"] = 9.99
                pricing_result["price_strategy"] = "default"
                pricing_result["recommendation_reason"] = (
                    "Insufficient data, using default price"
                )

        # Ensure price is reasonable
        if pricing_result["recommended_price"]:
            # Minimum $3.99 (to cover shipping costs)
            pricing_result["recommended_price"] = max(
                3.99, pricing_result["recommended_price"]
            )
            # Maximum $49.99 (reasonable for most CDs)
            pricing_result["recommended_price"] = min(
                49.99, pricing_result["recommended_price"]
            )

        return pricing_result


# Global pricing fetcher instance
_pricing_fetcher = None


def get_pricing_fetcher() -> PricingFetcher:
    """Get the global pricing fetcher instance."""
    global _pricing_fetcher
    if _pricing_fetcher is None:
        _pricing_fetcher = PricingFetcher()
    return _pricing_fetcher
