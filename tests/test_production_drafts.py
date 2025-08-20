#!/usr/bin/env python3
"""
Test the production batch processing with actual draft creation.
"""

import requests
import json
import time
import sys

# Production URL
BASE_URL = "https://draft-maker-541660382374.us-west1.run.app"

def test_with_draft_creation():
    """Test batch processing with actual draft creation."""
    
    print("\n" + "="*60)
    print("🚀 Testing eBay Draft Creator - Production Draft Creation")
    print("="*60 + "\n")
    
    # Use the small test file we created earlier
    gcs_path = "gs://draft-maker-bucket/test_small_batch.txt"
    
    print(f"1. Testing with GCS file: {gcs_path}")
    print("   - File contains 3 UPC codes")
    print("   - Mode: PRODUCTION (creating actual eBay drafts)")
    print()
    
    # Check OAuth status
    print("2. Checking OAuth token status...")
    try:
        response = requests.get(f"{BASE_URL}/oauth/status", timeout=10)
        if response.status_code == 200:
            oauth_status = response.json()
            if oauth_status.get("token_valid"):
                print(f"   ✅ OAuth tokens are valid")
                print(f"   - Expires at: {oauth_status.get('expires_at')}")
            else:
                print(f"   ❌ OAuth tokens are not valid")
                print(f"   - Please authorize at: {BASE_URL}/oauth/authorize")
                return
        else:
            print(f"   ⚠️ OAuth status check returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ OAuth status check failed: {e}")
        return
    
    print()
    print("3. ⚠️  WARNING: This will create ACTUAL eBay draft listings!")
    print("   Continue? (y/n): ", end="")
    
    confirmation = input().strip().lower()
    if confirmation != 'y':
        print("   ❌ Cancelled by user")
        return
    
    print()
    print("4. Triggering batch processing...")
    print(f"   - GCS Path: {gcs_path}")
    print(f"   - Mode: PRODUCTION (creating actual drafts)")
    print()
    
    payload = {
        "gcs_path": gcs_path,
        "create_drafts": True,  # PRODUCTION MODE - Creates actual drafts
        "test_mode": False
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/batch/process",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data.get("job_id")
            print(f"   ✅ Batch job created")
            print(f"   - Job ID: {job_id}")
            print()
            
            # Monitor job status
            print("5. Monitoring job progress...")
            max_attempts = 60  # 5 minutes max
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)
                attempt += 1
                
                status_response = requests.get(
                    f"{BASE_URL}/api/batch/status/{job_id}",
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    current_status = status_data.get("status")
                    
                    print(f"   [{attempt}] Status: {current_status}")
                    
                    if current_status == "completed":
                        print()
                        print("   ✅ Batch processing completed!")
                        print(f"   - Total UPCs: {status_data.get('total_upcs', 0)}")
                        print(f"   - Successful: {status_data.get('successful', 0)}")
                        print(f"   - Failed: {status_data.get('failed', 0)}")
                        
                        # Show results
                        if status_data.get("results"):
                            results = status_data.get("results", {})
                            
                            print("\n   Created Drafts:")
                            print("   " + "-"*50)
                            
                            # Show details of created drafts
                            if "details" in results:
                                for item in results["details"]:
                                    if isinstance(item, dict):
                                        upc = item.get("upc", "Unknown")
                                        success = item.get("success", False)
                                        
                                        if success:
                                            draft = item.get("draft", {})
                                            sku = draft.get("sku", "N/A")
                                            offer_id = draft.get("offer_id", "N/A")
                                            metadata = item.get("metadata", {})
                                            title = f"{metadata.get('artist_name', '')} - {metadata.get('title', '')}"
                                            
                                            print(f"   ✓ UPC: {upc}")
                                            print(f"     Title: {title[:60]}")
                                            print(f"     SKU: {sku}")
                                            print(f"     Offer ID: {offer_id}")
                                            print()
                                        else:
                                            error = item.get("error", "Unknown error")
                                            print(f"   ✗ UPC: {upc}")
                                            print(f"     Error: {error}")
                                            print()
                        
                        print("   " + "-"*50)
                        print("\n   📝 Note: Check your eBay Seller Hub to view the created drafts")
                        print("   URL: https://www.ebay.com/sh/lst/drafts")
                        break
                        
                    elif current_status == "failed":
                        print(f"   ❌ Job failed: {status_data.get('error', 'Unknown error')}")
                        break
                else:
                    print(f"   ⚠️ Failed to get status: {status_response.status_code}")
                    break
            
            if attempt >= max_attempts:
                print("   ⚠️ Job monitoring timed out")
        
        else:
            print(f"   ❌ Failed to create batch job: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    print("\n" + "="*60)
    print("✅ Production test completed")
    print("="*60)

if __name__ == "__main__":
    try:
        test_with_draft_creation()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
