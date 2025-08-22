#!/usr/bin/env python3
"""Test script to verify Discogs API authentication with Personal Access Token."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.components.metadata_fetcher import MetadataFetcher
from src.config import settings

async def test_discogs_auth():
    """Test Discogs API authentication with a known UPC."""
    # Test UPCs - one that should be in Discogs
    test_upcs = [
        "020831147927",  # One that failed in production
        "614223110721",  # Another that failed
        "093624593928",  # Morrissey - should be in Discogs
    ]
    
    # Check if token is configured
    if not settings.discogs_personal_access_token:
        print("❌ DISCOGS_PERSONAL_ACCESS_TOKEN not configured!")
        print("Please set the environment variable:")
        print("export DISCOGS_PERSONAL_ACCESS_TOKEN=<your_token>")
        return False
    
    print(f"✅ Discogs Personal Access Token found (starts with: {settings.discogs_personal_access_token[:8]}...)")
    
    fetcher = MetadataFetcher()
    success_count = 0
    
    for upc in test_upcs:
        print(f"\nTesting UPC: {upc}")
        print("-" * 40)
        
        try:
            # Test Discogs directly
            discogs_data = await fetcher._fetch_from_discogs(upc)
            
            if discogs_data:
                print(f"✅ Discogs API returned data:")
                print(f"   Title: {discogs_data.get('title')}")
                print(f"   Artist: {discogs_data.get('artist_name')}")
                print(f"   Year: {discogs_data.get('year')}")
                print(f"   Discogs ID: {discogs_data.get('discogs_id')}")
                success_count += 1
            else:
                print(f"⚠️ No data returned from Discogs (might not exist in database)")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            
    print(f"\n{'='*50}")
    print(f"Results: {success_count}/{len(test_upcs)} successful API calls")
    print(f"{'='*50}")
    
    return success_count > 0

if __name__ == "__main__":
    # Get the token from the secret (for testing)
    token = os.getenv("DISCOGS_PERSONAL_ACCESS_TOKEN")
    if not token:
        print("Attempting to get token from Google Secret Manager...")
        import subprocess
        try:
            result = subprocess.run(
                ["gcloud", "secrets", "versions", "access", "latest", 
                 "--secret=DISCOGS_PERSONAL_ACCESS_TOKEN", 
                 "--project=draft-maker-468923"],
                capture_output=True,
                text=True,
                check=True
            )
            token = result.stdout.strip()
            if token:
                os.environ["DISCOGS_PERSONAL_ACCESS_TOKEN"] = token
                print("✅ Token retrieved from Secret Manager")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to get token from Secret Manager: {e}")
    
    # Run the test
    success = asyncio.run(test_discogs_auth())
    sys.exit(0 if success else 1)
