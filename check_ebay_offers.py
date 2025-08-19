#!/usr/bin/env python3
"""
Check eBay offers created via the Sell API.
"""

import sys
import os
import asyncio
import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def check_offers():
    """Check eBay offers via API."""
    print("\n" + "="*60)
    print("🔍 Checking eBay Offers Created via API")
    print("="*60 + "\n")
    
    try:
        # Get token from token manager
        print("1. Retrieving access token...")
        token_manager = get_token_manager()
        access_token = await token_manager.get_ebay_token()
        print(f"   ✅ Token retrieved")
        print()
        
        # List offers
        print("2. Fetching offers from eBay API...")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Get all offers
        url = "https://api.ebay.com/sell/inventory/v1/offer?limit=100"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                offers = data.get("offers", [])
                total = data.get("total", 0)
                
                print(f"   ✅ Found {total} offers")
                print()
                
                if offers:
                    print("3. Offer Details:")
                    print("   " + "-"*50)
                    
                    for i, offer in enumerate(offers[:10], 1):  # Show first 10
                        offer_id = offer.get("offerId")
                        sku = offer.get("sku")
                        status = offer.get("status")
                        price = offer.get("pricingSummary", {}).get("price", {})
                        price_value = price.get("value", "N/A")
                        currency = price.get("currency", "USD")
                        listing_status = offer.get("listing", {}).get("listingStatus", "UNPUBLISHED")
                        
                        print(f"   [{i}] Offer ID: {offer_id}")
                        print(f"       SKU: {sku}")
                        print(f"       Status: {status}")
                        print(f"       Price: {currency} {price_value}")
                        print(f"       Listing Status: {listing_status}")
                        
                        # Get inventory item details for this SKU
                        if sku:
                            inv_url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
                            inv_response = await client.get(inv_url, headers=headers, timeout=30.0)
                            
                            if inv_response.status_code == 200:
                                inv_data = inv_response.json()
                                title = inv_data.get("product", {}).get("title", "N/A")
                                print(f"       Title: {title[:60]}...")
                        
                        print()
                    
                    if total > 10:
                        print(f"   ... and {total - 10} more offers")
                    
                    print("   " + "-"*50)
                    print()
                    print("   📝 Note: These offers are created via API and are NOT")
                    print("   the same as 'drafts' in the Seller Hub UI.")
                    print()
                    print("   To make them appear as listings:")
                    print("   1. Publish them via API using the publish endpoint")
                    print("   2. Or use eBay's Seller Hub API tools")
                else:
                    print("   No offers found")
                    
            else:
                print(f"   ⚠️ API returned status {response.status_code}")
                print(f"   Response: {response.text[:500]}")
        
        print("\n" + "="*60)
        print("✅ Check complete")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(check_offers())
    except KeyboardInterrupt:
        print("\n\nCheck cancelled by user.")
    except Exception as e:
        print(f"\n❌ Check failed: {e}")
        sys.exit(1)
