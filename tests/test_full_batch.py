#!/usr/bin/env python3
"""
Test the production batch processing with the full upc_group_t.txt file.
"""

import requests
import json
import time
import sys

# Production URL
BASE_URL = "https://draft-maker-541660382374.us-west1.run.app"


def test_full_batch():
    """Test batch processing with the full UPC file."""

    print("\n" + "=" * 60)
    print("🚀 Testing eBay Draft Creator - Full Production Test")
    print("=" * 60 + "\n")

    # Use the full test file
    gcs_path = "gs://draft-maker-bucket/upc_group_t.txt"

    print(f"1. Testing with GCS file: {gcs_path}")
    print("   - File contains 29 UPC codes")
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
                return
        else:
            print(f"   ⚠️ OAuth status check returned {response.status_code}")
    except Exception as e:
        print(f"   ❌ OAuth status check failed: {e}")
        return

    print()
    print("3. Triggering batch processing...")
    print(f"   - GCS Path: {gcs_path}")
    print(f"   - Mode: PRODUCTION (creating actual drafts)")
    print()

    payload = {
        "gcs_path": gcs_path,
        "create_drafts": True,  # PRODUCTION MODE
        "test_mode": False,
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/batch/process", json=payload, timeout=30
        )

        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data.get("job_id")
            print(f"   ✅ Batch job created")
            print(f"   - Job ID: {job_id}")
            print()

            # Monitor job status with less frequent updates
            print("4. Monitoring job progress (this will take several minutes)...")
            print(
                "   Processing 29 UPCs with metadata fetching, pricing, and draft creation..."
            )
            print()

            max_attempts = 120  # 10 minutes max
            attempt = 0
            last_status = None

            while attempt < max_attempts:
                time.sleep(5)
                attempt += 1

                status_response = requests.get(
                    f"{BASE_URL}/api/batch/status/{job_id}", timeout=10
                )

                if status_response.status_code == 200:
                    status_data = status_response.json()
                    current_status = status_data.get("status")

                    # Only print status updates when it changes or every 12 attempts (1 minute)
                    if current_status != last_status or attempt % 12 == 0:
                        elapsed = attempt * 5
                        print(f"   [{elapsed}s] Status: {current_status}")
                        last_status = current_status

                    if current_status == "completed":
                        print()
                        print("   ✅ Batch processing completed!")
                        print()
                        print("   Summary:")
                        print("   " + "-" * 50)
                        print(f"   Total UPCs: {status_data.get('total_upcs', 0)}")
                        print(f"   Successful: {status_data.get('successful', 0)}")
                        print(f"   Failed: {status_data.get('failed', 0)}")

                        # Calculate success rate
                        total = status_data.get("total_upcs", 0)
                        successful = status_data.get("successful", 0)
                        if total > 0:
                            success_rate = (successful / total) * 100
                            print(f"   Success Rate: {success_rate:.1f}%")

                        print("   " + "-" * 50)
                        print()
                        print("   📝 Check your eBay Seller Hub for created drafts:")
                        print("   URL: https://www.ebay.com/sh/lst/drafts")
                        break

                    elif current_status == "failed":
                        print()
                        print(
                            f"   ❌ Job failed: {status_data.get('error', 'Unknown error')}"
                        )
                        break
                else:
                    print(f"   ⚠️ Failed to get status: {status_response.status_code}")
                    break

            if attempt >= max_attempts:
                print()
                print("   ⚠️ Job monitoring timed out after 10 minutes")
                print(
                    "   The job may still be running. Check status with job ID:", job_id
                )

        else:
            print(f"   ❌ Failed to create batch job: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    print("\n" + "=" * 60)
    print("✅ Full batch test completed")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_full_batch()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
