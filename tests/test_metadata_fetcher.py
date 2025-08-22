#!/usr/bin/env python3
"""Test the metadata fetcher component."""

import sys
import os
import asyncio
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.components.metadata_fetcher import get_metadata_fetcher
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_metadata_fetch(upc: str):
    """
    Test metadata fetching for a specific UPC.

    Args:
        upc: The UPC to test
    """
    print(f"\n{'='*60}")
    print(f"Testing metadata fetch for UPC: {upc}")
    print("=" * 60)

    fetcher = get_metadata_fetcher()

    try:
        # Fetch metadata
        print("\nFetching metadata...")
        metadata = await fetcher.fetch_metadata(upc)

        if not metadata:
            print("❌ No metadata found")
            return False

        # Display key information
        print("\n📀 Album Information:")
        print(f"  Title: {metadata.get('title', 'N/A')}")
        print(f"  Artist: {metadata.get('artist_name', 'N/A')}")
        print(f"  Year: {metadata.get('year', 'N/A')}")
        print(f"  Label: {metadata.get('label_name', 'N/A')}")
        print(f"  Catalog #: {metadata.get('catalog_number', 'N/A')}")
        print(f"  Format: {metadata.get('format', 'N/A')}")
        print(f"  Country: {metadata.get('country', 'N/A')}")

        if metadata.get("genres"):
            print(f"  Genres: {', '.join(metadata['genres'])}")

        if metadata.get("styles"):
            print(f"  Styles: {', '.join(metadata['styles'])}")

        print(f"\n🎵 Track Information:")
        print(f"  Track Count: {metadata.get('track_count', 'N/A')}")

        if metadata.get("tracks") and len(metadata["tracks"]) > 0:
            print("  Sample Tracks:")
            for track in metadata["tracks"][:3]:  # Show first 3 tracks
                print(
                    f"    {track.get('position', '?')}. {track.get('title', 'Unknown')}"
                )
            if len(metadata["tracks"]) > 3:
                print(f"    ... and {len(metadata['tracks']) - 3} more tracks")

        print(f"\n🔍 Data Sources:")
        print(f"  Sources: {', '.join(metadata.get('metadata_sources', []))}")
        print(f"  MBID: {metadata.get('mbid', 'N/A')}")
        print(f"  Discogs ID: {metadata.get('discogs_id', 'N/A')}")
        print(f"  Complete: {'✅' if metadata.get('is_complete') else '❌'}")

        # Test caching
        print("\n🔄 Testing cache...")
        metadata2 = await fetcher.fetch_metadata(upc)

        if metadata2.get("fetched_at") == metadata.get("fetched_at"):
            print("✅ Cache is working - same timestamp")
        else:
            print("❌ Cache might not be working - different timestamps")

        return True

    except Exception as e:
        print(f"❌ Error during test: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run metadata fetcher tests."""
    print("\n" + "=" * 60)
    print("METADATA FETCHER TEST")
    print("=" * 60)

    # Use test UPCs from settings
    test_upcs = settings.test_upc_codes[:3]  # Test first 3 UPCs

    print(f"\nTesting with {len(test_upcs)} UPC codes...")

    results = []
    for upc in test_upcs:
        result = await test_metadata_fetch(upc)
        results.append(result)

        # Add delay between requests to respect rate limits
        if upc != test_upcs[-1]:
            print("\n⏳ Waiting before next request (rate limiting)...")
            await asyncio.sleep(2)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    successful = sum(results)
    total = len(results)

    print(f"\nResults: {successful}/{total} successful")

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
