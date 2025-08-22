#!/usr/bin/env python3
"""Process sample UPC codes through the production Draft Maker app."""

import httpx
import asyncio
import json
from datetime import datetime

# Production URL
PRODUCTION_URL = "https://draft-maker-541660382374.us-west1.run.app"

# UPC codes from sample_2_upc.txt
UPC_CODES = [
    "077779847921",
    "023138640320",
    "077775764529",
    "018777271325",
    "074646749128",
]


async def process_single_upc(client, upc):
    """Process a single UPC through the production app."""
    print(f"\n{'='*60}")
    print(f"Processing UPC: {upc}")
    print(f"{'='*60}")

    try:
        # Call the production endpoint
        response = await client.post(
            f"{PRODUCTION_URL}/process-upc", json={"upc": upc}, timeout=60.0
        )

        if response.status_code == 200:
            result = response.json()

            # Extract key information
            if result.get("success"):
                print(f"✅ SUCCESS - UPC: {upc}")
                print(
                    f"   Artist: {result.get('metadata', {}).get('artist_name', 'N/A')}"
                )
                print(f"   Album: {result.get('metadata', {}).get('title', 'N/A')}")
                print(f"   Year: {result.get('metadata', {}).get('year', 'N/A')}")
                print(f"   SKU: {result.get('draft', {}).get('sku', 'N/A')}")
                print(f"   Offer ID: {result.get('draft', {}).get('offer_id', 'N/A')}")
                print(
                    f"   Listing ID: {result.get('draft', {}).get('listing_id', 'N/A')}"
                )
                print(f"   Status: {result.get('draft', {}).get('status', 'N/A')}")

                if result.get("draft", {}).get("listing_id"):
                    listing_url = (
                        f"https://www.ebay.com/itm/{result['draft']['listing_id']}"
                    )
                    print(f"   🔗 View Listing: {listing_url}")

                # Check if producer was found
                producer = result.get("metadata", {}).get("producer")
                if producer:
                    print(f"   Producer: {producer}")

                return {
                    "upc": upc,
                    "success": True,
                    "listing_id": result.get("draft", {}).get("listing_id"),
                    "artist": result.get("metadata", {}).get("artist_name"),
                    "album": result.get("metadata", {}).get("title"),
                    "year": result.get("metadata", {}).get("year"),
                }
            else:
                error_msg = result.get("error", "Unknown error")
                print(f"❌ FAILED - UPC: {upc}")
                print(f"   Error: {error_msg}")
                return {"upc": upc, "success": False, "error": error_msg}
        else:
            print(f"❌ HTTP Error {response.status_code} for UPC: {upc}")
            print(f"   Response: {response.text[:200]}")
            return {
                "upc": upc,
                "success": False,
                "error": f"HTTP {response.status_code}",
            }

    except httpx.TimeoutException:
        print(f"⏱️ TIMEOUT - UPC: {upc} (exceeded 60 seconds)")
        return {"upc": upc, "success": False, "error": "Timeout"}
    except Exception as e:
        print(f"❌ EXCEPTION - UPC: {upc}")
        print(f"   Error: {str(e)}")
        return {"upc": upc, "success": False, "error": str(e)}


async def process_all_upcs():
    """Process all UPC codes through the production app."""
    print("=" * 60)
    print("PROCESSING SAMPLE UPCs THROUGH PRODUCTION APP")
    print(f"URL: {PRODUCTION_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total UPCs: {len(UPC_CODES)}")
    print("=" * 60)

    results = []

    async with httpx.AsyncClient() as client:
        # Process UPCs sequentially to avoid overwhelming the API
        for upc in UPC_CODES:
            result = await process_single_upc(client, upc)
            results.append(result)

            # Add a small delay between requests
            await asyncio.sleep(2)

    # Print summary
    print("\n" + "=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")

    if successful:
        print("\n📋 SUCCESSFUL LISTINGS:")
        for r in successful:
            print(
                f"   • {r['upc']}: {r.get('artist', 'N/A')} - {r.get('album', 'N/A')}"
            )
            if r.get("listing_id"):
                print(f"     → https://www.ebay.com/itm/{r['listing_id']}")

    if failed:
        print("\n⚠️ FAILED UPCS:")
        for r in failed:
            print(f"   • {r['upc']}: {r.get('error', 'Unknown error')}")

    # Save results to file
    results_file = (
        f"sample_upcs_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Results saved to: {results_file}")

    return results


if __name__ == "__main__":
    # Run the async function
    results = asyncio.run(process_all_upcs())

    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("Please check the eBay listings to verify:")
    print("1. Best Offer is enabled")
    print("2. Release date appears in title (when available)")
    print("3. CD Grading shows 'Excellent Condition'")
    print("4. Case Condition shows 'Excellent'")
    print("5. Language shows 'English'")
    print("6. Description has track listing after condition text")
    print("7. No 'Case may have punch holes' text appears")
    print("=" * 60)
