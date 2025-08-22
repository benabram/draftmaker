#!/usr/bin/env python3
"""
Test to identify and debug the issue where Discogs metadata is being disregarded
when MusicBrainz API returns no results, causing draft creation to fail.

This test focuses on UPCs from draft-maker-bucket/usedupc7.txt that fail to
return data from MusicBrainz but should successfully retrieve metadata from Discogs.
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils.logger import get_logger, setup_logging
from src.components.metadata_fetcher import get_metadata_fetcher
from src.components.pricing_fetcher import get_pricing_fetcher
from src.components.image_fetcher import get_image_fetcher
from src.components.draft_composer import get_draft_composer
from src.orchestrator import ListingOrchestrator
from google.cloud import storage

# Enable DEBUG level logging to see all details
setup_logging("DEBUG")
logger = get_logger(__name__)


class DiscogsMetadataBugTester:
    """Test harness for debugging the Discogs metadata bug."""
    
    def __init__(self):
        """Initialize test components."""
        self.metadata_fetcher = get_metadata_fetcher()
        self.pricing_fetcher = get_pricing_fetcher()
        self.image_fetcher = get_image_fetcher()
        self.draft_composer = get_draft_composer()
        self.orchestrator = ListingOrchestrator()
        self.storage_client = storage.Client()
        
    async def get_problematic_upcs_from_gcs(self, limit: int = 5) -> List[str]:
        """
        Get UPCs from usedupc7.txt that are likely to have the issue.
        
        Args:
            limit: Maximum number of UPCs to return
            
        Returns:
            List of UPC codes to test
        """
        try:
            bucket = self.storage_client.bucket("draft-maker-bucket")
            blob = bucket.blob("usedupc7.txt")
            content = blob.download_as_text()
            
            # Parse UPCs from the file
            upcs = [line.strip() for line in content.splitlines() if line.strip()]
            
            # Return limited number for testing
            return upcs[:limit]
            
        except Exception as e:
            logger.error(f"Failed to load UPCs from GCS: {e}")
            # Fallback to known problematic UPCs
            return [
                "075596251129",
                "718751853928",
                "018663462622",
                "727057570422",
                "075679228529"
            ][:limit]
    
    async def test_metadata_fetching_flow(self, upc: str) -> Dict[str, Any]:
        """
        Test metadata fetching for a single UPC to identify where data is lost.
        
        Args:
            upc: UPC code to test
            
        Returns:
            Detailed test results
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"TESTING UPC: {upc}")
        logger.info(f"{'='*80}")
        
        result = {
            "upc": upc,
            "timestamp": datetime.utcnow().isoformat(),
            "musicbrainz_response": None,
            "discogs_response": None,
            "combined_metadata": None,
            "draft_creation": None,
            "errors": []
        }
        
        try:
            # Step 1: Test MusicBrainz API directly
            logger.info("\n[STEP 1] Testing MusicBrainz API...")
            musicbrainz_data = await self.metadata_fetcher._fetch_from_musicbrainz(upc)
            
            if musicbrainz_data:
                logger.info(f"✓ MusicBrainz returned data: {json.dumps(musicbrainz_data, indent=2)[:500]}...")
                result["musicbrainz_response"] = {
                    "found": True,
                    "has_title": bool(musicbrainz_data.get("title")),
                    "has_artist": bool(musicbrainz_data.get("artist_name")),
                    "has_mbid": bool(musicbrainz_data.get("mbid")),
                    "data": musicbrainz_data
                }
            else:
                logger.warning("✗ MusicBrainz returned no data (empty dict)")
                result["musicbrainz_response"] = {
                    "found": False,
                    "data": None
                }
            
            # Step 2: Test Discogs API directly
            logger.info("\n[STEP 2] Testing Discogs API...")
            discogs_data = await self.metadata_fetcher._fetch_from_discogs(upc)
            
            if discogs_data:
                logger.info(f"✓ Discogs returned data: {json.dumps(discogs_data, indent=2)[:500]}...")
                result["discogs_response"] = {
                    "found": True,
                    "has_title": bool(discogs_data.get("title")),
                    "has_artist": bool(discogs_data.get("artist_name")),
                    "has_discogs_id": bool(discogs_data.get("discogs_id")),
                    "data": discogs_data
                }
            else:
                logger.warning("✗ Discogs returned no data")
                result["discogs_response"] = {
                    "found": False,
                    "data": None
                }
            
            # Step 3: Test metadata combination
            logger.info("\n[STEP 3] Testing metadata combination...")
            combined = self.metadata_fetcher._combine_metadata(
                musicbrainz_data or {},
                discogs_data or {},
                upc
            )
            
            logger.info(f"Combined metadata: {json.dumps(combined, indent=2)[:500]}...")
            result["combined_metadata"] = {
                "is_complete": combined.get("is_complete"),
                "has_title": bool(combined.get("title")),
                "has_artist": bool(combined.get("artist_name")),
                "sources": combined.get("metadata_sources", []),
                "data": combined
            }
            
            # Step 4: Test full metadata fetch (with caching)
            logger.info("\n[STEP 4] Testing full metadata fetch...")
            full_metadata = await self.metadata_fetcher.fetch_metadata(upc)
            
            if full_metadata and full_metadata.get("is_complete"):
                logger.info(f"✓ Full metadata fetch successful: {full_metadata.get('artist_name')} - {full_metadata.get('title')}")
            else:
                logger.warning(f"✗ Full metadata fetch incomplete or failed")
                result["errors"].append("Full metadata fetch returned incomplete data")
            
            # Step 5: Test orchestrator processing
            logger.info("\n[STEP 5] Testing orchestrator processing...")
            orchestrator_result = await self.orchestrator.process_single_upc(upc, create_draft=False)
            
            if orchestrator_result.get("success"):
                logger.info("✓ Orchestrator processing successful")
            else:
                logger.warning(f"✗ Orchestrator processing failed: {orchestrator_result.get('error')}")
                result["errors"].append(f"Orchestrator failed: {orchestrator_result.get('error')}")
            
            result["orchestrator_result"] = orchestrator_result
            
            # Step 6: If metadata is complete, test draft creation
            if full_metadata and full_metadata.get("is_complete"):
                logger.info("\n[STEP 6] Testing draft creation with metadata...")
                
                # Get pricing
                pricing = await self.pricing_fetcher.fetch_pricing(full_metadata)
                if not pricing or not pricing.get("recommended_price"):
                    pricing = {
                        "recommended_price": 9.99,
                        "min_price": 7.99,
                        "max_price": 12.99,
                        "confidence": "none",
                        "sample_size": 0,
                        "source": "default"
                    }
                
                # Get images
                images = await self.image_fetcher.fetch_images(full_metadata)
                if not images:
                    images = {"primary_image": None, "images": []}
                
                # Try to create draft
                draft_result = await self.draft_composer.create_draft_listing(
                    metadata=full_metadata,
                    images=images,
                    pricing=pricing
                )
                
                result["draft_creation"] = draft_result
                
                if draft_result.get("success"):
                    logger.info(f"✓ Draft creation successful - SKU: {draft_result.get('sku')}")
                    if draft_result.get("listing_id"):
                        logger.info(f"✓ Listing published - ID: {draft_result.get('listing_id')}")
                    else:
                        logger.warning("✗ Draft created but not published")
                else:
                    logger.error(f"✗ Draft creation failed: {draft_result.get('error')}")
                    result["errors"].append(f"Draft creation failed: {draft_result.get('error')}")
            
        except Exception as e:
            logger.error(f"Unexpected error during testing: {e}", exc_info=True)
            result["errors"].append(f"Exception: {str(e)}")
        
        return result
    
    async def run_full_test(self):
        """Run the complete test suite."""
        logger.info("\n" + "="*80)
        logger.info("DISCOGS METADATA BUG TEST")
        logger.info("Testing UPCs that fail MusicBrainz but should work with Discogs")
        logger.info("="*80)
        
        # Get problematic UPCs
        upcs = await self.get_problematic_upcs_from_gcs(limit=3)
        logger.info(f"\nTesting {len(upcs)} UPCs from usedupc7.txt")
        
        results = []
        for upc in upcs:
            result = await self.test_metadata_fetching_flow(upc)
            results.append(result)
            
            # Add delay between tests
            await asyncio.sleep(2)
        
        # Analyze results
        logger.info("\n" + "="*80)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("="*80)
        
        successful = 0
        musicbrainz_only = 0
        discogs_only = 0
        both_sources = 0
        failed = 0
        
        for result in results:
            upc = result["upc"]
            mb_found = result["musicbrainz_response"]["found"] if result["musicbrainz_response"] else False
            discogs_found = result["discogs_response"]["found"] if result["discogs_response"] else False
            combined_complete = result["combined_metadata"]["is_complete"] if result["combined_metadata"] else False
            
            if mb_found and discogs_found:
                both_sources += 1
            elif mb_found:
                musicbrainz_only += 1
            elif discogs_found:
                discogs_only += 1
            
            if combined_complete:
                successful += 1
                status = "✓ SUCCESS"
            else:
                failed += 1
                status = "✗ FAILED"
            
            logger.info(f"\n{status} - UPC: {upc}")
            logger.info(f"  MusicBrainz: {'Found' if mb_found else 'Not found'}")
            logger.info(f"  Discogs: {'Found' if discogs_found else 'Not found'}")
            logger.info(f"  Combined metadata complete: {combined_complete}")
            
            if result["errors"]:
                logger.info(f"  Errors: {', '.join(result['errors'])}")
            
            if result.get("draft_creation"):
                draft = result["draft_creation"]
                if draft.get("success"):
                    logger.info(f"  Draft: Created (SKU: {draft.get('sku')})")
                    if draft.get("listing_id"):
                        logger.info(f"  Listing: Published (ID: {draft.get('listing_id')})")
                else:
                    logger.info(f"  Draft: Failed - {draft.get('error')}")
        
        logger.info("\n" + "-"*40)
        logger.info(f"Total tested: {len(results)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Data sources:")
        logger.info(f"  - Both APIs: {both_sources}")
        logger.info(f"  - MusicBrainz only: {musicbrainz_only}")
        logger.info(f"  - Discogs only: {discogs_only}")
        
        # Save detailed results
        output_file = Path("tests/test_results/discogs_bug_test_results.json")
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump({
                "test_run": datetime.utcnow().isoformat(),
                "summary": {
                    "total": len(results),
                    "successful": successful,
                    "failed": failed,
                    "both_sources": both_sources,
                    "musicbrainz_only": musicbrainz_only,
                    "discogs_only": discogs_only
                },
                "detailed_results": results
            }, f, indent=2, default=str)
        
        logger.info(f"\nDetailed results saved to: {output_file}")
        
        return results


async def main():
    """Main entry point."""
    tester = DiscogsMetadataBugTester()
    results = await tester.run_full_test()
    
    # Check if any tests failed
    failed_tests = [r for r in results if r.get("errors")]
    if failed_tests:
        logger.error(f"\n⚠️  {len(failed_tests)} tests encountered errors")
        sys.exit(1)
    else:
        logger.info(f"\n✓ All tests completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
