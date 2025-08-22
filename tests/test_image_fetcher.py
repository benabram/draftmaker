#!/usr/bin/env python3
"""Test the image fetcher component."""

import sys
import os
import asyncio
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.components.metadata_fetcher import get_metadata_fetcher
from src.components.image_fetcher import get_image_fetcher
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_image_fetch(upc: str):
    """
    Test image fetching for a specific UPC.

    Args:
        upc: The UPC to test
    """
    print(f"\n{'='*60}")
    print(f"Testing image fetch for UPC: {upc}")
    print("=" * 60)

    # First fetch metadata to get MBID if available
    metadata_fetcher = get_metadata_fetcher()
    image_fetcher = get_image_fetcher()

    try:
        # Get metadata
        print("\nFetching metadata first...")
        metadata = await metadata_fetcher.fetch_metadata(upc)

        if not metadata:
            print("❌ No metadata found, cannot fetch images")
            return False

        print(
            f"  Album: {metadata.get('title', 'N/A')} by {metadata.get('artist_name', 'N/A')}"
        )
        print(f"  MBID: {metadata.get('mbid', 'None')}")

        # Fetch images
        print("\n🖼️ Fetching images...")
        images_result = await image_fetcher.fetch_images(metadata)

        if not images_result.get("images"):
            print("❌ No images found")
            return False

        # Display results
        print(f"\n📊 Image Results:")
        print(f"  Total Images: {len(images_result['images'])}")
        print(f"  Sources: {', '.join(images_result['sources'])}")
        print(
            f"  Primary Image: {'✅' if images_result.get('primary_image') else '❌'}"
        )

        # Show image details
        print(f"\n📸 Image Details:")
        for i, img in enumerate(images_result["images"][:3], 1):  # Show first 3
            source = img.get("source", "unknown")
            if source == "cover_art_archive":
                print(f"  {i}. Cover Art Archive:")
                print(f"     - Type: {'Front' if img.get('is_front') else 'Other'}")
                print(f"     - Approved: {'✅' if img.get('approved') else '❌'}")
                print(
                    f"     - Has 500px thumbnail: {'✅' if img.get('thumbnail_500') else '❌'}"
                )
                print(f"     - eBay URL: {img.get('ebay_url', 'N/A')[:50]}...")
            elif source == "spotify":
                print(f"  {i}. Spotify:")
                print(
                    f"     - Size: {img.get('width', 'N/A')}x{img.get('height', 'N/A')}"
                )
                print(f"     - Category: {img.get('size_category', 'N/A')}")
                print(f"     - Album: {img.get('album_name', 'N/A')}")
                print(f"     - URL: {img.get('url', 'N/A')[:50]}...")

        if len(images_result["images"]) > 3:
            print(f"  ... and {len(images_result['images']) - 3} more images")

        # Test primary image selection
        print(f"\n🎯 Primary Image Selection:")
        if images_result.get("primary_image"):
            print(f"  URL: {images_result['primary_image'][:80]}...")

            # Find which source provided the primary image
            for img in images_result["images"]:
                if img.get("url") == images_result["primary_image"]:
                    print(f"  Source: {img.get('source', 'unknown')}")
                    break
        else:
            print("  ❌ No primary image selected")

        return True

    except Exception as e:
        print(f"❌ Error during test: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False


async def main():
    """Run image fetcher tests."""
    print("\n" + "=" * 60)
    print("IMAGE FETCHER TEST")
    print("=" * 60)

    # Test cases: mix of UPCs with and without MBID
    test_cases = [
        settings.test_upc_codes[
            0
        ],  # First test UPC (likely no MBID based on previous test)
        settings.test_upc_codes[1],  # Second test UPC (has MBID based on previous test)
        settings.test_upc_codes[2],  # Third test UPC (has MBID based on previous test)
    ]

    print(f"\nTesting with {len(test_cases)} UPC codes...")
    print(
        "Note: Testing both scenarios - with MBID (Cover Art) and without (Spotify only)"
    )

    results = []
    for upc in test_cases:
        result = await test_image_fetch(upc)
        results.append(result)

        # Add delay between requests
        if upc != test_cases[-1]:
            print("\n⏳ Waiting before next request...")
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
