#!/usr/bin/env python3
"""Debug script to check what payload is being sent to eBay."""

import json
import copy
from pathlib import Path
from datetime import datetime

# Load the template
template_path = Path("data/listing_payload.json")
with open(template_path, "r") as f:
    listing_template = json.load(f)

# Test metadata similar to what we got from the batch
test_metadata = {
    "upc": "023138640320",
    "artist_name": "Crystalized Movements",
    "title": "This Wideness Comes",
    "year": "1990",  # This is in the metadata!
    "date": "1990",
    "label_name": "No. 6 Records",
    "catalog_number": "kar003-2",
    "genres": ["Rock"],
    "release_type": "Album",
    "track_count": 0,
    "tracks": [],
}


def check_offer_payload():
    """Check what the offer payload looks like."""
    print("=" * 60)
    print("CHECKING OFFER PAYLOAD")
    print("=" * 60)

    # Deep copy as in the fixed code
    offer = copy.deepcopy(listing_template["offer"])

    print("\n1. Original template structure:")
    print(json.dumps(listing_template["offer"], indent=2))

    print("\n2. After deep copy:")
    print(json.dumps(offer, indent=2))

    # Check bestOfferEnabled field
    print("\n3. Checking bestOfferEnabled:")
    if "pricingSummary" in offer:
        if "bestOfferEnabled" in offer["pricingSummary"]:
            print(
                f"   ✓ bestOfferEnabled is present: {offer['pricingSummary']['bestOfferEnabled']}"
            )
        else:
            print("   ✗ bestOfferEnabled is NOT in pricingSummary")
    else:
        print("   ✗ pricingSummary is NOT in offer")

    # Set price as the code does
    offer["pricingSummary"]["price"]["value"] = "9.99"

    print("\n4. After setting price:")
    print(f"   Price: {offer['pricingSummary']['price']['value']}")
    print(
        f"   bestOfferEnabled still present: {offer['pricingSummary'].get('bestOfferEnabled', 'MISSING!')}"
    )


def check_inventory_payload():
    """Check what the inventory payload looks like."""
    print("\n" + "=" * 60)
    print("CHECKING INVENTORY PAYLOAD")
    print("=" * 60)

    inventory = copy.deepcopy(listing_template["inventoryItem"])

    # Build title as in the code
    artist = test_metadata.get("artist_name", "Unknown Artist")
    album = test_metadata.get("title", "Unknown Album")
    year = test_metadata.get("year", "")

    print(f"\n1. Metadata values:")
    print(f"   Artist: {artist}")
    print(f"   Album: {album}")
    print(f"   Year from metadata: '{year}' (type: {type(year)})")
    print(f"   Year is truthy: {bool(year)}")

    # Build title
    title_parts = [artist, album]
    if year:
        title_parts.append(f"{year}")
        print(f"   ✓ Year added to title parts")
    else:
        print(f"   ✗ Year NOT added to title parts (empty or falsy)")
    title_parts.append("CD")

    title = " ".join(title_parts)
    print(f"\n2. Generated title: '{title}'")

    # Check aspects
    aspects = inventory["product"]["aspects"]
    if year:
        aspects["Release Year"] = [str(year)]
        print(f"\n3. Release Year aspect set to: {aspects['Release Year']}")
    else:
        print(f"\n3. Release Year aspect NOT set (year is empty)")

    # Check what year values actually come from the API
    print("\n4. Checking actual batch data for year fields:")

    # From the actual batch results
    batch_examples = [
        {"name": "Gun World Porn", "date": "1992-01-28", "year": None},
        {"name": "This Wideness Comes", "date": "1990", "year": None},
        {"name": "Too Little, Too Late", "date": "1992", "year": None},
        {"name": "Tin Cans", "date": "", "year": None},
    ]

    for ex in batch_examples:
        print(f"\n   {ex['name']}:")
        print(f"      date field: '{ex['date']}'")
        print(f"      year field: '{ex['year']}'")

        # Simulate year extraction as in metadata_fetcher
        year_value = ex.get("year")
        if not year_value and ex.get("date"):
            # Extract year from date
            date_str = ex["date"]
            if len(date_str) >= 4:
                year_value = date_str[:4]

        print(f"      Extracted year: '{year_value}'")


def check_metadata_processing():
    """Check how metadata is processed."""
    print("\n" + "=" * 60)
    print("CHECKING METADATA PROCESSING")
    print("=" * 60)

    # Looking at the actual batch result structure
    actual_metadata = {
        "mbid": "81b995ed-a9b0-4eac-9c34-ab03d74c9e37",
        "title": "This Wideness Comes",
        "barcode": "023138640320",
        "date": "1990",  # This is what we get!
        "country": "US",
        "status": "Official",
        # Note: NO 'year' field directly from MusicBrainz
    }

    print("\n1. Raw metadata from MusicBrainz:")
    print(f"   date: '{actual_metadata.get('date')}'")
    print(f"   year: '{actual_metadata.get('year')}' (not present)")

    # This is what metadata_fetcher should do (lines 406-410)
    combined = actual_metadata.copy()
    if not combined.get("year") and combined.get("date"):
        # Extract year from date
        combined["year"] = (
            combined["date"][:4] if len(combined.get("date", "")) >= 4 else None
        )
        print(f"\n2. After year extraction in metadata_fetcher:")
        print(f"   year should be: '{combined['year']}'")

    print("\n3. PROBLEM IDENTIFIED:")
    print("   The metadata_fetcher extracts year from date field,")
    print("   but this might not be happening in production!")


if __name__ == "__main__":
    check_offer_payload()
    check_inventory_payload()
    check_metadata_processing()

    print("\n" + "=" * 60)
    print("ISSUES FOUND:")
    print("=" * 60)
    print(
        """
1. BEST OFFER ISSUE:
   - The template has bestOfferEnabled: true ✓
   - Deep copy preserves it ✓
   - BUT: The offer might be getting modified elsewhere OR
   - eBay API might require additional fields/settings

2. RELEASE DATE ISSUES:
   - MusicBrainz returns 'date' field, NOT 'year' field
   - The metadata_fetcher should extract year from date (lines 406-410)
   - But the batch results show NO year field in final metadata!
   - This means the year extraction logic is NOT working properly

3. RECOMMENDED FIXES:
   - Fix metadata_fetcher to properly extract year from date for MusicBrainz
   - Ensure bestOfferEnabled is in the correct format for eBay API
   - Add more logging to see what's actually sent to eBay
"""
    )
