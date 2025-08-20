"""Test to verify that store category names are properly included in eBay offer payloads."""

import json
from src.components.draft_composer import DraftComposer


def test_offer_includes_store_category():
    """Test that the offer payload includes storeCategoryNames field with 'CD' value."""
    # Create a composer instance
    composer = DraftComposer()
    
    # Mock data
    test_sku = 'CD_722975007524_20250820123456'
    test_pricing = {
        'recommended_price': 15.99,
        'lowest_price': 12.99,
        'average_price': 14.50
    }
    
    # Build the offer
    offer = composer._build_offer(test_sku, test_pricing)
    
    # Assertions
    assert 'storeCategoryNames' in offer, "storeCategoryNames field is missing from offer payload"
    assert isinstance(offer['storeCategoryNames'], list), "storeCategoryNames should be a list"
    assert offer['storeCategoryNames'] == ['CD'], "storeCategoryNames should contain 'CD'"
    
    # Also verify other essential fields are present
    assert offer['sku'] == test_sku
    assert offer['categoryId'] == '176984'  # Music CDs category
    assert offer['marketplaceId'] == 'EBAY_US'
    assert offer['format'] == 'FIXED_PRICE'
    assert offer['merchantLocationKey'] == 'DEFAULT_LOCATION'
    
    # Verify pricing is correctly set
    assert offer['pricingSummary']['price']['value'] == '15.99'
    assert offer['pricingSummary']['bestOfferEnabled'] is True
    
    print("✅ All assertions passed: Store category 'CD' is properly included in offer payload")


def test_offer_payload_structure():
    """Test the complete structure of the offer payload including store categories."""
    composer = DraftComposer()
    
    test_metadata = {
        'upc': '722975007524',
        'artist_name': 'Test Artist',
        'title': 'Test Album',
        'year': '2024'
    }
    
    test_sku = composer._generate_sku(test_metadata)
    test_pricing = {'recommended_price': 9.99}
    
    offer = composer._build_offer(test_sku, test_pricing)
    
    # Log the offer structure for debugging
    print("\nOffer payload structure:")
    print(json.dumps({
        'sku': offer.get('sku'),
        'storeCategoryNames': offer.get('storeCategoryNames'),
        'categoryId': offer.get('categoryId'),
        'format': offer.get('format'),
        'marketplaceId': offer.get('marketplaceId'),
        'merchantLocationKey': offer.get('merchantLocationKey'),
        'pricingSummary': {
            'price': offer.get('pricingSummary', {}).get('price'),
            'bestOfferEnabled': offer.get('pricingSummary', {}).get('bestOfferEnabled')
        }
    }, indent=2))
    
    # Verify the store category is included
    assert offer['storeCategoryNames'] == ['CD'], "Store category 'CD' should be included in every offer"
    
    print("\n✅ Store category verification passed")


if __name__ == "__main__":
    # Run the tests
    test_offer_includes_store_category()
    test_offer_payload_structure()
    print("\n🎉 All tests passed! Store category 'CD' will be included in all new eBay offer listings.")
