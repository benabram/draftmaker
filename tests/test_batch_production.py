#!/usr/bin/env python3
"""
Script to trigger batch processing on production app.
"""

import requests
import json
import time
from datetime import datetime

def trigger_batch_processing(gcs_path, create_drafts=True, test_mode=False):
    """
    Trigger batch processing on production.
    
    Args:
        gcs_path: GCS path to the UPC file (e.g., gs://bucket/file.txt)
        create_drafts: Whether to create eBay drafts
        test_mode: Whether to run in test mode
    """
    # Production URL with correct endpoint
    url = 'https://draft-app-467925563302.us-central1.run.app/api/batch/process'
    
    # Create the request payload
    payload = {
        'gcs_path': gcs_path,
        'create_drafts': create_drafts,
        'test_mode': test_mode
    }
    
    print(f"Triggering batch processing...")
    print(f"Endpoint: {url}")
    print(f"GCS Path: {gcs_path}")
    print(f"Create Drafts: {create_drafts}")
    print(f"Test Mode: {test_mode}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    try:
        # Send the POST request
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            
            job_id = result.get("job_id")
            if job_id:
                print(f"\n✅ Batch job created successfully!")
                print(f"Job ID: {job_id}")
                print(f"Status: {result.get('status', 'Unknown')}")
                print(f"Started at: {result.get('started_at', 'Unknown')}")
                return job_id
            else:
                print("Batch processing initiated but no job ID returned")
                return None
        else:
            print(f"❌ Error Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 30 seconds")
        return None
    except Exception as e:
        print(f"❌ Error occurred: {str(e)}")
        return None


def check_job_status(job_id):
    """
    Check the status of a batch job.
    
    Args:
        job_id: The job ID to check
    """
    url = f'https://draft-app-467925563302.us-central1.run.app/api/batch/status/{job_id}'
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"Failed to get job status: {response.text}")
            return None
    except Exception as e:
        print(f"Error checking job status: {str(e)}")
        return None


def monitor_job(job_id, check_interval=10, max_checks=60):
    """
    Monitor a batch job until completion.
    
    Args:
        job_id: The job ID to monitor
        check_interval: Seconds between status checks
        max_checks: Maximum number of checks before giving up
    """
    print(f"\nMonitoring job {job_id}...")
    print(f"Checking every {check_interval} seconds (max {max_checks} checks)")
    print("-" * 50)
    
    for i in range(max_checks):
        status = check_job_status(job_id)
        
        if not status:
            print(f"Check {i+1}: Failed to get status")
            time.sleep(check_interval)
            continue
        
        job_status = status.get("status", "unknown")
        print(f"Check {i+1}: Status = {job_status}")
        
        if job_status == "completed":
            print("\n✅ Job completed successfully!")
            print(f"Total UPCs: {status.get('total_upcs', 0)}")
            print(f"Successful: {status.get('successful', 0)}")
            print(f"Failed: {status.get('failed', 0)}")
            
            if status.get('results'):
                print(f"\nDetailed Results:")
                print(json.dumps(status['results'], indent=2))
            
            return status
            
        elif job_status == "failed":
            print(f"\n❌ Job failed!")
            print(f"Error: {status.get('error', 'Unknown error')}")
            return status
            
        elif job_status == "running":
            # Show progress if available
            if status.get('total_upcs'):
                print(f"  Progress: {status.get('successful', 0) + status.get('failed', 0)}/{status.get('total_upcs')} UPCs processed")
        
        time.sleep(check_interval)
    
    print(f"\n⚠️ Monitoring timed out after {max_checks * check_interval} seconds")
    return None


def list_recent_jobs(limit=5):
    """
    List recent batch jobs.
    
    Args:
        limit: Number of jobs to return
    """
    url = f'https://draft-app-467925563302.us-central1.run.app/api/batch/jobs?limit={limit}'
    
    print(f"\nFetching last {limit} batch jobs...")
    print("-" * 50)
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            jobs = result.get('jobs', [])
            
            if not jobs:
                print("No batch jobs found")
                return
            
            print(f"Found {len(jobs)} jobs (total: {result.get('total', 0)})")
            print()
            
            for job in jobs:
                print(f"Job ID: {job.get('job_id')}")
                print(f"  Status: {job.get('status')}")
                print(f"  GCS Path: {job.get('gcs_path')}")
                print(f"  Started: {job.get('started_at')}")
                if job.get('completed_at'):
                    print(f"  Completed: {job.get('completed_at')}")
                if job.get('total_upcs'):
                    print(f"  Results: {job.get('successful', 0)}/{job.get('total_upcs')} successful")
                if job.get('error'):
                    print(f"  Error: {job.get('error')}")
                print()
        else:
            print(f"Failed to list jobs: {response.text}")
            
    except Exception as e:
        print(f"Error listing jobs: {str(e)}")


if __name__ == "__main__":
    # Test file in GCS bucket
    gcs_path = 'gs://ebay-draft-images/test_batch_20241215_sample.txt'
    
    print("=" * 50)
    print("eBay Draft Maker - Batch Processing Test")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # First, list recent jobs
    list_recent_jobs(5)
    
    # Trigger batch processing
    print("\n" + "=" * 50)
    print("Starting new batch job...")
    print("=" * 50)
    
    job_id = trigger_batch_processing(
        gcs_path=gcs_path,
        create_drafts=True,  # Create actual eBay drafts
        test_mode=False      # Production mode
    )
    
    if job_id:
        # Monitor the job until completion
        final_status = monitor_job(job_id, check_interval=10, max_checks=60)
        
        if final_status:
            print("\n" + "=" * 50)
            print("Batch processing complete!")
            print("=" * 50)
        else:
            print("\n" + "=" * 50)
            print("Batch processing status unknown")
            print("=" * 50)
    else:
        print("\n❌ Failed to start batch processing")
