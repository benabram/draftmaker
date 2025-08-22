#!/usr/bin/env python3
"""Test the metadata fetcher fallback behavior when MusicBrainz returns no results."""

import sys
import os
import asyncio
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.components.metadata_fetcher import MetadataFetcher
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_musicbrainz_empty_response():
    """
    Test what happens when MusicBrainz returns an empty search result.
    This simulates the case where a CD album is not found in MusicBrainz.
    """
    print("\n" + "="*60)
    print("TEST: MusicBrainz Empty Response Handling")
    print("="*60)
    
    fetcher = MetadataFetcher()
    
    # Use a UPC that's unlikely to exist in MusicBrainz
    # But might exist in Discogs
    test_upcs = [
        "999999999999",  # Likely not in any database
        "888888888888",  # Another unlikely UPC
        "111111111111",  # Yet another test
    ]
    
    for upc in test_upcs:
        print(f"\nTesting UPC: {upc}")
        print("-" * 40)
        
        # Test individual API calls
        print("\n1. Direct API calls:")
        mb_data = await fetcher._fetch_from_musicbrainz(upc)
        dc_data = await fetcher._fetch_from_discogs(upc)
        
        # Check if MusicBrainz returns empty-ish data
        mb_has_title = mb_data.get("title") is not None
        mb_has_artist = mb_data.get("artist_name") is not None
        dc_has_title = dc_data.get("title") is not None
        dc_has_artist = dc_data.get("artist_name") is not None
        
        print(f"   MusicBrainz: Title={mb_data.get('title')}, Artist={mb_data.get('artist_name')}")
        print(f"   Discogs:     Title={dc_data.get('title')}, Artist={dc_data.get('artist_name')}")
        
        # Test combination
        print("\n2. Combined metadata:")
        combined = fetcher._combine_metadata(mb_data, dc_data, upc)
        
        print(f"   Title:       {combined.get('title')}")
        print(f"   Artist:      {combined.get('artist_name')}")
        print(f"   Is Complete: {combined.get('is_complete')}")
        print(f"   Sources:     {combined.get('metadata_sources')}")
        
        # Check for the bug
        print("\n3. Bug Analysis:")
        
        # Bug 1: MusicBrainz in sources even when it returns nothing useful
        if not mb_has_title and not mb_has_artist and "musicbrainz" in combined.get("metadata_sources", []):
            print("   ❌ BUG FOUND: MusicBrainz listed in sources despite returning no useful data")
        else:
            print("   ✅ Correct: MusicBrainz source handling is appropriate")
        
        # Bug 2: Discogs data not being used when MusicBrainz fails
        if dc_has_title and not mb_has_title and combined.get("title") != dc_data.get("title"):
            print("   ❌ BUG FOUND: Discogs title not used when MusicBrainz has no title")
        else:
            print("   ✅ Correct: Title fallback working properly")
            
        if dc_has_artist and not mb_has_artist and combined.get("artist_name") != dc_data.get("artist_name"):
            print("   ❌ BUG FOUND: Discogs artist not used when MusicBrainz has no artist")
        else:
            print("   ✅ Correct: Artist fallback working properly")
        
        # Add delay between tests
        await asyncio.sleep(2)


async def test_full_pipeline():
    """
    Test the complete metadata fetching pipeline with a UPC that should
    demonstrate the fallback behavior.
    """
    print("\n" + "="*60)
    print("TEST: Full Pipeline with Fallback")
    print("="*60)
    
    fetcher = MetadataFetcher()
    
    # Test with a specific UPC that we know might not be in MusicBrainz
    test_upc = "987654321098"
    
    print(f"\nFetching metadata for UPC: {test_upc}")
    metadata = await fetcher.fetch_metadata(test_upc)
    
    print("\nResults:")
    print(f"  Title:       {metadata.get('title')}")
    print(f"  Artist:      {metadata.get('artist_name')}")
    print(f"  Year:        {metadata.get('year')}")
    print(f"  Label:       {metadata.get('label_name')}")
    print(f"  Format:      {metadata.get('format')}")
    print(f"  Is Complete: {metadata.get('is_complete')}")
    print(f"  Sources:     {metadata.get('metadata_sources')}")
    print(f"  MBID:        {metadata.get('mbid')}")
    print(f"  Discogs ID:  {metadata.get('discogs_id')}")
    
    # Analyze the results
    print("\nAnalysis:")
    if metadata.get("mbid") is None and "musicbrainz" in metadata.get("metadata_sources", []):
        print("  ⚠️  Potential issue: MusicBrainz in sources but no MBID found")
    
    if metadata.get("discogs_id") and metadata.get("is_complete"):
        print("  ✅ Discogs fallback appears to be working")
    
    if not metadata.get("is_complete"):
        print("  ❌ Metadata is incomplete - fallback may not be working properly")


async def main():
    """Run all metadata fetcher fallback tests."""
    print("\n" + "="*60)
    print("METADATA FETCHER FALLBACK TEST SUITE")
    print("="*60)
    print("\nThis test verifies that Discogs is properly used as a fallback")
    print("when MusicBrainz cannot find a CD album.")
    
    try:
        # Run the tests
        await test_musicbrainz_empty_response()
        await test_full_pipeline()
        
        print("\n" + "="*60)
        print("TEST SUITE COMPLETE")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False
    
    return True


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
