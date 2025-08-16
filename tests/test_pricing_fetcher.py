#!/usr/bin/env python3
"""Test the pricing fetcher component."""

import sys
import os
import asyncio
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.components.metadata_fetcher import get_metadata_fetcher
from src.components.pricing_fetcher import get_pricing_fetcher
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_pricing_fetch(upc: str):
    """
    Test pricing fetching for a specific UPC.
    
    Args:
        upc: The UPC to test
    """
    print(f"\n{'='*60}")
    print(f"Testing pricing fetch for UPC: {upc}")
    print('='*60)
    
    # First fetch metadata for better search context
    metadata_fetcher = get_metadata_fetcher()
    pricing_fetcher = get_pricing_fetcher()
    
    try:
        # Get metadata
        print("\nFetching metadata first for context...")
        metadata = await metadata_fetcher.fetch_metadata(upc)
        
        if metadata:
            print(f"  Album: {metadata.get('title', 'N/A')} by {metadata.get('artist_name', 'N/A')}")
        else:
            print("  No metadata found, will search with UPC only")
            metadata = None
        
        # Fetch pricing
        print("\n💰 Fetching pricing data...")
        pricing_result = await pricing_fetcher.fetch_pricing(upc, metadata)
        
        # Display results
        print(f"\n📊 Pricing Analysis:")
        print(f"  Sample Size: {pricing_result['sample_size']} sold items")
        print(f"  Confidence: {pricing_result['confidence'].upper()}")
        print(f"  Search Method: {pricing_result['search_method'] or 'N/A'}")
        
        if pricing_result['sample_size'] > 0:
            print(f"\n💵 Price Statistics:")
            print(f"  Average Price: ${pricing_result['average_price']:.2f}")
            print(f"  Median Price: ${pricing_result['median_price']:.2f}")
            print(f"  Price Range: ${pricing_result['min_price']:.2f} - ${pricing_result['max_price']:.2f}")
            
            # Show sample listings
            if pricing_result.get('sample_listings'):
                print(f"\n📝 Sample Sold Listings:")
                for i, listing in enumerate(pricing_result['sample_listings'][:3], 1):
                    print(f"  {i}. {listing['title']}")
                    print(f"     Price: ${listing['price']:.2f} | Condition: {listing['condition']}")
        else:
            print("\n❌ No sold data found")
        
        # Show recommendation
        print(f"\n🎯 Pricing Recommendation:")
        print(f"  Recommended Price: ${pricing_result['recommended_price']:.2f}")
        print(f"  Strategy: {pricing_result.get('price_strategy', 'N/A')}")
        print(f"  Reason: {pricing_result.get('recommendation_reason', 'N/A')}")
        
        return pricing_result['sample_size'] > 0 or pricing_result['recommended_price'] is not None
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run pricing fetcher tests."""
    print("\n" + "="*60)
    print("PRICING FETCHER TEST")
    print("="*60)
    
    # Test with different UPCs - some might have more sold data than others
    test_cases = [
        settings.test_upc_codes[0],  # First test UPC
        settings.test_upc_codes[1],  # Second test UPC (likely more popular)
        settings.test_upc_codes[7],  # Different test UPC (might have different results)
    ]
    
    print(f"\nTesting with {len(test_cases)} UPC codes...")
    print("Note: Results depend on actual eBay sold listings data")
    
    results = []
    for upc in test_cases:
        result = await test_pricing_fetch(upc)
        results.append(result)
        
        # Add delay between requests to respect rate limits
        if upc != test_cases[-1]:
            print("\n⏳ Waiting before next request...")
            await asyncio.sleep(1)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    successful = sum(results)
    total = len(results)
    
    print(f"\nResults: {successful}/{total} successful")
    print("Note: 'Successful' means the component worked correctly,")
    print("      even if no sold data was found (default pricing is used)")
    
    if successful == total:
        print("✅ All tests passed!")
    else:
        print(f"⚠️  {total - successful} test(s) failed")
    
    return successful == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        sys.exit(1)
