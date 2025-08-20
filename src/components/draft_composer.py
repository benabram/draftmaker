"""Draft composer component for creating eBay listings using the Sell API."""

import json
import asyncio
import copy
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from pathlib import Path

from src.config import settings
from src.utils.logger import get_logger
from src.utils.token_manager import get_token_manager

logger = get_logger(__name__)

# eBay Sell API endpoints
EBAY_API_BASE_URL = "https://api.ebay.com"


class DraftComposer:
    """Composes and creates eBay draft listings using the Sell API."""
    
    def __init__(self):
        """Initialize the draft composer."""
        self.token_manager = get_token_manager()
        # Load the listing template
        template_path = Path(__file__).parent.parent.parent / "data" / "listing_payload.json"
        with open(template_path, 'r') as f:
            self.listing_template = json.load(f)
    
    async def create_draft_listing(
        self,
        metadata: Dict[str, Any],
        images: Dict[str, Any],
        pricing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a draft eBay listing using all gathered data.
        
        Args:
            metadata: Album metadata from metadata_fetcher
            images: Image URLs from image_fetcher
            pricing: Pricing information from pricing_fetcher
            
        Returns:
            Result dictionary with listing details and status
        """
        upc = metadata.get("upc")
        logger.info(f"Creating draft listing for UPC: {upc}")
        
        result = {
            "upc": upc,
            "success": False,
            "sku": None,
            "offer_id": None,
            "listing_id": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            # Get eBay access token
            access_token = await self.token_manager.get_ebay_token()
            
            # Generate SKU for this item
            sku = self._generate_sku(metadata)
            result["sku"] = sku
            
            # Build the inventory item payload
            inventory_payload = self._build_inventory_item(metadata, images, pricing)
            
            # Create or update inventory item
            inventory_success = await self._create_inventory_item(sku, inventory_payload, access_token)
            
            if not inventory_success:
                result["error"] = "Failed to create inventory item"
                return result
            
            # Build the offer payload
            offer_payload = self._build_offer(sku, pricing)
            
            # Create offer (this creates the draft listing)
            offer_result = await self._create_offer(offer_payload, access_token)
            
            if offer_result and "offerId" in offer_result:
                result["offer_id"] = offer_result["offerId"]
                result["success"] = True
                result["status"] = "unpublished"
                
                logger.info(f"Successfully created offer for UPC {upc} with SKU {sku}")
                
                # Publish the offer to create a live listing
                logger.info(f"Publishing offer {offer_result['offerId']} to create live listing...")
                listing_result = await self._publish_offer(offer_result["offerId"], access_token)
                
                if listing_result and "listingId" in listing_result:
                    result["listing_id"] = listing_result["listingId"]
                    result["status"] = "published"
                    logger.info(f"Successfully published listing {listing_result['listingId']} for UPC {upc}")
                else:
                    logger.warning(f"Offer created but not published for UPC {upc}. It remains as an unpublished offer.")
                    result["status"] = "unpublished"
            else:
                result["error"] = "Failed to create offer"
                
        except Exception as e:
            logger.error(f"Error creating draft listing for UPC {upc}: {e}")
            result["error"] = str(e)
        
        return result
    
    def _generate_sku(self, metadata: Dict[str, Any]) -> str:
        """
        Generate a unique SKU for the item.
        
        Args:
            metadata: Album metadata
            
        Returns:
            SKU string
        """
        upc = metadata.get("upc", "")
        # Create a simple SKU format: UPC_TIMESTAMP
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"CD_{upc}_{timestamp}"
    
    def _build_inventory_item(self, metadata: Dict[str, Any], images: Dict[str, Any], pricing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the inventory item payload for eBay Sell API.
        
        Args:
            metadata: Album metadata
            images: Image URLs
            pricing: Pricing information
            
        Returns:
            Inventory item payload
        """
        # Start with a deep copy of the template to avoid modifying the original
        inventory = copy.deepcopy(self.listing_template["inventoryItem"])
        
        # Build title
        artist = metadata.get("artist_name", "Unknown Artist")
        album = metadata.get("title", "Unknown Album")
        year = metadata.get("year", "")
        label = metadata.get("label_name", "")
        catalog = metadata.get("catalog_number", "")
        
        # Log metadata for debugging
        logger.debug(f"Building title with metadata - Artist: {artist}, Album: {album}, Year: {year}")
        
        # Create title (max 80 characters for eBay)
        title_parts = [artist, album]
        if year:
            title_parts.append(f"{year}")
        title_parts.append("CD")
        if label:
            title_parts.append(label)
        if catalog:
            title_parts.append(catalog)
        
        title = " ".join(title_parts)
        if len(title) > 80:
            # Truncate if too long
            title = f"{artist} {album} CD"[:77] + "..."
        
        inventory["product"]["title"] = title
        
        # Set image URLs
        if images.get("primary_image"):
            inventory["product"]["imageUrls"] = [images["primary_image"]]
            # Add additional images if available (eBay allows up to 12)
            for img in images.get("images", [])[:11]:  # First 11 + primary = 12 max
                img_url = img.get("ebay_url") or img.get("url")
                if img_url and img_url != images["primary_image"]:
                    inventory["product"]["imageUrls"].append(img_url)
        
        # Set item specifics (aspects)
        aspects = inventory["product"]["aspects"]
        aspects["Artist"] = [artist]
        aspects["Album Name"] = [album]
        
        # Set genre from metadata
        if metadata.get("genres"):
            aspects["Genre"] = [metadata["genres"][0]]  # Use first genre
        elif metadata.get("styles"):
            aspects["Genre"] = [metadata["styles"][0]]  # Use style as fallback
        
        if year:
            aspects["Release Year"] = [str(year)]
            logger.debug(f"Set Release Year aspect to: {year}")
        else:
            logger.warning(f"No year found in metadata for UPC: {metadata.get('upc')}")
        
        if label:
            aspects["Record Label"] = [label]
        
        if catalog:
            aspects["Catalog Number"] = [catalog]
        
        # Add Producer if available in metadata
        producer = metadata.get("producer", "")
        if producer:
            aspects["Producer"] = [producer]
            logger.debug(f"Set Producer aspect to: {producer}")
        
        # Set format details
        aspects["Format"] = ["CD"]
        aspects["Type"] = [metadata.get("release_type", "Album")]
        
        # Set CD Grading (already set in template, but ensure it's "Excellent Condition")
        aspects["CD Grading"] = ["Excellent Condition"]
        
        # Add Case Condition as a separate aspect
        aspects["Case Condition"] = ["Excellent"]
        
        # Set Language to English
        aspects["Language"] = ["English"]
        
        # Remove "Features" if not sealed
        if "Features" in aspects:
            del aspects["Features"]  # We're selling used CDs
        
        # Set condition (most of our CDs are used)
        inventory["condition"] = "USED_VERY_GOOD"
        
        # Set UPC
        inventory["product"]["upc"] = [metadata.get("upc")]
        
        # Build description
        description = self._build_description(metadata, pricing)
        inventory["product"]["description"] = description
        
        # Set availability with merchant location key
        # The merchant location must be pre-configured in the seller's account
        # We created DEFAULT_LOCATION with North Hollywood, CA 91602
        inventory["availability"] = {
            "shipToLocationAvailability": {
                "quantity": 1
            }
        }
        
        # Reference the merchant location key (required for publishing)
        inventory["merchantLocationKey"] = "DEFAULT_LOCATION"
        
        # Add package details (required for publishing)
        # Standard CD jewel case dimensions and weight
        inventory["packageWeightAndSize"] = {
            "dimensions": {
                "height": 1.0,  # inches
                "length": 7.0,  # inches
                "width": 7.0,   # inches
                "unit": "INCH"
            },
            "weight": {
                "value": 12.0,  # ounces (typical CD in jewel case)
                "unit": "OUNCE"
            }
        }
        
        return inventory
    
    def _build_offer(self, sku: str, pricing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the offer payload for eBay Sell API.
        
        Args:
            sku: The SKU of the inventory item
            pricing: Pricing information
            
        Returns:
            Offer payload
        """
        # Start with a deep copy of the template to preserve bestOfferEnabled and other nested fields
        offer = copy.deepcopy(self.listing_template["offer"])
        
        # Set SKU
        offer["sku"] = sku
        
        # Set pricing
        recommended_price = pricing.get("recommended_price", 9.99)
        offer["pricingSummary"]["price"]["value"] = str(recommended_price)
        
        # Remove bestOfferEnabled from pricingSummary if it exists (wrong location)
        if "bestOfferEnabled" in offer["pricingSummary"]:
            del offer["pricingSummary"]["bestOfferEnabled"]
        
        # Add Best Offer configuration at the correct level (offer level, not in pricingSummary)
        offer["bestOfferTerms"] = {
            "bestOfferEnabled": True
        }
        
        logger.info(f"Best Offer enabled: {offer.get('bestOfferTerms', {}).get('bestOfferEnabled', False)}")
        
        # Available quantity is always 1 for individual CDs
        offer["availableQuantity"] = 1
        
        # Set listing start quantity (required for publishing)
        offer["listingStartQuantity"] = 1
        
        # Use the eBay listing policy IDs from settings
        offer["listingPolicies"]["fulfillmentPolicyId"] = "381603015022"  # CD Combined Shipping
        offer["listingPolicies"]["paymentPolicyId"] = settings.ebay_payment_policy_id
        offer["listingPolicies"]["returnPolicyId"] = settings.ebay_return_policy_id
        
        # Set category ID for Music CDs
        offer["categoryId"] = settings.ebay_category_id
        
        # Set marketplace
        offer["marketplaceId"] = "EBAY_US"
        
        # Set format as FIXED_PRICE
        offer["format"] = "FIXED_PRICE"
        
        # Set merchant location key for the offer
        offer["merchantLocationKey"] = "DEFAULT_LOCATION"
        
        # Add store category names (your eBay store's custom categories)
        # This adds the item to your store's "CD" category
        offer["storeCategoryNames"] = ["CD"]
        
        return offer
    
    def _build_description(self, metadata: Dict[str, Any], pricing: Dict[str, Any]) -> str:
        """
        Build a detailed description for the listing.
        
        Args:
            metadata: Album metadata
            pricing: Pricing information
            
        Returns:
            HTML description string
        """
        artist = metadata.get("artist_name", "Unknown Artist")
        album = metadata.get("title", "Unknown Album")
        year = metadata.get("year", "")
        label = metadata.get("label_name", "")
        catalog = metadata.get("catalog_number", "")
        track_count = metadata.get("track_count", "")
        
        description_parts = [
            f"<h3>{artist} - {album}</h3>"
        ]
        
        # Add new condition and refund text block (removed "Case may have punch holes.")
        description_parts.append(
            "<p>The CD, Cover and Case are in Excellent condition.</p>"
        )
        description_parts.append(
            "<p>The listing image is the official release cover art. If a CD or its cover and jewel case "
            "are not in the described condition, we will issue a full refund on receipt of refund request "
            "and proof images.</p>"
        )
        
        # Add track listing after the condition text block
        if metadata.get("tracks") and len(metadata["tracks"]) > 0:
            description_parts.append("<p><strong>Track Listing:</strong></p>")
            description_parts.append("<ol>")
            for track in metadata["tracks"][:20]:  # Limit to first 20 tracks
                track_title = track.get("title", "Unknown")
                description_parts.append(f"<li>{track_title}</li>")
            if len(metadata["tracks"]) > 20:
                description_parts.append(f"<li>... and {len(metadata['tracks']) - 20} more tracks</li>")
            description_parts.append("</ol>")
        
        # Add catalog number after track listing
        if catalog:
            description_parts.append(f"<p><strong>Catalog Number:</strong> {catalog}</p>")
        
        # Add standard footer
        description_parts.append(
            "<hr><p><strong>Shipping:</strong> Combined Shipping available. All CDs are shipped in bubble wrap and a box with tracking.</p>"
        )
        
        return "\n".join(description_parts)
    
    async def _create_inventory_item(self, sku: str, payload: Dict[str, Any], access_token: str) -> bool:
        """
        Create or update an inventory item on eBay.
        
        Args:
            sku: The SKU for the item
            payload: The inventory item payload
            access_token: eBay access token
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/inventory_item/{sku}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Content-Language": "en-US"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Successfully created/updated inventory item with SKU: {sku}")
                    return True
                else:
                    logger.error(f"Failed to create inventory item. Status: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error creating inventory item: {e}")
            return False
    
    async def _create_offer(self, payload: Dict[str, Any], access_token: str) -> Optional[Dict[str, Any]]:
        """
        Create an offer (draft listing) on eBay.
        
        Args:
            payload: The offer payload
            access_token: eBay access token
            
        Returns:
            Offer response with offer ID if successful, None otherwise
        """
        url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Content-Language": "en-US"
        }
        
        # Log the payload being sent to eBay
        logger.info(f"Creating offer with payload:")
        logger.info(f"  SKU: {payload.get('sku')}")
        logger.info(f"  PricingSummary: {json.dumps(payload.get('pricingSummary', {}), indent=2)}")
        logger.info(f"  Store Category Names: {payload.get('storeCategoryNames', [])}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"Successfully created offer with ID: {result.get('offerId')}")
                    
                    # Log what eBay returned
                    if 'pricingSummary' in result:
                        logger.info(f"Returned pricingSummary: {json.dumps(result['pricingSummary'], indent=2)}")
                    
                    return result
                else:
                    logger.error(f"Failed to create offer. Status: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error creating offer: {e}")
            return None
    
    async def _publish_offer(self, offer_id: str, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Publish an offer to create a live listing.
        
        Args:
            offer_id: The offer ID to publish
            access_token: eBay access token
            
        Returns:
            Listing response with listing ID if successful, None otherwise
        """
        url = f"{EBAY_API_BASE_URL}/sell/inventory/v1/offer/{offer_id}/publish"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={},  # Empty body for publish
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Successfully published offer as listing ID: {result.get('listingId')}")
                    return result
                else:
                    logger.error(f"Failed to publish offer. Status: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error publishing offer: {e}")
            return None


# Global draft composer instance
_draft_composer = None


def get_draft_composer() -> DraftComposer:
    """Get the global draft composer instance."""
    global _draft_composer
    if _draft_composer is None:
        _draft_composer = DraftComposer()
    return _draft_composer
