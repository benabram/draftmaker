"""
Improvements for batch processing to handle instance terminations better.

Issues to fix:
1. Security: Discogs credentials exposed in logs
2. Stuck jobs: Detect jobs stuck in "running" state
3. Auto-recovery: Automatically recover stuck jobs
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from google.cloud import firestore

from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


class BatchHealthMonitor:
    """Monitor batch jobs and auto-recover stuck ones."""
    
    def __init__(self):
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.batch_collection = self.db.collection("batch_jobs")
        
    def check_stuck_jobs(self, timeout_minutes: int = 10) -> list:
        """
        Find jobs that are stuck in 'running' state.
        
        A job is considered stuck if:
        - Status is 'running'
        - Last update was more than timeout_minutes ago
        - No checkpoints in the last timeout_minutes
        
        Args:
            timeout_minutes: Minutes after which a job is considered stuck
            
        Returns:
            List of stuck job IDs
        """
        stuck_jobs = []
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        # Query for running jobs
        running_jobs = self.batch_collection.where("status", "==", "running").stream()
        
        for job_doc in running_jobs:
            job_data = job_doc.to_dict()
            job_id = job_data.get("job_id")
            
            # Check last update time
            last_update = job_data.get("updated_at")
            if isinstance(last_update, str):
                last_update = datetime.fromisoformat(last_update)
            
            if last_update and last_update < timeout_threshold:
                # Check if there are recent checkpoints
                checkpoints = job_data.get("checkpoints", [])
                if checkpoints:
                    # Get the most recent checkpoint
                    last_checkpoint = max(checkpoints, key=lambda x: x.get("timestamp", datetime.min))
                    checkpoint_time = last_checkpoint.get("timestamp")
                    
                    if isinstance(checkpoint_time, str):
                        checkpoint_time = datetime.fromisoformat(checkpoint_time)
                    
                    if checkpoint_time < timeout_threshold:
                        stuck_jobs.append(job_id)
                        logger.warning(f"Job {job_id} appears to be stuck (no checkpoint since {checkpoint_time})")
                else:
                    # No checkpoints and old update time
                    stuck_jobs.append(job_id)
                    logger.warning(f"Job {job_id} appears to be stuck (no checkpoints, last update: {last_update})")
        
        return stuck_jobs
    
    def mark_job_as_stuck(self, job_id: str) -> bool:
        """
        Mark a stuck job as failed so it can be recovered.
        
        Args:
            job_id: The job ID to mark as stuck
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.batch_collection.document(job_id)
            doc_ref.update({
                "status": "failed",
                "error": "Job stuck - instance likely terminated",
                "updated_at": datetime.utcnow()
            })
            logger.info(f"Marked job {job_id} as failed for recovery")
            return True
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as stuck: {e}")
            return False
    
    async def auto_recover_stuck_jobs(self, timeout_minutes: int = 10):
        """
        Automatically detect and recover stuck jobs.
        
        Args:
            timeout_minutes: Minutes after which a job is considered stuck
        """
        stuck_jobs = self.check_stuck_jobs(timeout_minutes)
        
        for job_id in stuck_jobs:
            logger.info(f"Auto-recovering stuck job: {job_id}")
            
            # Mark as failed first
            if self.mark_job_as_stuck(job_id):
                # Trigger recovery via API
                # Note: In production, this would call the recovery endpoint
                logger.info(f"Job {job_id} marked for recovery - call /api/batch/recover/{job_id}")
        
        return stuck_jobs


def sanitize_error_message(error_message: str) -> str:
    """
    Remove sensitive information from error messages before logging.
    
    Args:
        error_message: The original error message
        
    Returns:
        Sanitized error message
    """
    import re
    
    # Remove API keys and secrets from URLs
    # Pattern to match key=XXX or secret=XXX in URLs
    sanitized = re.sub(r'[?&](key|secret|token|api_key|apikey|password|auth)=[^&\s\'\"]+', 
                       r'&\1=***REDACTED***', 
                       error_message)
    
    # Remove authorization headers
    sanitized = re.sub(r'Authorization[:\s]+[^\s\'\"]+', 
                       'Authorization: ***REDACTED***', 
                       sanitized)
    
    # Remove any remaining potential secrets (long alphanumeric strings)
    # This is more aggressive but safer
    sanitized = re.sub(r'\b[a-zA-Z0-9]{20,}\b', 
                       '***POTENTIAL_SECRET_REDACTED***', 
                       sanitized)
    
    return sanitized


class RobustBatchProcessor:
    """
    Enhanced batch processor with better resilience to instance terminations.
    """
    
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.batch_collection = self.db.collection("batch_jobs")
        
    def heartbeat(self):
        """
        Update job timestamp to show it's still active.
        This helps distinguish between stuck jobs and actively running ones.
        """
        try:
            doc_ref = self.batch_collection.document(self.job_id)
            doc_ref.update({
                "last_heartbeat": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
        except Exception as e:
            logger.error(f"Failed to update heartbeat for job {self.job_id}: {e}")
    
    async def process_with_heartbeat(self, process_func, *args, **kwargs):
        """
        Run a processing function with periodic heartbeats.
        
        Args:
            process_func: The async function to run
            *args, **kwargs: Arguments for the function
        """
        async def heartbeat_task():
            """Background task to send heartbeats."""
            while True:
                self.heartbeat()
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
        
        # Start heartbeat task
        heartbeat = asyncio.create_task(heartbeat_task())
        
        try:
            # Run the actual processing
            result = await process_func(*args, **kwargs)
            return result
        finally:
            # Cancel heartbeat task
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass


# Example usage for monitoring script
async def monitor_and_recover():
    """
    Run this periodically (e.g., via Cloud Scheduler) to recover stuck jobs.
    """
    monitor = BatchHealthMonitor()
    stuck_jobs = await monitor.auto_recover_stuck_jobs(timeout_minutes=10)
    
    if stuck_jobs:
        logger.info(f"Found and marked {len(stuck_jobs)} stuck jobs for recovery")
        return stuck_jobs
    else:
        logger.info("No stuck jobs found")
        return []


if __name__ == "__main__":
    # Run the monitor
    asyncio.run(monitor_and_recover())
