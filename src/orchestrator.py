"""Main orchestrator for the eBay listing creation pipeline."""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path

from src.config import settings
from src.utils.logger import get_logger
from src.components.upc_processor import get_upc_processor
from src.components.metadata_fetcher import get_metadata_fetcher
from src.components.pricing_fetcher import get_pricing_fetcher
from src.components.image_fetcher import get_image_fetcher
from src.components.draft_composer import get_draft_composer

logger = get_logger(__name__)


class ListingOrchestrator:
    """Orchestrates the entire listing creation process."""

    def __init__(self, job_id: str = None):
        """Initialize the orchestrator with all components.

        Args:
            job_id: Optional batch job ID for checkpointing
        """
        self.upc_processor = get_upc_processor()
        self.metadata_fetcher = get_metadata_fetcher()
        self.pricing_fetcher = get_pricing_fetcher()
        self.image_fetcher = get_image_fetcher()
        self.draft_composer = get_draft_composer()
        self.job_id = job_id

        # Initialize batch job manager if job_id is provided
        if self.job_id:
            from src.utils.batch_job_manager import get_batch_job_manager

            self.batch_job_manager = get_batch_job_manager()
        else:
            self.batch_job_manager = None

        # Create output directory for results
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

    async def process_batch(
        self,
        input_source: str,
        create_drafts: bool = True,
        save_results: bool = True,
        is_gcs: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a batch of UPCs from a text file.

        Args:
            input_source: GCS path (gs://bucket/file.txt) or local file path
            create_drafts: Whether to create eBay draft listings
            save_results: Whether to save results to files
            is_gcs: Whether the input source is from Google Cloud Storage

        Returns:
            Summary of the batch processing results
        """
        start_time = datetime.utcnow()
        logger.info(f"Starting batch processing from {input_source}")

        # Load and validate UPCs
        if is_gcs:
            # Parse GCS path
            if input_source.startswith("gs://"):
                path_parts = input_source[5:].split("/", 1)
                if len(path_parts) != 2:
                    logger.error(f"Invalid GCS path format: {input_source}")
                    return {
                        "success": False,
                        "error": "Invalid GCS path format. Use: gs://bucket/file.txt",
                        "processed": 0,
                    }
                bucket_name, file_name = path_parts
                upcs = self.upc_processor.load_upcs_from_gcs(bucket_name, file_name)
            else:
                logger.error(f"Invalid GCS path format: {input_source}")
                return {
                    "success": False,
                    "error": "GCS path must start with gs://",
                    "processed": 0,
                }
        else:
            # Load from local file
            upcs = self.upc_processor.load_upcs_from_local_txt(input_source)

        if not upcs:
            logger.error("No valid UPCs found in input file")
            return {"success": False, "error": "No valid UPCs found", "processed": 0}

        logger.info(f"Loaded {len(upcs)} valid UPCs for processing")

        # Check if we should resume from a checkpoint
        start_index = 0
        if self.batch_job_manager and self.job_id:
            start_index = self.batch_job_manager.get_resume_index(self.job_id)
            if start_index > 0:
                logger.info(f"Resuming from checkpoint at index {start_index}")
            # Update total UPCs in job
            self.batch_job_manager.update_job(self.job_id, {"total_upcs": len(upcs)})

        # Process each UPC
        results = []
        successful = 0
        failed = 0

        for i, upc in enumerate(upcs):
            # Skip already processed UPCs if resuming
            if i < start_index:
                continue

            logger.info(f"Processing UPC {i+1}/{len(upcs)}: {upc}")

            try:
                result = await self.process_single_upc(upc, create_drafts)
                results.append(result)

                # Add checkpoint after processing each UPC
                if self.batch_job_manager and self.job_id:
                    self.batch_job_manager.add_checkpoint(
                        self.job_id, i, upc, result["success"], result  # Current index
                    )

                if result["success"]:
                    successful += 1
                    logger.info(f"✓ Successfully processed UPC {upc}")
                else:
                    failed += 1
                    logger.warning(
                        f"✗ Failed to process UPC {upc}: {result.get('error')}"
                    )

                # Add a small delay between requests to avoid rate limiting
                if i < len(upcs) - 1:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Unexpected error processing UPC {upc}: {e}")
                failed += 1
                result = {"upc": upc, "success": False, "error": str(e)}
                results.append(result)

                # Add checkpoint for failed UPC
                if self.batch_job_manager and self.job_id:
                    self.batch_job_manager.add_checkpoint(
                        self.job_id, i, upc, False, result
                    )

        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        # Create summary
        summary = {
            "input_source": input_source,
            "source_type": "gcs" if is_gcs else "local",
            "total_upcs": len(upcs),
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / len(upcs) * 100) if upcs else 0,
            "processing_time_seconds": processing_time,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "results": results,
        }

        # Save results if requested
        if save_results:
            await self._save_results(summary)

        # Log summary
        logger.info(f"\n{'='*50}")
        logger.info(f"BATCH PROCESSING COMPLETE")
        logger.info(f"{'='*50}")
        logger.info(f"Total UPCs: {summary['total_upcs']}")
        logger.info(f"Successful: {summary['successful']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Success Rate: {summary['success_rate']:.1f}%")
        logger.info(
            f"Processing Time: {summary['processing_time_seconds']:.1f} seconds"
        )
        logger.info(f"{'='*50}\n")

        return summary

    async def process_single_upc(
        self, upc: str, create_draft: bool = True
    ) -> Dict[str, Any]:
        """
        Process a single UPC through the entire pipeline.

        Args:
            upc: The UPC to process
            create_draft: Whether to create an eBay draft listing

        Returns:
            Complete result dictionary with all data and status
        """
        result = {
            "upc": upc,
            "success": False,
            "metadata": None,
            "pricing": None,
            "images": None,
            "draft": None,
            "error": None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Step 1: Fetch metadata
            logger.info(f"[{upc}] Fetching metadata...")
            metadata = await self.metadata_fetcher.fetch_metadata(upc)

            # Check if metadata is complete (has at least title and artist)
            if not metadata or not metadata.get("is_complete"):
                result["error"] = "No metadata found or incomplete"
                logger.warning(f"[{upc}] No metadata found or incomplete data")
                return result

            result["metadata"] = metadata
            logger.info(
                f"[{upc}] Metadata found: {metadata.get('artist_name')} - {metadata.get('title')}"
            )

            # Step 2: Fetch pricing
            logger.info(f"[{upc}] Fetching pricing data...")
            pricing = await self.pricing_fetcher.fetch_pricing(metadata)

            if not pricing or not pricing.get("recommended_price"):
                # Use default pricing if fetch fails
                pricing = {
                    "recommended_price": 9.99,
                    "min_price": 7.99,
                    "max_price": 12.99,
                    "confidence": "none",
                    "sample_size": 0,
                    "source": "default",
                }
                logger.warning(f"[{upc}] Using default pricing")
            else:
                logger.info(
                    f"[{upc}] Pricing found: ${pricing['recommended_price']:.2f} (confidence: {pricing.get('confidence', 'unknown')})"
                )

            result["pricing"] = pricing

            # Step 3: Fetch images
            logger.info(f"[{upc}] Fetching album images...")
            images = await self.image_fetcher.fetch_images(metadata)

            if not images or not images.get("primary_image"):
                logger.warning(f"[{upc}] No images found")
                # Continue anyway - eBay allows listings without images
            else:
                logger.info(f"[{upc}] Found {len(images.get('images', []))} images")

            result["images"] = images

            # Step 4: Create draft listing (if requested)
            if create_draft:
                logger.info(f"[{upc}] Creating eBay draft listing...")
                draft_result = await self.draft_composer.create_draft_listing(
                    metadata=metadata,
                    images=images or {"primary_image": None, "images": []},
                    pricing=pricing,
                )

                if draft_result.get("success"):
                    result["draft"] = draft_result
                    result["success"] = True

                    # Log the appropriate information based on whether it was published
                    if draft_result.get("status") == "published" and draft_result.get(
                        "listing_id"
                    ):
                        logger.info(
                            f"[{upc}] Listing published successfully - SKU: {draft_result.get('sku')}, Listing ID: {draft_result.get('listing_id')}"
                        )
                    else:
                        logger.info(
                            f"[{upc}] Offer created successfully - SKU: {draft_result.get('sku')}, Offer ID: {draft_result.get('offer_id')}"
                        )
                else:
                    result["error"] = (
                        f"Draft creation failed: {draft_result.get('error')}"
                    )
                    logger.error(f"[{upc}] {result['error']}")
            else:
                # If not creating drafts, consider success if we have metadata
                result["success"] = True
                logger.info(f"[{upc}] Processing complete (draft creation skipped)")

        except Exception as e:
            logger.error(f"[{upc}] Unexpected error in pipeline: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    async def _save_results(self, summary: Dict[str, Any]) -> None:
        """
        Save processing results to files.

        Args:
            summary: The complete summary dictionary to save
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # Save full results as JSON
        json_file = self.output_dir / f"batch_results_{timestamp}.json"
        with open(json_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"Results saved to {json_file}")

        # Save summary as CSV for easy viewing
        csv_file = self.output_dir / f"batch_summary_{timestamp}.csv"
        with open(csv_file, "w") as f:
            # Write header
            f.write(
                "UPC,Success,Artist,Album,Year,Price,SKU,Offer_ID,Listing_ID,Status,Error\n"
            )

            # Write each result
            for result in summary["results"]:
                upc = result.get("upc", "")
                success = "Yes" if result.get("success") else "No"

                # Get metadata fields
                metadata = result.get("metadata") or {}
                artist = metadata.get("artist_name", "") if metadata else ""
                if artist:
                    artist = artist.replace(",", ";")
                album = metadata.get("title", "") if metadata else ""
                if album:
                    album = album.replace(",", ";")
                year = metadata.get("year", "") if metadata else ""

                # Get pricing
                pricing = result.get("pricing") or {}
                price = pricing.get("recommended_price", "") if pricing else ""

                # Get draft info
                draft = result.get("draft") or {}
                sku = draft.get("sku", "") if draft else ""
                offer_id = draft.get("offer_id", "") if draft else ""
                listing_id = draft.get("listing_id", "") if draft else ""
                status = draft.get("status", "") if draft else ""

                # Get error
                error = result.get("error") or ""
                if error:
                    error = error.replace(",", ";").replace("\n", " ")

                # Write row
                f.write(
                    f"{upc},{success},{artist},{album},{year},{price},{sku},{offer_id},{listing_id},{status},{error}\n"
                )

        logger.info(f"Summary saved to {csv_file}")

    async def test_single_upc(self, upc: str) -> None:
        """
        Test the pipeline with a single UPC.

        Args:
            upc: The UPC to test
        """
        logger.info(f"\n{'='*50}")
        logger.info(f"TESTING SINGLE UPC: {upc}")
        logger.info(f"{'='*50}\n")

        result = await self.process_single_upc(upc, create_draft=False)

        # Pretty print the result
        print("\nRESULT:")
        print("=" * 50)
        print(json.dumps(result, indent=2, default=str))
        print("=" * 50)


# Global orchestrator instance
_orchestrator = None


def get_orchestrator() -> ListingOrchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ListingOrchestrator()
    return _orchestrator


async def main():
    """Main entry point for the orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="eBay Listing Orchestrator")
    parser.add_argument(
        "input_source",
        help="GCS path (gs://bucket/file.txt) or local file path to text file containing UPCs",
    )
    parser.add_argument(
        "--local", action="store_true", help="Use local file instead of GCS"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode - fetch data but don't create drafts",
    )
    parser.add_argument("--single", type=str, help="Process a single UPC for testing")

    args = parser.parse_args()

    orchestrator = get_orchestrator()

    if args.single:
        # Test single UPC
        await orchestrator.test_single_upc(args.single)
    else:
        # Process batch
        create_drafts = not args.test
        is_gcs = not args.local

        summary = await orchestrator.process_batch(
            input_source=args.input_source,
            create_drafts=create_drafts,
            save_results=True,
            is_gcs=is_gcs,
        )

        if summary.get("success") is False:
            exit(1)


if __name__ == "__main__":
    asyncio.run(main())
