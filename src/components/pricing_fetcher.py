"""Pricing component with fixed pricing for CDs."""

from typing import Dict, Any, Optional
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PricingFetcher:
    """Provides fixed pricing for CD listings."""

    def __init__(self):
        """Initialize the pricing fetcher."""
        # Fixed price for all CDs
        self.fixed_price = 9.99

    async def fetch_pricing(
        self, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Return fixed pricing for CD listings.

        Args:
            metadata: Optional metadata (not used for fixed pricing)

        Returns:
            Fixed pricing information
        """
        upc = metadata.get("upc") if metadata else "Unknown"
        logger.info(f"Using fixed pricing for UPC: {upc}")

        pricing_result = {
            "upc": upc,
            "recommended_price": self.fixed_price,
            "average_price": self.fixed_price,
            "median_price": self.fixed_price,
            "min_price": self.fixed_price,
            "max_price": self.fixed_price,
            "prices": [self.fixed_price],
            "sample_size": 1,
            "currency": "USD",
            "confidence": "fixed",
            "price_strategy": "fixed",
            "search_method": "fixed_pricing",
            "recommendation_reason": "Fixed pricing model - all CDs priced at $9.99",
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Fixed pricing set at ${self.fixed_price:.2f} for UPC: {upc}")

        return pricing_result



# Global pricing fetcher instance
_pricing_fetcher = None


def get_pricing_fetcher() -> PricingFetcher:
    """Get the global pricing fetcher instance."""
    global _pricing_fetcher
    if _pricing_fetcher is None:
        _pricing_fetcher = PricingFetcher()
    return _pricing_fetcher
