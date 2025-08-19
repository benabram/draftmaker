#!/usr/bin/env python3
"""
Check eBay merchant locations configured in the seller account.
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

async def check_merchant_locations():
    """Check eBay merchant locations."""
    print("\n" + "="*60)
    print("🔍 Checking eBay Merchant Locations")
    print("="*60 + "\n")
    
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
        
        # Get merchant locations
        print("2. Fetching merchant locations from eBay...")
        url = "https://api.ebay.com/sell/inventory/v1/location"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            
            print(f"   Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                locations = data.get("locations", [])
                total = data.get("total", 0)
                
                print(f"   ✅ Found {total} merchant location(s)")
                print()
                
                if locations:
                    print("3. Location Details:")
                    print("   " + "-"*50)
                    
                    for i, location in enumerate(locations, 1):
                        location_key = location.get("merchantLocationKey")
                        name = location.get("name")
                        status = location.get("merchantLocationStatus")
                        
                        address = location.get("location", {}).get("address", {})
                        city = address.get("city")
                        state = address.get("stateOrProvince")
                        country = address.get("country")
                        postal = address.get("postalCode")
                        
                        print(f"   [{i}] Location Key: {location_key}")
                        print(f"       Name: {name}")
                        print(f"       Status: {status}")
                        print(f"       Address: {city}, {state} {postal}, {country}")
                        print()
                    
                    print("   " + "-"*50)
                    print()
                    print("   ✅ You have merchant locations configured!")
                    print("   These are required for publishing offers.")
                    
                else:
                    print("   ❌ No merchant locations found!")
                    print()
                    print("   To publish offers, you need to:")
                    print("   1. Set up a merchant location in eBay Seller Hub")
                    print("   2. Or create one via API using POST /sell/inventory/v1/location/{merchantLocationKey}")
                    print()
                    print("   Creating a default location now...")
                    
                    # Create a default location
                    location_key = "DEFAULT_LOCATION"
                    location_data = {
                        "location": {
                            "address": {
                                "addressLine1": "123 Main Street",
                                "city": "North Hollywood",
                                "stateOrProvince": "CA",
                                "postalCode": "91602",
                                "country": "US"
                            }
                        },
                        "name": "Default Location",
                        "merchantLocationStatus": "ENABLED",
                        "locationTypes": ["STORE"],
                        "merchantLocationKey": location_key
                    }
                    
                    create_url = f"https://api.ebay.com/sell/inventory/v1/location/{location_key}"
                    create_response = await client.post(
                        create_url,
                        headers=headers,
                        json=location_data,
                        timeout=30.0
                    )
                    
                    if create_response.status_code in [200, 201, 204]:
                        print(f"   ✅ Successfully created default merchant location: {location_key}")
                    else:
                        print(f"   ❌ Failed to create location: {create_response.status_code}")
                        print(f"   Response: {create_response.text[:500]}")
                    
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
        asyncio.run(check_merchant_locations())
    except KeyboardInterrupt:
        print("\n\nCheck cancelled by user.")
    except Exception as e:
        print(f"\n❌ Check failed: {e}")
        sys.exit(1)
