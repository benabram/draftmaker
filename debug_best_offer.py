#!/usr/bin/env python3
"""Debug script to check Best Offer configuration in listings."""

import asyncio
import json
import httpx
from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

EBAY_API_BASE_URL = "https://api.ebay.com"

async def get_offer_details(offer_id: str, access_token: str):
    """Get details of a specific offer."""
    url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer/{offer_id}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                offer = response.json()
                print(f"\nOffer ID: {offer_id}")
                print(f"SKU: {offer.get('sku')}")
                print(f"Status: {offer.get('status')}")
                
                pricing = offer.get('pricingSummary', {})
                print(f"\nPricing Summary:")
                print(f"  Price: ${pricing.get('price', {}).get('value')}")
                print(f"  Best Offer Enabled: {pricing.get('bestOfferEnabled', False)}")
                
                if pricing.get('bestOfferAutoAcceptPrice'):
                    print(f"  Auto Accept Price: ${pricing['bestOfferAutoAcceptPrice'].get('value')}")
                if pricing.get('bestOfferAutoDeclinePrice'):
                    print(f"  Auto Decline Price: ${pricing['bestOfferAutoDeclinePrice'].get('value')}")
                
                return offer
            else:
                print(f"Failed to get offer. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return None
    except Exception as e:
        print(f"Error getting offer: {e}")
        return None

async def list_recent_offers(access_token: str, limit: int = 10):
    """List recent offers to check their Best Offer status."""
    url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    params = {
        "limit": limit,
        "offset": 0,
        "marketplace_id": "EBAY_US"  # Add marketplace filter
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                offers = data.get('offers', [])
                
                print(f"\nFound {len(offers)} offers")
                print("-" * 80)
                
                for offer in offers:
                    offer_id = offer.get('offerId')
                    sku = offer.get('sku')
                    status = offer.get('status')
                    pricing = offer.get('pricingSummary', {})
                    best_offer = pricing.get('bestOfferEnabled', False)
                    
                    print(f"\nOffer ID: {offer_id}")
                    print(f"  SKU: {sku}")
                    print(f"  Status: {status}")
                    print(f"  Price: ${pricing.get('price', {}).get('value')}")
                    print(f"  Best Offer Enabled: {best_offer}")
                    
                    if not best_offer and status == 'PUBLISHED':
                        print(f"  ⚠️  WARNING: Published listing without Best Offer!")
                
                return offers
            else:
                print(f"Failed to list offers. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return []
    except Exception as e:
        print(f"Error listing offers: {e}")
        return []

async def test_create_offer_with_best_offer(access_token: str):
    """Test creating an offer with Best Offer explicitly enabled."""
    
    # Create a test SKU
    test_sku = f"TEST_BESTOFFER_{asyncio.get_event_loop().time():.0f}"
    
    # First create an inventory item
    inventory_url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/inventory_item/{test_sku}"
    
    inventory_payload = {
        "product": {
            "title": "TEST - Best Offer Debug Test Listing",
            "aspects": {
                "Format": ["CD"],
                "Artist": ["Test Artist"],
                "Genre": ["Rock"]
            },
            "description": "This is a test listing to debug Best Offer functionality."
        },
        "condition": "USED_VERY_GOOD",
        "availability": {
            "shipToLocationAvailability": {
                "quantity": 1
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": "en-US"
    }
    
    async with httpx.AsyncClient() as client:
        # Create inventory item
        response = await client.put(
            inventory_url,
            headers=headers,
            json=inventory_payload,
            timeout=30.0
        )
        
        if response.status_code not in [200, 201, 204]:
            print(f"Failed to create inventory item. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        print(f"Created inventory item with SKU: {test_sku}")
        
        # Now create an offer with Best Offer enabled using CORRECT structure
        offer_url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer"
        
        offer_payload = {
            "sku": test_sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "pricingSummary": {
                "price": {
                    "value": "19.99",
                    "currency": "USD"
                }
            },
            "bestOfferTerms": {  # CORRECT: Best Offer at offer level, not in pricingSummary
                "bestOfferEnabled": True,
                "autoAcceptPrice": {
                    "value": "15.00",
                    "currency": "USD"
                },
                "autoDeclinePrice": {
                    "value": "10.00",
                    "currency": "USD"
                }
            },
            "listingPolicies": {
                "fulfillmentPolicyId": "381603015022",
                "paymentPolicyId": "345889112022",
                "returnPolicyId": "345889054022"
            },
            "categoryId": "176984",
            "merchantLocationKey": "DEFAULT_LOCATION"
        }
        
        print(f"\nCreating offer with Best Offer enabled...")
        print(f"Pricing Summary: {json.dumps(offer_payload['pricingSummary'], indent=2)}")
        print(f"Best Offer Terms: {json.dumps(offer_payload.get('bestOfferTerms', {}), indent=2)}")
        
        response = await client.post(
            offer_url,
            headers=headers,
            json=offer_payload,
            timeout=30.0
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            offer_id = result.get('offerId')
            print(f"\n✅ Successfully created offer with ID: {offer_id}")
            
            # Now get the offer details to verify Best Offer is enabled
            await get_offer_details(offer_id, access_token)
        else:
            print(f"\n❌ Failed to create offer. Status: {response.status_code}")
            print(f"Response: {response.text}")

async def main():
    """Main function to debug Best Offer settings."""
    print("=== eBay Best Offer Debug Tool ===\n")
    
    # Initialize token manager
    token_manager = get_token_manager()
    
    # Get eBay access token
    print("Getting eBay access token...")
    access_token = await token_manager.get_ebay_token()
    
    if not access_token:
        print("Failed to get eBay access token")
        return
    
    print("✅ Got access token\n")
    
    # List recent offers to check their Best Offer status
    print("1. Checking recent offers for Best Offer status...")
    await list_recent_offers(access_token, limit=20)
    
    # Test creating an offer with Best Offer enabled
    print("\n" + "="*80)
    print("\n2. Testing offer creation with Best Offer explicitly enabled...")
    await test_create_offer_with_best_offer(access_token)
    
    print("\n" + "="*80)
    print("\nDebug complete!")

if __name__ == "__main__":
    asyncio.run(main())
