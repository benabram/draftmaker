#!/usr/bin/env python3
"""
Fix for the batch recovery endpoint to prevent race conditions and infinite recovery loops.
This file contains the improved recovery logic that should replace the current implementation.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from google.cloud import firestore
from fastapi import HTTPException, BackgroundTasks
import logging

logger = logging.getLogger(__name__)

# Maximum number of recovery attempts before giving up
MAX_RECOVERY_ATTEMPTS = 3

async def recover_batch_job_fixed(
    job_id: str,
    batch_job_manager,
    background_tasks: BackgroundTasks
):
    """
    Improved recovery endpoint with atomic transactions and recovery limits.
    
    This function should replace the current recover_batch_job endpoint in app.py.
    It uses Firestore transactions to atomically check and update job status,
    preventing race conditions between the monitor and recovery processes.
    """
    
    db = firestore.Client(project='draft-maker-468923')
    
    # Use a transaction to atomically check and update the job
    @firestore.transactional
    def atomic_recovery(transaction, job_ref):
        # Get the job document within the transaction
        job_snapshot = job_ref.get(transaction=transaction)
        
        if not job_snapshot.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )
        
        job = job_snapshot.to_dict()
        
        # Check if job is already completed
        if job.get("status") == "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} is already completed"
            )
        
        # Check recovery attempt count
        recovery_attempts = job.get("recovery_attempts", 0)
        if recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
            # Mark as permanently failed
            transaction.update(job_ref, {
                "status": "failed",
                "error": f"Maximum recovery attempts ({MAX_RECOVERY_ATTEMPTS}) exceeded",
                "updated_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc)
            })
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} has exceeded maximum recovery attempts"
            )
        
        # Check if job is currently running
        if job.get("status") == "running":
            # Check if it's genuinely stuck (no updates for more than 10 minutes)
            last_update = job.get("updated_at")
            if last_update:
                if isinstance(last_update, str):
                    last_update = datetime.fromisoformat(last_update)
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=timezone.utc)
                
                time_since_update = datetime.now(timezone.utc) - last_update
                if time_since_update.total_seconds() < 600:  # Less than 10 minutes
                    raise HTTPException(
                        status_code=400,
                        detail=f"Job {job_id} is still actively running (last update: {time_since_update.total_seconds():.0f} seconds ago)"
                    )
        
        # Proceed with recovery - atomically update the job status
        transaction.update(job_ref, {
            "status": "pending",  # Set to pending for re-processing
            "error": None,  # Clear any previous error
            "recovery_attempts": recovery_attempts + 1,
            "last_recovery_attempt": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "recovery_history": firestore.ArrayUnion([{
                "attempt": recovery_attempts + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "previous_status": job.get("status"),
                "previous_error": job.get("error")
            }])
        })
        
        return job
    
    try:
        # Get job reference
        job_ref = db.collection('batch_jobs').document(job_id)
        
        # Execute the transaction
        transaction = db.transaction()
        job = atomic_recovery(transaction, job_ref)
        
        # If transaction succeeded, add background task to resume processing
        from app import run_batch_processing_task  # Import the actual function
        
        background_tasks.add_task(
            run_batch_processing_task,
            job_id,
            job.get("gcs_path"),
            job.get("create_drafts", True),
            job.get("test_mode", False)
        )
        
        logger.info(f"Batch job {job_id} successfully marked for recovery (attempt {job.get('recovery_attempts', 0) + 1}/{MAX_RECOVERY_ATTEMPTS})")
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": f"Job queued for recovery (attempt {job.get('recovery_attempts', 0) + 1}/{MAX_RECOVERY_ATTEMPTS})",
            "gcs_path": job.get("gcs_path"),
            "total_upcs": job.get("total_upcs"),
            "processed_upcs": job.get("processed_upcs", 0),
            "successful_upcs": job.get("successful_upcs", 0),
            "failed_upcs": job.get("failed_upcs", 0)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to recover job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during recovery: {str(e)}"
        )


def mark_job_for_recovery_fixed(batch_job_manager, job_id: str) -> bool:
    """
    Improved mark_job_for_recovery method with transaction support.
    This should be added to the BatchJobManager class.
    """
    db = firestore.Client(project='draft-maker-468923')
    
    @firestore.transactional
    def atomic_mark_for_recovery(transaction, job_ref):
        job_snapshot = job_ref.get(transaction=transaction)
        
        if not job_snapshot.exists:
            return False
        
        job = job_snapshot.to_dict()
        
        # Only mark for recovery if not already running or completed
        if job.get("status") in ["running", "completed"]:
            return False
        
        transaction.update(job_ref, {
            "status": "pending",
            "error": None,
            "updated_at": datetime.now(timezone.utc),
            "marked_for_recovery": datetime.now(timezone.utc)
        })
        
        return True
    
    try:
        job_ref = db.collection('batch_jobs').document(job_id)
        transaction = db.transaction()
        return atomic_mark_for_recovery(transaction, job_ref)
    except Exception as e:
        logger.error(f"Failed to mark job {job_id} for recovery: {e}")
        return False


# Additional helper function to check if a job needs recovery
def check_job_needs_recovery(job_data: Dict[str, Any]) -> bool:
    """
    Determine if a job needs recovery based on its state.
    
    Args:
        job_data: The job document from Firestore
        
    Returns:
        True if the job needs recovery, False otherwise
    """
    status = job_data.get("status")
    
    # Don't recover completed jobs
    if status == "completed":
        return False
    
    # Check recovery attempts
    recovery_attempts = job_data.get("recovery_attempts", 0)
    if recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
        return False
    
    # If failed, always allow recovery (up to the limit)
    if status == "failed":
        return True
    
    # If running, check if it's stuck
    if status == "running":
        last_update = job_data.get("updated_at")
        if last_update:
            if isinstance(last_update, str):
                last_update = datetime.fromisoformat(last_update)
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)
            
            time_since_update = datetime.now(timezone.utc) - last_update
            # Consider stuck if no update for more than 10 minutes
            if time_since_update.total_seconds() > 600:
                return True
    
    # If pending for too long
    if status == "pending":
        created_at = job_data.get("created_at")
        if created_at:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            time_since_creation = datetime.now(timezone.utc) - created_at
            # Consider stuck if pending for more than 5 minutes
            if time_since_creation.total_seconds() > 300:
                return True
    
    return False
