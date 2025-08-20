#!/usr/bin/env python3
"""
Check specific eBay offers by their IDs.
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

async def check_specific_offers():
    """Check specific eBay offers via API."""
    print("\n" + "="*60)
    print("🔍 Checking Specific eBay Offers")
    print("="*60 + "\n")
    
    # The offer IDs from our test
    offer_ids = ["65038900011", "65038947011"]
    skus = ["CD_093624999621_20250819045418", "CD_638812705228_20250819045448"]
    
    try:
        # Get token from token manager
        print("1. Retrieving access token...")
        token_manager = get_token_manager()
        access_token = await token_manager.get_ebay_token()
        print(f"   ✅ Token retrieved")
        print()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Check each offer
            print("2. Checking offers by ID...")
            print("   " + "-"*50)
            
            for offer_id in offer_ids:
                print(f"\n   Offer ID: {offer_id}")
                url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}"
                
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code == 200:
                    offer = response.json()
                    sku = offer.get("sku")
                    status = offer.get("status")
                    price = offer.get("pricingSummary", {}).get("price", {})
                    price_value = price.get("value", "N/A")
                    currency = price.get("currency", "USD")
                    
                    print(f"   ✅ Found offer!")
                    print(f"   SKU: {sku}")
                    print(f"   Status: {status}")
                    print(f"   Price: {currency} {price_value}")
                    
                    # Check if it's published
                    listing = offer.get("listing")
                    if listing:
                        print(f"   Listing ID: {listing.get('listingId')}")
                        print(f"   Listing Status: {listing.get('listingStatus')}")
                    else:
                        print(f"   Listing Status: UNPUBLISHED (not visible in Seller Hub)")
                        
                elif response.status_code == 404:
                    print(f"   ❌ Offer not found")
                else:
                    print(f"   ⚠️ Error: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
            
            print("\n   " + "-"*50)
            
            # Check inventory items
            print("\n3. Checking inventory items by SKU...")
            print("   " + "-"*50)
            
            for sku in skus:
                print(f"\n   SKU: {sku}")
                url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
                
                response = await client.get(url, headers=headers, timeout=30.0)
                
                if response.status_code == 200:
                    item = response.json()
                    title = item.get("product", {}).get("title", "N/A")
                    condition = item.get("condition", "N/A")
                    quantity = item.get("availability", {}).get("shipToLocationAvailability", {}).get("quantity", 0)
                    
                    print(f"   ✅ Found inventory item!")
                    print(f"   Title: {title[:60]}...")
                    print(f"   Condition: {condition}")
                    print(f"   Quantity: {quantity}")
                    
                elif response.status_code == 404:
                    print(f"   ❌ Inventory item not found")
                else:
                    print(f"   ⚠️ Error: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
        
        print("\n   " + "-"*50)
        print()
        print("   📝 IMPORTANT NOTES:")
        print("   - Offers created via API are NOT visible in Seller Hub drafts")
        print("   - They exist as 'unpublished offers' in the API")
        print("   - To make them visible as active listings, they must be published")
        print("   - To publish: use the /offer/{offerId}/publish endpoint")
        
        print("\n" + "="*60)
        print("✅ Check complete")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(check_specific_offers())
    except KeyboardInterrupt:
        print("\n\nCheck cancelled by user.")
    except Exception as e:
        print(f"\n❌ Check failed: {e}")
        sys.exit(1)
