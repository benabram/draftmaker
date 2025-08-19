#!/usr/bin/env python3
"""
Test the production batch processing endpoint with a small subset of UPCs.
"""

import requests
import json
import time
import sys

# Production URL
BASE_URL = "https://draft-maker-541660382374.us-west1.run.app"

def test_small_batch():
    """Test batch processing with a smaller UPC file."""
    
    print("\n" + "="*60)
    print("🧪 Testing eBay Draft Creator - Small Batch Test")
    print("="*60 + "\n")
    
    # Create a small test file with just 3 UPCs
    test_upcs = [
        "093624999621",
        "722975007524",
        "638812705228"
    ]
    
    # Write to a local file first
    with open("test_small_batch.txt", "w") as f:
        for upc in test_upcs:
            f.write(f"{upc}\n")
    
    print(f"1. Created test file with {len(test_upcs)} UPCs:")
    for upc in test_upcs:
        print(f"   - {upc}")
    print()
    
    # Upload to GCS
    print("2. Uploading test file to GCS...")
    import subprocess
    result = subprocess.run(
        ["gsutil", "cp", "test_small_batch.txt", "gs://draft-maker-bucket/test_small_batch.txt"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("   ✅ File uploaded to GCS")
        gcs_path = "gs://draft-maker-bucket/test_small_batch.txt"
    else:
        print(f"   ❌ Failed to upload: {result.stderr}")
        return
    
    print()
    print("3. Checking OAuth token status...")
    try:
        response = requests.get(f"{BASE_URL}/oauth/status", timeout=10)
        if response.status_code == 200:
            oauth_status = response.json()
            if oauth_status.get("token_valid"):
                print(f"   ✅ OAuth tokens are valid")
            else:
                print(f"   ❌ OAuth tokens are not valid")
                return
        else:
            print(f"   ⚠️ OAuth status check returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ OAuth status check failed: {e}")
        return
    
    print()
    print("4. Triggering batch processing...")
    print(f"   - GCS Path: {gcs_path}")
    print(f"   - Mode: Test mode (fetching data only, no drafts)")
    print()
    
    payload = {
        "gcs_path": gcs_path,
        "create_drafts": False,  # Test mode
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
            print(f"   ✅ Batch job created")
            print(f"   - Job ID: {job_id}")
            print()
            
            # Monitor job status
            print("5. Monitoring job progress...")
            max_attempts = 30  # 2.5 minutes max
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
                        
                        # Show details if available
                        if status_data.get("results"):
                            print("\n   Processing details:")
                            results = status_data.get("results", {})
                            
                            # Show summary
                            if "summary" in results:
                                print("   Summary:")
                                for key, value in results["summary"].items():
                                    print(f"     - {key}: {value}")
                            
                            # Show individual UPC results
                            if "details" in results:
                                print("\n   UPC Results:")
                                for upc_result in results["details"]:
                                    if isinstance(upc_result, dict):
                                        upc = upc_result.get("upc", "Unknown")
                                        success = upc_result.get("success", False)
                                        title = upc_result.get("title", "N/A")
                                        print(f"     - {upc}: {'✓' if success else '✗'} {title[:50]}")
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
    print("✅ Small batch test completed")
    print("="*60)

if __name__ == "__main__":
    try:
        test_small_batch()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
