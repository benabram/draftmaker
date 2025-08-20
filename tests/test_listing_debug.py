#!/usr/bin/env python3
"""Test script to debug eBay listing creation issues."""

import json
import copy
from pathlib import Path
from datetime import datetime

# Load the template
template_path = Path("data/listing_payload.json")
with open(template_path, 'r') as f:
    listing_template = json.load(f)

# Test metadata (simulating what would come from the API)
test_metadata = {
    "upc": "123456789012",
    "artist_name": "Test Artist",
    "title": "Test Album",
    "year": "2023",
    "label_name": "Test Label",
    "catalog_number": "CAT-123",
    "genres": ["Rock"],
    "release_type": "Album",
    "track_count": 10
}

test_pricing = {
    "recommended_price": 12.99
}

test_images = {
    "primary_image": "https://example.com/image.jpg"
}

def test_offer_creation():
    """Test how the offer is being created."""
    print("=" * 60)
    print("TESTING OFFER CREATION")
    print("=" * 60)
    
    # Method 1: Shallow copy (current implementation)
    offer_shallow = listing_template["offer"].copy()
    print("\n1. Original template bestOfferEnabled:", 
          listing_template["offer"]["pricingSummary"].get("bestOfferEnabled"))
    
    # Modify the shallow copy
    offer_shallow["sku"] = "TEST_SKU_123"
    offer_shallow["pricingSummary"]["price"]["value"] = "12.99"
    
    print("2. Shallow copy bestOfferEnabled after modification:", 
          offer_shallow["pricingSummary"].get("bestOfferEnabled"))
    
    # Method 2: Deep copy (proposed fix)
    offer_deep = copy.deepcopy(listing_template["offer"])
    offer_deep["sku"] = "TEST_SKU_456"
    offer_deep["pricingSummary"]["price"]["value"] = "15.99"
    
    print("3. Deep copy bestOfferEnabled after modification:", 
          offer_deep["pricingSummary"].get("bestOfferEnabled"))
    
    print("\n4. Final offer structure (shallow copy):")
    print(json.dumps(offer_shallow, indent=2))
    
    print("\n5. Final offer structure (deep copy):")
    print(json.dumps(offer_deep, indent=2))

def test_title_generation():
    """Test how the title is being generated."""
    print("\n" + "=" * 60)
    print("TESTING TITLE GENERATION")
    print("=" * 60)
    
    artist = test_metadata.get("artist_name", "Unknown Artist")
    album = test_metadata.get("title", "Unknown Album")
    year = test_metadata.get("year", "")
    label = test_metadata.get("label_name", "")
    catalog = test_metadata.get("catalog_number", "")
    
    # Current implementation
    title_parts = [artist, album]
    if year:
        title_parts.append(f"{year}")  # Current: no parentheses
    title_parts.append("CD")
    if label:
        title_parts.append(label)
    if catalog:
        title_parts.append(catalog)
    
    title = " ".join(title_parts)
    print(f"\n1. Generated title ({len(title)} chars): {title}")
    
    # Check if year is empty
    if not year:
        print("   WARNING: Year is empty or None!")
    
    # Alternative formats
    title_parts_alt1 = [artist, album]
    if year:
        title_parts_alt1.append(f"({year})")  # With parentheses
    title_parts_alt1.append("CD")
    
    title_alt1 = " ".join(title_parts_alt1)
    print(f"2. Alternative title with parens ({len(title_alt1)} chars): {title_alt1}")
    
    # Check truncation
    if len(title) > 80:
        title_truncated = f"{artist} {album} CD"[:77] + "..."
        print(f"3. Truncated title: {title_truncated}")

def test_aspects():
    """Test how aspects/item specifics are being set."""
    print("\n" + "=" * 60)
    print("TESTING ASPECTS/ITEM SPECIFICS")
    print("=" * 60)
    
    # Start with template aspects
    aspects = copy.deepcopy(listing_template["inventoryItem"]["product"]["aspects"])
    
    artist = test_metadata.get("artist_name", "Unknown Artist")
    album = test_metadata.get("title", "Unknown Album")
    year = test_metadata.get("year", "")
    
    # Set aspects as in the code
    aspects["Artist"] = [artist]
    aspects["Album Name"] = [album]
    
    if test_metadata.get("genres"):
        aspects["Genre"] = [test_metadata["genres"][0]]
    
    if year:
        aspects["Release Year"] = [str(year)]
        print(f"\n1. Release Year set to: {aspects['Release Year']}")
    else:
        print("\n1. WARNING: Release Year NOT set (year is empty)")
    
    # Remove Features if present
    if "Features" in aspects:
        del aspects["Features"]
    
    print("\n2. Final aspects:")
    for key, value in aspects.items():
        print(f"   {key}: {value}")
    
    # Check if Release Year is in the final aspects
    if "Release Year" not in aspects:
        print("\n3. ERROR: Release Year is missing from final aspects!")

def check_metadata_source():
    """Check what the metadata might look like from the source."""
    print("\n" + "=" * 60)
    print("CHECKING METADATA SOURCE")
    print("=" * 60)
    
    print("\nTest metadata fields:")
    print(f"  year: {test_metadata.get('year')} (type: {type(test_metadata.get('year'))})")
    print(f"  release_date: {test_metadata.get('release_date')} (type: {type(test_metadata.get('release_date'))})")
    print(f"  released: {test_metadata.get('released')} (type: {type(test_metadata.get('released'))})")
    
    # Check if year might be in a different field
    possible_year_fields = ['year', 'release_year', 'release_date', 'released', 'date']
    print("\nChecking possible year fields:")
    for field in possible_year_fields:
        value = test_metadata.get(field)
        if value:
            print(f"  {field}: {value}")

if __name__ == "__main__":
    test_offer_creation()
    test_title_generation()
    test_aspects()
    check_metadata_source()
    
    print("\n" + "=" * 60)
    print("IDENTIFIED ISSUES:")
    print("=" * 60)
    print("""
1. BEST OFFER ISSUE:
   - The code uses shallow copy (.copy()) which doesn't properly copy nested dicts
   - When pricingSummary["price"]["value"] is modified, it may affect the template
   - Need to use copy.deepcopy() instead

2. RELEASE DATE IN TITLE:
   - The year IS being added to the title if it exists in metadata
   - Need to verify that metadata actually contains 'year' field
   - May need to check alternative field names (release_date, released, etc.)

3. RELEASE DATE IN ASPECTS:
   - The code correctly sets Release Year if year exists
   - Need to ensure year field is populated from the metadata source
   - The field name must match eBay's expected aspect name
""")
