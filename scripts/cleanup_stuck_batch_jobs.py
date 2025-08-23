#!/usr/bin/env python3
"""
Emergency cleanup script for stuck batch jobs.
This script will:
1. Find all batch jobs stuck in 'running' state
2. Mark them as 'failed' with appropriate error messages
3. Provide a summary of actions taken
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from google.cloud import firestore
import json

# Set up service account credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/benbuntu/draftmaker/service-account-key.json'

# Constants
PROJECT_ID = 'draft-maker-468923'
COLLECTION_NAME = 'batch_jobs'

def cleanup_stuck_jobs():
    """Clean up all stuck batch jobs."""
    
    # Initialize Firestore client
    db = firestore.Client(project=PROJECT_ID)
    batch_collection = db.collection(COLLECTION_NAME)
    
    print("=" * 70)
    print("BATCH JOB CLEANUP SCRIPT")
    print("=" * 70)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    # Find all running jobs
    print("Step 1: Finding all batch jobs in 'running' state...")
    running_jobs = batch_collection.where("status", "==", "running").stream()
    
    jobs_to_clean = []
    for job_doc in running_jobs:
        job_data = job_doc.to_dict()
        job_id = job_data.get("job_id")
        jobs_to_clean.append({
            "id": job_id,
            "started_at": job_data.get("started_at"),
            "last_update": job_data.get("updated_at"),
            "total_upcs": job_data.get("total_upcs", 0),
            "processed": job_data.get("processed_upcs", 0),
            "successful": job_data.get("successful_upcs", 0),
            "failed": job_data.get("failed_upcs", 0),
            "gcs_path": job_data.get("gcs_path")
        })
    
    if not jobs_to_clean:
        print("✅ No stuck jobs found. All clear!")
        return
    
    print(f"⚠️  Found {len(jobs_to_clean)} stuck job(s):")
    print()
    
    for job in jobs_to_clean:
        print(f"  Job ID: {job['id']}")
        print(f"    - GCS Path: {job['gcs_path']}")
        print(f"    - Started: {job['started_at']}")
        print(f"    - Progress: {job['processed']}/{job['total_upcs']} UPCs")
        print(f"    - Success/Failed: {job['successful']}/{job['failed']}")
        print()
    
    # Confirm action
    print("-" * 70)
    response = input("Do you want to mark all these jobs as failed? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Operation cancelled.")
        return
    
    print()
    print("Step 2: Marking jobs as failed...")
    print()
    
    success_count = 0
    fail_count = 0
    
    for job in jobs_to_clean:
        job_id = job['id']
        try:
            # Update the job status
            doc_ref = batch_collection.document(job_id)
            doc_ref.update({
                "status": "failed",
                "error": "Batch job stuck due to scheduler misconfiguration - marked as failed during cleanup",
                "completed_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "cleanup_notes": {
                    "cleaned_at": datetime.now(timezone.utc).isoformat(),
                    "reason": "Emergency cleanup - batch monitor scheduler was running every 10 seconds instead of 10 minutes",
                    "original_error": job_data.get("error") if 'job_data' in locals() else None,
                    "processed_count": job['processed'],
                    "success_count": job['successful'],
                    "failed_count": job['failed']
                }
            })
            print(f"  ✅ Successfully marked {job_id} as failed")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ Failed to update {job_id}: {e}")
            fail_count += 1
    
    print()
    print("=" * 70)
    print("CLEANUP SUMMARY")
    print("=" * 70)
    print(f"Total jobs processed: {len(jobs_to_clean)}")
    print(f"Successfully cleaned: {success_count}")
    print(f"Failed to clean: {fail_count}")
    print()
    
    # Additional verification
    print("Step 3: Verifying cleanup...")
    remaining = batch_collection.where("status", "==", "running").stream()
    remaining_count = sum(1 for _ in remaining)
    
    if remaining_count == 0:
        print("✅ All stuck jobs have been successfully cleaned up!")
    else:
        print(f"⚠️  Warning: {remaining_count} job(s) still in 'running' state")
    
    print()
    print("Next Steps:")
    print("1. Fix the batch-monitor-scheduler schedule (change from */10 * * * * to */10 * * *)")
    print("2. Implement proper transaction-based recovery in the API")
    print("3. Add recovery attempt limits to prevent infinite loops")
    print("4. Resume the scheduler after fixes are in place")
    print()
    print("To fix the scheduler, run:")
    print('gcloud scheduler jobs update http batch-monitor-scheduler \\')
    print('  --schedule="*/10 * * * *" \\')
    print('  --location=us-west1 \\')
    print('  --project=draft-maker-468923')
    print()

if __name__ == "__main__":
    try:
        cleanup_stuck_jobs()
    except KeyboardInterrupt:
        print("\n\n❌ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
