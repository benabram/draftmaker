#!/usr/bin/env python
"""Test script for the simplified draft-maker application."""

import asyncio
import json
from src.components.metadata_fetcher import get_metadata_fetcher
from src.components.image_fetcher import get_image_fetcher
from src.components.pricing_fetcher import get_pricing_fetcher
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_simplified_pipeline():
    """Test the simplified API integration pipeline."""
    
    # Test UPCs
    test_upcs = [
        "722975007524",  # Test UPC 1
        "638812705228",  # Test UPC 2
    ]
    
    for upc in test_upcs:
        print(f"\n{'='*60}")
        print(f"Testing UPC: {upc}")
        print('='*60)
        
        try:
            # Test 1: Metadata fetching (Discogs only)
            print("\n1. Testing Metadata Fetching (Discogs only)...")
            metadata_fetcher = get_metadata_fetcher()
            metadata = await metadata_fetcher.fetch_metadata(upc)
            
            if metadata.get("is_complete"):
                print(f"✓ Metadata found: {metadata.get('artist_name')} - {metadata.get('title')}")
                print(f"  Source: {', '.join(metadata.get('metadata_sources', []))}")
                print(f"  Year: {metadata.get('year', 'N/A')}")
            else:
                print(f"✗ No complete metadata found")
                continue
            
            # Test 2: Image fetching (Spotify primary, Discogs fallback)
            print("\n2. Testing Image Fetching (Spotify primary)...")
            image_fetcher = get_image_fetcher()
            images = await image_fetcher.fetch_images(metadata)
            
            if images.get("primary_image"):
                print(f"✓ Found {len(images.get('images', []))} images")
                print(f"  Sources: {', '.join(images.get('sources', []))}")
            else:
                print(f"✗ No images found")
            
            # Test 3: Fixed pricing
            print("\n3. Testing Fixed Pricing...")
            pricing_fetcher = get_pricing_fetcher()
            pricing = await pricing_fetcher.fetch_pricing(metadata)
            
            print(f"✓ Fixed price: ${pricing.get('recommended_price'):.2f}")
            print(f"  Strategy: {pricing.get('price_strategy')}")
            print(f"  Reason: {pricing.get('recommendation_reason')}")
            
            # Summary
            print("\n" + "-"*40)
            print("Pipeline Summary:")
            print(f"  Metadata: {'✓' if metadata.get('is_complete') else '✗'} (Discogs)")
            print(f"  Images: {'✓' if images.get('primary_image') else '✗'} ({', '.join(images.get('sources', []))})")
            print(f"  Price: ✓ ${pricing.get('recommended_price'):.2f} (Fixed)")
            
        except Exception as e:
            print(f"\n✗ Error testing UPC {upc}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_simplified_pipeline())
