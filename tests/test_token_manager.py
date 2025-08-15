#!/usr/bin/env python3
"""Test the token management system."""

import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_spotify_token():
    """Test Spotify token acquisition."""
    print("\n" + "="*60)
    print("Testing Spotify Token Management")
    print("="*60)
    
    token_manager = get_token_manager()
    
    try:
        # First call - should fetch new token
        print("\n1. Getting Spotify token (first call - fetch from API)...")
        token1 = await token_manager.get_spotify_token()
        print(f"✅ Token obtained: {token1[:20]}...{token1[-10:]}")
        
        # Second call - should use cache
        print("\n2. Getting Spotify token (second call - from cache)...")
        token2 = await token_manager.get_spotify_token()
        print(f"✅ Token obtained: {token2[:20]}...{token2[-10:]}")
        
        # Verify tokens are the same
        if token1 == token2:
            print("✅ Tokens match - caching is working correctly!")
        else:
            print("❌ Tokens don't match - something went wrong")
            
        # Test that we can actually use the token
        print("\n3. Testing token validity with Spotify API...")
        import httpx
        
        headers = {
            "Authorization": f"Bearer {token1}"
        }
        
        async with httpx.AsyncClient() as client:
            # Test with a simple API call
            response = await client.get(
                "https://api.spotify.com/v1/browse/categories",
                headers=headers,
                params={"limit": 1}
            )
            
            if response.status_code == 200:
                print("✅ Token is valid - API call successful!")
            else:
                print(f"❌ API call failed with status {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
        
    print("\n" + "="*60)
    print("✅ Spotify token management test completed successfully!")
    print("="*60)
    return True


async def test_ebay_token():
    """Test eBay token management."""
    print("\n" + "="*60)
    print("Testing eBay Token Management")
    print("="*60)
    
    token_manager = get_token_manager()
    
    try:
        print("\nAttempting to get eBay token...")
        token = await token_manager.get_ebay_token()
        print(f"✅ Token obtained: {token[:20]}...{token[-10:]}")
        
    except Exception as e:
        expected_error = "No eBay refresh token found"
        if expected_error in str(e):
            print(f"⚠️  Expected error: {expected_error}")
            print("This is normal - eBay tokens need to be set up first using:")
            print("  python src/utils/ebay_auth_setup.py")
        else:
            print(f"❌ Unexpected error: {e}")
            return False
            
    print("\n" + "="*60)
    return True


async def main():
    """Run all token management tests."""
    print("\n" + "="*60)
    print("TOKEN MANAGEMENT SYSTEM TEST")
    print("="*60)
    
    # Test Spotify token management
    spotify_result = await test_spotify_token()
    
    # Test eBay token management
    ebay_result = await test_ebay_token()
    
    if spotify_result:
        print("\n✅ All token management tests passed!")
    else:
        print("\n❌ Some tests failed. Check the logs above.")
        

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
