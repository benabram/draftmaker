#!/usr/bin/env python3
"""Test script to create and publish an offer with Best Offer enabled."""

import asyncio
import json
import httpx
from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

EBAY_API_BASE_URL = "https://api.ebay.com"


async def create_and_publish_with_best_offer(access_token: str):
    """Create and publish an offer with Best Offer enabled."""

    # Create a test SKU
    test_sku = f"TEST_BO_{asyncio.get_event_loop().time():.0f}"

    # First create an inventory item with all required fields
    inventory_url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/inventory_item/{test_sku}"

    inventory_payload = {
        "product": {
            "title": "Test CD - Best Offer Debug Test",
            "aspects": {
                "Format": ["CD"],
                "Artist": ["Test Artist"],
                "Album Name": ["Test Album"],
                "Genre": ["Rock"],
                "Release Year": ["2020"],
                "CD Grading": ["Excellent Condition"],
                "Case Condition": ["Excellent"],
                "Type": ["Album"],
                "Language": ["English"],
            },
            "description": "<p>Test listing to verify Best Offer functionality. This is a test CD.</p>",
            "imageUrls": [
                "https://i.ebayimg.com/images/g/FYsAAOSwPc5fqz~w/s-l1600.jpg"  # Sample image
            ],
            # Use a valid UPC from our database
            "upc": ["023138640320"],  # Valid UPC from our test data
        },
        "condition": "USED_VERY_GOOD",
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "merchantLocationKey": "DEFAULT_LOCATION",
        "packageWeightAndSize": {
            "dimensions": {"height": 1.0, "length": 7.0, "width": 7.0, "unit": "INCH"},
            "weight": {"value": 12.0, "unit": "OUNCE"},
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Content-Language": "en-US",
    }

    async with httpx.AsyncClient() as client:
        # Create inventory item
        print(f"Creating inventory item with SKU: {test_sku}")
        response = await client.put(
            inventory_url, headers=headers, json=inventory_payload, timeout=30.0
        )

        if response.status_code not in [200, 201, 204]:
            print(f"Failed to create inventory item. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return

        print(f"✅ Created inventory item")

        # Create offer with Best Offer using different structure attempts
        offer_url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer"

        # Try structure 1: bestOfferTerms at offer level
        offer_payload = {
            "sku": test_sku,
            "marketplaceId": "EBAY_US",
            "format": "FIXED_PRICE",
            "availableQuantity": 1,
            "listingStartQuantity": 1,
            "pricingSummary": {"price": {"value": "24.99", "currency": "USD"}},
            "bestOfferTerms": {
                "bestOfferEnabled": True,
                "autoAcceptPrice": {"value": "20.00", "currency": "USD"},
                "autoDeclinePrice": {"value": "12.00", "currency": "USD"},
            },
            "listingPolicies": {
                "fulfillmentPolicyId": "381603015022",
                "paymentPolicyId": "345889112022",
                "returnPolicyId": "345889054022",
            },
            "categoryId": "176984",
            "merchantLocationKey": "DEFAULT_LOCATION",
        }

        print(f"\nCreating offer with Best Offer enabled...")
        print("Structure: bestOfferTerms at offer level")

        response = await client.post(
            offer_url, headers=headers, json=offer_payload, timeout=30.0
        )

        if response.status_code not in [200, 201]:
            print(f"❌ Failed to create offer. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return

        result = response.json()
        offer_id = result.get("offerId")
        print(f"✅ Created offer with ID: {offer_id}")

        # Get offer details before publishing
        print(f"\nChecking offer BEFORE publishing...")
        offer_details_url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer/{offer_id}"
        response = await client.get(offer_details_url, headers=headers, timeout=30.0)

        if response.status_code == 200:
            offer = response.json()
            pricing = offer.get("pricingSummary", {})
            print(f"  Price: ${pricing.get('price', {}).get('value')}")
            print(
                f"  Best Offer Enabled (in pricingSummary): {pricing.get('bestOfferEnabled', False)}"
            )

            # Check if bestOfferTerms exists at offer level
            if "bestOfferTerms" in offer:
                print(f"  Best Offer Terms found: {offer['bestOfferTerms']}")

        # Now publish the offer
        print(f"\nPublishing offer {offer_id}...")
        publish_url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer/{offer_id}/publish"

        response = await client.post(
            publish_url,
            headers=headers,
            json={},  # Empty body for publish
            timeout=30.0,
        )

        if response.status_code == 200:
            publish_result = response.json()
            listing_id = publish_result.get("listingId")
            print(f"✅ Published as listing ID: {listing_id}")

            # Check the offer again after publishing
            print(f"\nChecking offer AFTER publishing...")
            response = await client.get(
                offer_details_url, headers=headers, timeout=30.0
            )

            if response.status_code == 200:
                offer = response.json()
                pricing = offer.get("pricingSummary", {})
                print(f"  Price: ${pricing.get('price', {}).get('value')}")
                print(f"  Best Offer Enabled: {pricing.get('bestOfferEnabled', False)}")
                print(f"  Status: {offer.get('status')}")

                # Check the actual listing
                print(f"\n🔍 View the live listing at:")
                print(f"   https://www.ebay.com/itm/{listing_id}")

        else:
            print(f"❌ Failed to publish offer. Status: {response.status_code}")
            print(f"Response: {response.text}")


async def main():
    """Main function."""
    print("=== eBay Best Offer Publishing Test ===\n")

    # Initialize token manager
    token_manager = get_token_manager()

    # Get eBay access token
    print("Getting eBay access token...")
    access_token = await token_manager.get_ebay_token()

    if not access_token:
        print("Failed to get eBay access token")
        return

    print("✅ Got access token\n")

    # Test creating and publishing with Best Offer
    await create_and_publish_with_best_offer(access_token)

    print("\n" + "=" * 80)
    print("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(main())
