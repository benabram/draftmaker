#!/usr/bin/env python3
"""
Test the production batch processing endpoint with upc_group_t.txt from GCS.
"""

import requests
import json
import time
import sys

# Production URL
BASE_URL = "https://draft-maker-541660382374.us-west1.run.app"

def test_batch_processing():
    """Test batch processing with UPC file from GCS."""
    
    print("\n" + "="*60)
    print("🧪 Testing eBay Draft Creator - Production Batch Processing")
    print("="*60 + "\n")
    
    # Test file from GCS
    gcs_path = "gs://draft-maker-bucket/upc_group_t.txt"
    
    print(f"1. Testing with GCS file: {gcs_path}")
    print("   - File contains 29 UPC codes")
    print()
    
    # Step 1: Check health
    print("2. Checking service health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health = response.json()
            print(f"   ✅ Service is healthy")
            print(f"   - Status: {health.get('status')}")
            print(f"   - Environment: {health.get('environment')}")
            print()
        else:
            print(f"   ⚠️ Health check returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return
    
    # Step 2: Check OAuth status
    print("3. Checking OAuth token status...")
    try:
        response = requests.get(f"{BASE_URL}/oauth/status", timeout=10)
        if response.status_code == 200:
            oauth_status = response.json()
            if oauth_status.get("token_valid"):
                print(f"   ✅ OAuth tokens are valid")
                print(f"   - Expires at: {oauth_status.get('expires_at')}")
                print()
            else:
                print(f"   ❌ OAuth tokens are not valid")
                print(f"   - Please authorize at: {BASE_URL}/oauth/authorize")
                return
        else:
            print(f"   ⚠️ OAuth status check returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ OAuth status check failed: {e}")
        return
    
    # Step 3: Trigger batch processing
    print("4. Triggering batch processing...")
    print(f"   - GCS Path: {gcs_path}")
    print(f"   - Mode: Test mode (no actual drafts created)")
    print()
    
    payload = {
        "gcs_path": gcs_path,
        "create_drafts": False,  # Test mode - don't create actual drafts
        "test_mode": True
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
            print(f"   ✅ Batch job created successfully")
            print(f"   - Job ID: {job_id}")
            print(f"   - Status: {job_data.get('status')}")
            print()
            
            # Step 4: Monitor job status
            print("5. Monitoring job progress...")
            max_attempts = 60  # Max 5 minutes
            attempt = 0
            
            while attempt < max_attempts:
                time.sleep(5)  # Wait 5 seconds between checks
                attempt += 1
                
                status_response = requests.get(
                    f"{BASE_URL}/api/batch/status/{job_id}",
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    current_status = status_data.get("status")
                    
                    print(f"   [{attempt}] Status: {current_status}", end="")
                    
                    if current_status == "completed":
                        print()
                        print()
                        print("   ✅ Batch processing completed!")
                        print(f"   - Total UPCs: {status_data.get('total_upcs', 0)}")
                        print(f"   - Successful: {status_data.get('successful', 0)}")
                        print(f"   - Failed: {status_data.get('failed', 0)}")
                        
                        if status_data.get("results"):
                            print("\n   Results summary:")
                            results = status_data.get("results", {})
                            if results.get("summary"):
                                for key, value in results["summary"].items():
                                    print(f"     - {key}: {value}")
                        break
                    elif current_status == "failed":
                        print()
                        print(f"   ❌ Job failed: {status_data.get('error', 'Unknown error')}")
                        break
                    else:
                        print(f" (checking again in 5s...)")
                else:
                    print(f"\n   ⚠️ Failed to get status: {status_response.status_code}")
                    break
            
            if attempt >= max_attempts:
                print("\n   ⚠️ Job monitoring timed out after 5 minutes")
        
        else:
            print(f"   ❌ Failed to create batch job: {response.status_code}")
            print(f"   Response: {response.text}")
    
    except Exception as e:
        print(f"   ❌ Error triggering batch processing: {e}")
        return
    
    print("\n" + "="*60)
    print("🎉 Test completed!")
    print("="*60)

if __name__ == "__main__":
    try:
        test_batch_processing()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
