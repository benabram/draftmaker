#!/usr/bin/env python3
"""Trigger batch processing of sample UPCs through the production app."""

import httpx
import asyncio
import json
import time
from datetime import datetime

# Production URL
PRODUCTION_URL = "https://draft-maker-541660382374.us-west1.run.app"

# GCS file path (using the sample file we already have)
GCS_PATH = "gs://draft-maker-bucket/sample_2_upc.txt"

async def trigger_batch_processing():
    """Trigger batch processing through the production API."""
    print("="*60)
    print("TRIGGERING BATCH PROCESSING ON PRODUCTION")
    print(f"URL: {PRODUCTION_URL}")
    print(f"GCS Path: {GCS_PATH}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Trigger batch processing
        print("\n📤 Sending batch processing request...")
        
        try:
            response = await client.post(
                f"{PRODUCTION_URL}/api/batch/process",
                json={
                    "gcs_path": GCS_PATH,
                    "create_drafts": True,
                    "test_mode": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get("job_id")
                print(f"✅ Batch job started successfully!")
                print(f"   Job ID: {job_id}")
                print(f"   Status: {result.get('status')}")
                
                # Monitor the job status
                print("\n⏳ Monitoring job progress...")
                print("-" * 40)
                
                completed = False
                last_status = None
                
                while not completed:
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                    # Get job status
                    status_response = await client.get(
                        f"{PRODUCTION_URL}/api/batch/status/{job_id}"
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        current_status = status_data.get("status")
                        
                        # Print update if status changed
                        if current_status != last_status:
                            print(f"   Status: {current_status}")
                            last_status = current_status
                        
                        # Print progress if available
                        if status_data.get("total_upcs"):
                            successful = status_data.get("successful", 0)
                            failed = status_data.get("failed", 0)
                            total = status_data.get("total_upcs", 0)
                            processed = successful + failed
                            
                            print(f"   Progress: {processed}/{total} UPCs processed")
                            print(f"   ✅ Successful: {successful}")
                            print(f"   ❌ Failed: {failed}")
                        
                        # Check if completed
                        if current_status in ["completed", "failed"]:
                            completed = True
                            
                            print("\n" + "="*60)
                            print("BATCH PROCESSING COMPLETE")
                            print("="*60)
                            
                            if current_status == "completed":
                                print(f"✅ Job completed successfully!")
                                print(f"   Total UPCs: {status_data.get('total_upcs', 0)}")
                                print(f"   Successful: {status_data.get('successful', 0)}")
                                print(f"   Failed: {status_data.get('failed', 0)}")
                                
                                # Extract and display results
                                results = status_data.get("results", {})
                                if results.get("successful_listings"):
                                    print("\n📋 SUCCESSFUL LISTINGS:")
                                    for listing in results["successful_listings"]:
                                        print(f"\n   UPC: {listing.get('upc')}")
                                        print(f"   Artist: {listing.get('artist', 'N/A')}")
                                        print(f"   Album: {listing.get('album', 'N/A')}")
                                        print(f"   Year: {listing.get('year', 'N/A')}")
                                        
                                        listing_id = listing.get('listing_id')
                                        if listing_id:
                                            print(f"   Listing ID: {listing_id}")
                                            print(f"   🔗 View on eBay: https://www.ebay.com/itm/{listing_id}")
                                
                                if results.get("failed_upcs"):
                                    print("\n⚠️ FAILED UPCs:")
                                    for failed in results["failed_upcs"]:
                                        print(f"   • {failed.get('upc')}: {failed.get('error', 'Unknown error')}")
                            else:
                                print(f"❌ Job failed!")
                                print(f"   Error: {status_data.get('error', 'Unknown error')}")
                    else:
                        print(f"⚠️ Failed to get job status: HTTP {status_response.status_code}")
                        
                # Save final results
                if completed:
                    results_file = f"batch_results_{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    with open(results_file, 'w') as f:
                        json.dump(status_data, f, indent=2)
                    print(f"\n💾 Results saved to: {results_file}")
                    
                    print("\n" + "="*60)
                    print("VERIFICATION CHECKLIST")
                    print("="*60)
                    print("Please check the eBay listings to verify:")
                    print("✓ Best Offer is enabled")
                    print("✓ Release date appears in title (when available)")
                    print("✓ CD Grading shows 'Excellent Condition'")
                    print("✓ Case Condition shows 'Excellent'")
                    print("✓ Language shows 'English'")
                    print("✓ Description has track listing after condition text")
                    print("✓ NO 'Case may have punch holes' text appears")
                    print("✓ Producer field appears (when available)")
                    print("="*60)
                    
            else:
                print(f"❌ Failed to start batch job: HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                
        except httpx.TimeoutException:
            print("⏱️ Request timed out (exceeded 5 minutes)")
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(trigger_batch_processing())
