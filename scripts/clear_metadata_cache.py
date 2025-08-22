#!/usr/bin/env python3
"""
Script to clear cached metadata for specific UPCs that may have incomplete data
due to Discogs API authentication failures.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import firestore
from src.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# UPCs that were reported as having issues and any others that might have cached incomplete data
UPCS_TO_CLEAR = [
    "722975007425",  # Reported in the issue
    "738027100525",  # Reported in the issue
    "722975007524",  # From test data
    "638812705228",
    "724383030422",
    "652637281521",
    "606949007423",
    "074645276922",
    "017837709525",
    "075678304026",
    "074646850626",
    "075992412025",
    # Add any other UPCs from recent batch processing that might have incomplete data
    "5018584011928",
    "780622106921",
    "090062801127",
    "723809220027",
    "614223110721",
    "766627001126",
    "020831147927",
    "077775764529",
    "718751853928",
    "723248403227",
    "074644508321",
    "022397289622",
    "727057570422",
]

def clear_cache_entries():
    """Clear cached metadata for specified UPCs from Firestore."""
    
    # Initialize Firestore client
    db = firestore.Client(project=settings.gcp_project_id)
    collection = db.collection(settings.firestore_collection_mbid)
    
    cleared_count = 0
    error_count = 0
    
    for upc in UPCS_TO_CLEAR:
        try:
            # Check if document exists
            doc_ref = collection.document(upc)
            doc = doc_ref.get()
            
            if doc.exists:
                # Delete the cached entry
                doc_ref.delete()
                logger.info(f"✓ Cleared cache for UPC: {upc}")
                cleared_count += 1
            else:
                logger.debug(f"- No cache entry found for UPC: {upc}")
                
        except Exception as e:
            logger.error(f"✗ Error clearing cache for UPC {upc}: {e}")
            error_count += 1
    
    # Also clear any entries that have incomplete metadata (no discogs_id but should have one)
    logger.info("\nChecking for other potentially incomplete cache entries...")
    
    try:
        # Query for documents that might be incomplete
        # (have metadata but missing discogs_id which indicates Discogs fetch failed)
        docs = collection.stream()
        additional_cleared = 0
        
        for doc in docs:
            data = doc.to_dict()
            metadata = data.get("metadata", {})
            
            # If metadata exists but has no discogs_id and no discogs source, it might be incomplete
            if metadata and "discogs" not in metadata.get("metadata_sources", []):
                doc_ref = collection.document(doc.id)
                doc_ref.delete()
                logger.info(f"✓ Cleared potentially incomplete cache for UPC: {doc.id}")
                additional_cleared += 1
                
        if additional_cleared > 0:
            cleared_count += additional_cleared
            logger.info(f"Cleared {additional_cleared} additional incomplete cache entries")
            
    except Exception as e:
        logger.error(f"Error checking for incomplete entries: {e}")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Cache clearing complete!")
    logger.info(f"Cleared: {cleared_count} entries")
    if error_count > 0:
        logger.info(f"Errors: {error_count}")
    logger.info(f"{'='*50}")
    
    return cleared_count, error_count

if __name__ == "__main__":
    logger.info("Starting metadata cache cleanup...")
    logger.info(f"Target collection: {settings.firestore_collection_mbid}")
    logger.info(f"Project: {settings.gcp_project_id}")
    logger.info("")
    
    cleared, errors = clear_cache_entries()
    
    if errors > 0:
        sys.exit(1)
    sys.exit(0)
