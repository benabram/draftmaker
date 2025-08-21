#!/usr/bin/env python3
"""Test script to trace the exact Best Offer payload being sent to eBay."""

import asyncio
import json
import httpx
from src.components.draft_composer import DraftComposer
from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def test_best_offer_payload():
    """Test the exact payload being sent for Best Offer."""
    
    # Initialize components
    composer = DraftComposer()
    token_manager = get_token_manager()
    
    print("=" * 60)
    print("TESTING BEST OFFER PAYLOAD")
    print("=" * 60)
    
    # 1. Check the template
    print("\n1. Template pricingSummary:")
    print(json.dumps(composer.listing_template["offer"]["pricingSummary"], indent=2))
    
    # 2. Build an offer and check what it contains
    test_pricing = {"recommended_price": 19.99}
    offer = composer._build_offer("TEST_BEST_OFFER_SKU", test_pricing)
    
    print("\n2. After _build_offer method:")
    print("   pricingSummary:", json.dumps(offer["pricingSummary"], indent=2))
    print("   bestOfferEnabled value:", offer["pricingSummary"].get("bestOfferEnabled"))
    
    # 3. Create a real inventory item and offer to see what's sent
    print("\n3. Creating real test listing...")
    
    # Get eBay token
    access_token = await token_manager.get_ebay_token()
    
    # Create test metadata
    test_metadata = {
        "upc": "000000000000",  # Test UPC
        "artist_name": "Test Artist",
        "title": "Test Album - Best Offer Debug",
        "year": "2024",
        "genres": ["Rock"],
        "release_type": "Album",
        "is_complete": True
    }
    
    test_images = {
        "primary_image": "https://i.ebayimg.com/images/g/FYsAAOSwPc5fqz~w/s-l1600.jpg",
        "images": []
    }
    
    # Use composer to build inventory and offer
    sku = composer._generate_sku(test_metadata)
    inventory_payload = composer._build_inventory_item(test_metadata, test_images, test_pricing)
    offer_payload = composer._build_offer(sku, test_pricing)
    
    print(f"\n4. Offer payload that would be sent to eBay:")
    print(f"   SKU: {offer_payload['sku']}")
    print(f"   pricingSummary: {json.dumps(offer_payload['pricingSummary'], indent=2)}")
    
    # Check for any other Best Offer related fields
    print("\n5. Checking for other Best Offer fields in offer:")
    if "bestOfferTerms" in offer_payload:
        print(f"   ⚠️ bestOfferTerms found (WRONG!): {offer_payload['bestOfferTerms']}")
    else:
        print("   ✓ No bestOfferTerms field (correct)")
    
    if "bestOfferEnabled" in offer_payload:
        print(f"   ⚠️ bestOfferEnabled at offer level: {offer_payload['bestOfferEnabled']}")
    else:
        print("   ✓ No bestOfferEnabled at offer level (correct)")
    
    # Create inventory item
    print(f"\n6. Creating inventory item with SKU: {sku}")
    inventory_url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": "en-US"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.put(
            inventory_url,
            headers=headers,
            json=inventory_payload,
            timeout=30.0
        )
        
        if response.status_code in [200, 201, 204]:
            print("   ✓ Inventory item created successfully")
        else:
            print(f"   ✗ Failed to create inventory: {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        # Create offer
        print("\n7. Creating offer with Best Offer enabled...")
        print(f"   Sending pricingSummary: {json.dumps(offer_payload['pricingSummary'], indent=2)}")
        
        offer_url = "https://api.ebay.com/sell/inventory/v1/offer"
        response = await client.post(
            offer_url,
            headers=headers,
            json=offer_payload,
            timeout=30.0
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            offer_id = result.get("offerId")
            print(f"   ✓ Offer created with ID: {offer_id}")
            
            # Get offer details to see what eBay returns
            print("\n8. Retrieving offer from eBay to check Best Offer status...")
            offer_details_url = f"https://api.ebay.com/sell/inventory/v1/offer/{offer_id}"
            response = await client.get(offer_details_url, headers=headers, timeout=30.0)
            
            if response.status_code == 200:
                offer_data = response.json()
                pricing_summary = offer_data.get("pricingSummary", {})
                
                print(f"   eBay returned pricingSummary: {json.dumps(pricing_summary, indent=2)}")
                
                if "bestOfferEnabled" in pricing_summary:
                    print(f"   ✓ Best Offer Enabled: {pricing_summary['bestOfferEnabled']}")
                else:
                    print("   ⚠️ bestOfferEnabled NOT in eBay's response")
                    print("   Note: eBay may not return this field even when set")
        else:
            print(f"   ✗ Failed to create offer: {response.status_code}")
            print(f"   Response: {response.text}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_best_offer_payload())
