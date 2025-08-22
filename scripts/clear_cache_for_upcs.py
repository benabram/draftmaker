#!/usr/bin/env python3
"""
Script to clear cache entries for specific UPCs that may have stale or incomplete metadata.
This is useful when reprocessing UPCs that previously failed due to incomplete metadata.
"""

import asyncio
import sys
from pathlib import Path
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings, is_development
from src.utils.logger import get_logger, setup_logging
from google.cloud import storage, firestore

setup_logging("INFO")
logger = get_logger(__name__)


class CacheCleaner:
    """Utility to clean cache entries for specific UPCs."""
    
    def __init__(self):
        """Initialize cache cleaner."""
        self.is_dev = is_development()
        
        if self.is_dev:
            # Local cache directory
            self.cache_dir = Path(__file__).parent.parent / ".cache"
            logger.info(f"Using local cache directory: {self.cache_dir}")
        else:
            # Firestore for production
            self.db = firestore.Client(project=settings.gcp_project_id)
            self.collection = settings.firestore_collection_mbid
            logger.info(f"Using Firestore collection: {self.collection}")
    
    def clear_local_cache(self, upc: str) -> bool:
        """
        Clear local cache for a specific UPC.
        
        Args:
            upc: The UPC to clear
            
        Returns:
            True if cache was cleared, False if it didn't exist
        """
        cache_file = self.cache_dir / f"{upc}.json"
        
        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.info(f"✓ Cleared local cache for UPC: {upc}")
                return True
            except Exception as e:
                logger.error(f"✗ Failed to clear local cache for UPC {upc}: {e}")
                return False
        else:
            logger.info(f"  No local cache found for UPC: {upc}")
            return False
    
    async def clear_firestore_cache(self, upc: str) -> bool:
        """
        Clear Firestore cache for a specific UPC.
        
        Args:
            upc: The UPC to clear
            
        Returns:
            True if cache was cleared, False if it didn't exist
        """
        try:
            doc_ref = self.db.collection(self.collection).document(upc)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_ref.delete()
                logger.info(f"✓ Cleared Firestore cache for UPC: {upc}")
                return True
            else:
                logger.info(f"  No Firestore cache found for UPC: {upc}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Failed to clear Firestore cache for UPC {upc}: {e}")
            return False
    
    async def clear_cache_for_upcs(self, upcs: list[str]) -> dict:
        """
        Clear cache for multiple UPCs.
        
        Args:
            upcs: List of UPCs to clear
            
        Returns:
            Summary of cleared caches
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"CLEARING CACHE FOR {len(upcs)} UPCs")
        logger.info(f"{'='*60}\n")
        
        cleared = 0
        not_found = 0
        failed = 0
        
        for upc in upcs:
            if self.is_dev:
                result = self.clear_local_cache(upc)
            else:
                result = await self.clear_firestore_cache(upc)
            
            if result:
                cleared += 1
            elif result is False:
                not_found += 1
            else:
                failed += 1
        
        logger.info(f"\n{'='*60}")
        logger.info(f"CACHE CLEARING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total UPCs: {len(upcs)}")
        logger.info(f"Cleared: {cleared}")
        logger.info(f"Not found: {not_found}")
        logger.info(f"Failed: {failed}")
        
        return {
            "total": len(upcs),
            "cleared": cleared,
            "not_found": not_found,
            "failed": failed
        }
    
    async def clear_cache_from_gcs_file(self, bucket_name: str, file_name: str) -> dict:
        """
        Clear cache for all UPCs in a GCS file.
        
        Args:
            bucket_name: GCS bucket name
            file_name: File name in the bucket
            
        Returns:
            Summary of cleared caches
        """
        logger.info(f"Loading UPCs from gs://{bucket_name}/{file_name}")
        
        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            content = blob.download_as_text()
            
            # Parse UPCs
            upcs = [line.strip() for line in content.splitlines() if line.strip()]
            logger.info(f"Found {len(upcs)} UPCs in file")
            
            return await self.clear_cache_for_upcs(upcs)
            
        except Exception as e:
            logger.error(f"Failed to load UPCs from GCS: {e}")
            return {"error": str(e)}
    
    def list_cached_upcs(self) -> list[str]:
        """
        List all UPCs that have cache entries.
        
        Returns:
            List of cached UPCs
        """
        cached_upcs = []
        
        if self.is_dev:
            # List local cache files
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.json"):
                    upc = cache_file.stem
                    if upc.isdigit():  # Filter out non-UPC files
                        cached_upcs.append(upc)
        else:
            # List Firestore documents
            try:
                docs = self.db.collection(self.collection).stream()
                for doc in docs:
                    cached_upcs.append(doc.id)
            except Exception as e:
                logger.error(f"Failed to list Firestore cache: {e}")
        
        return sorted(cached_upcs)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clear cache entries for specific UPCs"
    )
    parser.add_argument(
        "--upcs",
        nargs="+",
        help="List of UPCs to clear cache for"
    )
    parser.add_argument(
        "--file",
        help="Local file containing UPCs (one per line)"
    )
    parser.add_argument(
        "--gcs",
        help="GCS path to file containing UPCs (e.g., draft-maker-bucket/usedupc7.txt)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all cached UPCs"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clear ALL cached entries (use with caution!)"
    )
    
    args = parser.parse_args()
    
    cleaner = CacheCleaner()
    
    if args.list:
        # List cached UPCs
        cached_upcs = cleaner.list_cached_upcs()
        logger.info(f"\nFound {len(cached_upcs)} cached UPCs:")
        for upc in cached_upcs:
            print(f"  {upc}")
    
    elif args.all:
        # Clear all cache
        response = input("Are you sure you want to clear ALL cache entries? (yes/no): ")
        if response.lower() == "yes":
            cached_upcs = cleaner.list_cached_upcs()
            if cached_upcs:
                await cleaner.clear_cache_for_upcs(cached_upcs)
            else:
                logger.info("No cached entries found")
        else:
            logger.info("Cancelled")
    
    elif args.upcs:
        # Clear specific UPCs
        await cleaner.clear_cache_for_upcs(args.upcs)
    
    elif args.file:
        # Clear UPCs from local file
        with open(args.file, "r") as f:
            upcs = [line.strip() for line in f if line.strip()]
        await cleaner.clear_cache_for_upcs(upcs)
    
    elif args.gcs:
        # Clear UPCs from GCS file
        parts = args.gcs.split("/", 1)
        if len(parts) != 2:
            logger.error("Invalid GCS path format. Use: bucket_name/file_name")
            sys.exit(1)
        
        bucket_name, file_name = parts
        await cleaner.clear_cache_from_gcs_file(bucket_name, file_name)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
