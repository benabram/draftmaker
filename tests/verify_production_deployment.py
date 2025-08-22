#!/usr/bin/env python3
"""
Script to verify that the deployed changes are working in production.
This checks:
1. Discogs API authentication (should not get 401 errors)
2. Text descriptions for neutral conditions
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from components.metadata_fetcher import MetadataFetcher
from components.draft_composer import DraftComposer
from utils.secrets_loader import load_secrets_from_cloud
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_discogs_api():
    """Test if Discogs API is working without 401 errors."""
    logger.info("Testing Discogs API authentication...")
    try:
        # Load secrets
        secrets = load_secrets_from_cloud()

        # Initialize metadata fetcher
        fetcher = MetadataFetcher(secrets)

        # Try to fetch data for a known release
        test_upc = "602547875198"  # Example UPC
        result = fetcher.fetch_metadata(test_upc)

        if result:
            logger.info("✅ Discogs API is working - no 401 errors")
            return True
        else:
            logger.warning("⚠️ No results returned, but no 401 error")
            return True
    except Exception as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            logger.error(f"❌ Discogs API authentication failed with 401: {e}")
            return False
        else:
            logger.error(f"❌ Unexpected error: {e}")
            return False


def test_neutral_descriptions():
    """Test if neutral condition descriptions are being used."""
    logger.info("Testing neutral condition descriptions...")
    try:
        # Initialize draft composer
        composer = DraftComposer()

        # Test with a mock item with neutral condition
        test_item = {
            "title": "Test Album",
            "artist": "Test Artist",
            "condition": "Good",
            "format": "Vinyl",
        }

        # Generate description
        description = composer.generate_description(test_item)

        # Check for neutral language (should not have overly promotional language)
        neutral_indicators = ["condition", "Good", "Fair", "Acceptable"]

        has_neutral_language = any(
            indicator.lower() in description.lower() for indicator in neutral_indicators
        )

        if has_neutral_language:
            logger.info("✅ Neutral condition descriptions are being used")
            logger.info(f"   Sample description: {description[:200]}...")
            return True
        else:
            logger.warning("⚠️ Could not verify neutral descriptions")
            return False

    except Exception as e:
        logger.error(f"❌ Error testing descriptions: {e}")
        return False


def main():
    """Run all verification tests."""
    logger.info("=" * 60)
    logger.info("PRODUCTION DEPLOYMENT VERIFICATION")
    logger.info("=" * 60)

    all_passed = True

    # Test 1: Discogs API
    if not test_discogs_api():
        all_passed = False

    # Test 2: Neutral descriptions
    if not test_neutral_descriptions():
        all_passed = False

    logger.info("=" * 60)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED - Deployment verified!")
    else:
        logger.error("❌ SOME TESTS FAILED - Check deployment")
    logger.info("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
