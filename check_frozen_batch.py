#!/usr/bin/env python3
"""
Check the status of the frozen batch job in Firestore.
"""

import os
import sys
from pathlib import Path
from google.cloud import firestore
from datetime import datetime
import json

# Set up service account credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/benbuntu/draftmaker/service-account-key.json'

def check_batch_job(job_id):
    """Check the status of a specific batch job."""
    
    # Initialize Firestore client
    db = firestore.Client(project='draft-maker-468923')
    
    print(f"Checking batch job: {job_id}")
    print("=" * 60)
    
    # Get the batch job document
    doc_ref = db.collection('batch_jobs').document(job_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        print(f"ERROR: Batch job {job_id} not found in Firestore!")
        return
    
    job_data = doc.to_dict()
    
    # Display job status
    print(f"Status: {job_data.get('status')}")
    print(f"Total UPCs: {job_data.get('total_upcs', 0)}")
    print(f"Processed UPCs: {job_data.get('processed_upcs', 0)}")
    print(f"Successful UPCs: {job_data.get('successful_upcs', 0)}")
    print(f"Failed UPCs: {job_data.get('failed_upcs', 0)}")
    print(f"Last Processed Index: {job_data.get('last_processed_index', -1)}")
    
    # Check timestamps
    created_at = job_data.get('created_at')
    updated_at = job_data.get('updated_at')
    started_at = job_data.get('started_at')
    completed_at = job_data.get('completed_at')
    
    print("\nTimestamps:")
    if created_at:
        print(f"  Created: {created_at}")
    if started_at:
        print(f"  Started: {started_at}")
    if updated_at:
        print(f"  Last Updated: {updated_at}")
        # Calculate time since last update
        if hasattr(updated_at, 'timestamp'):
            time_since = datetime.utcnow() - updated_at
            print(f"  Time Since Last Update: {time_since}")
    if completed_at:
        print(f"  Completed: {completed_at}")
    
    # Check for errors
    if job_data.get('error'):
        print(f"\nError: {job_data.get('error')}")
    
    # Check last few checkpoints
    checkpoints = job_data.get('checkpoints', [])
    if checkpoints:
        print(f"\nLast 5 Checkpoints:")
        for cp in checkpoints[-5:]:
            print(f"  - Index {cp.get('upc_index')}: UPC {cp.get('upc')} - {'Success' if cp.get('success') else 'Failed'} at {cp.get('timestamp')}")
    
    # Check failed UPCs
    failed_upcs = job_data.get('failed_upc_list', [])
    if failed_upcs:
        print(f"\nFailed UPCs (last 5):")
        for failed in failed_upcs[-5:]:
            print(f"  - UPC {failed.get('upc')} (index {failed.get('index')}): {failed.get('error', 'Unknown error')}")
    
    # Progress calculation
    if job_data.get('total_upcs', 0) > 0:
        progress = (job_data.get('processed_upcs', 0) / job_data.get('total_upcs')) * 100
        print(f"\nProgress: {progress:.1f}%")
        
        # Estimate if stuck
        if job_data.get('status') == 'running' and updated_at and hasattr(updated_at, 'timestamp'):
            time_since = datetime.utcnow() - updated_at
            if time_since.total_seconds() > 300:  # More than 5 minutes
                print(f"\n⚠️  WARNING: Job appears to be stuck! No updates for {time_since}")
    
    return job_data

if __name__ == "__main__":
    job_id = "batch_20250822_044405_817434"
    job_data = check_batch_job(job_id)
    
    if job_data and job_data.get('status') in ['running', 'pending']:
        print("\n" + "=" * 60)
        print("Recommendation: This job appears to be frozen.")
        print("You may want to:")
        print("1. Mark it for recovery")
        print("2. Resume from the last checkpoint")
        print("3. Check Cloud Run logs for errors")
