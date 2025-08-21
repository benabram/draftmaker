"""
Cloud Function to monitor and auto-recover stuck batch jobs.
This function should be triggered by Cloud Scheduler every 5-10 minutes.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import requests
from google.cloud import firestore

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "draft-maker-468923")
CLOUD_RUN_URL = os.environ.get("CLOUD_RUN_URL", "https://draft-maker-541660382374.us-west1.run.app")
TIMEOUT_MINUTES = int(os.environ.get("TIMEOUT_MINUTES", "10"))


class BatchHealthMonitor:
    """Monitor batch jobs and auto-recover stuck ones."""
    
    def __init__(self):
        self.db = firestore.Client(project=PROJECT_ID)
        self.batch_collection = self.db.collection("batch_jobs")
        
    def check_stuck_jobs(self, timeout_minutes: int = TIMEOUT_MINUTES) -> List[str]:
        """
        Find jobs that are stuck in 'running' state.
        
        A job is considered stuck if:
        - Status is 'running'
        - Last update was more than timeout_minutes ago
        - No recent heartbeat or checkpoints
        
        Args:
            timeout_minutes: Minutes after which a job is considered stuck
            
        Returns:
            List of stuck job IDs
        """
        stuck_jobs = []
        # Use timezone-aware datetime for comparison with Firestore timestamps
        timeout_threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        
        try:
            # Query for running jobs
            running_jobs = self.batch_collection.where("status", "==", "running").stream()
            
            for job_doc in running_jobs:
                job_data = job_doc.to_dict()
                job_id = job_data.get("job_id")
                
                # Check for heartbeat first (if implemented)
                last_heartbeat = job_data.get("last_heartbeat")
                if last_heartbeat:
                    if isinstance(last_heartbeat, str):
                        last_heartbeat = datetime.fromisoformat(last_heartbeat)
                    # Ensure heartbeat is timezone-aware
                    if last_heartbeat.tzinfo is None:
                        last_heartbeat = last_heartbeat.replace(tzinfo=timezone.utc)
                    if last_heartbeat > timeout_threshold:
                        logger.info(f"Job {job_id} has recent heartbeat, skipping")
                        continue
                
                # Check last update time
                last_update = job_data.get("updated_at")
                if isinstance(last_update, str):
                    last_update = datetime.fromisoformat(last_update)
                
                # Ensure last_update is timezone-aware
                if last_update and last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=timezone.utc)
                
                if last_update and last_update < timeout_threshold:
                    # Check if there are recent checkpoints
                    checkpoints = job_data.get("checkpoints", [])
                    if checkpoints:
                        # Get the most recent checkpoint
                        recent_checkpoint = False
                        for checkpoint in checkpoints[-5:]:  # Check last 5 checkpoints
                            checkpoint_time = checkpoint.get("timestamp")
                            if isinstance(checkpoint_time, str):
                                checkpoint_time = datetime.fromisoformat(checkpoint_time)
                            # Ensure checkpoint_time is timezone-aware
                            if checkpoint_time and checkpoint_time.tzinfo is None:
                                checkpoint_time = checkpoint_time.replace(tzinfo=timezone.utc)
                            if checkpoint_time and checkpoint_time > timeout_threshold:
                                recent_checkpoint = True
                                break
                        
                        if not recent_checkpoint:
                            stuck_jobs.append(job_id)
                            logger.warning(f"Job {job_id} appears to be stuck (no recent checkpoints)")
                    else:
                        # No checkpoints and old update time
                        stuck_jobs.append(job_id)
                        logger.warning(f"Job {job_id} appears to be stuck (no checkpoints, last update: {last_update})")
                        
        except Exception as e:
            logger.error(f"Error checking for stuck jobs: {e}")
        
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
                "error": "Job stuck - instance likely terminated (auto-detected)",
                "updated_at": datetime.now(timezone.utc)
            })
            logger.info(f"Marked job {job_id} as failed for recovery")
            return True
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as stuck: {e}")
            return False
    
    def recover_job(self, job_id: str) -> bool:
        """
        Call the Cloud Run recovery endpoint to restart a stuck job.
        
        Args:
            job_id: The job ID to recover
            
        Returns:
            True if recovery was triggered successfully
        """
        try:
            recovery_url = f"{CLOUD_RUN_URL}/api/batch/recover/{job_id}"
            response = requests.post(recovery_url, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Successfully triggered recovery for job {job_id}")
                return True
            else:
                logger.error(f"Failed to trigger recovery for job {job_id}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error triggering recovery for job {job_id}: {e}")
            return False
    
    def auto_recover_stuck_jobs(self) -> Dict[str, Any]:
        """
        Automatically detect and recover stuck jobs.
        
        Returns:
            Summary of actions taken
        """
        results = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "stuck_jobs": [],
            "recovered": [],
            "failed_to_recover": []
        }
        
        stuck_jobs = self.check_stuck_jobs()
        results["stuck_jobs"] = stuck_jobs
        
        for job_id in stuck_jobs:
            logger.info(f"Auto-recovering stuck job: {job_id}")
            
            # Mark as failed first
            if self.mark_job_as_stuck(job_id):
                # Trigger recovery via API
                if self.recover_job(job_id):
                    results["recovered"].append(job_id)
                else:
                    results["failed_to_recover"].append(job_id)
            else:
                results["failed_to_recover"].append(job_id)
        
        return results


def monitor_batch_jobs(request):
    """
    Cloud Function entry point for HTTP trigger.
    
    Args:
        request: Flask Request object
        
    Returns:
        JSON response with monitoring results
    """
    try:
        monitor = BatchHealthMonitor()
        results = monitor.auto_recover_stuck_jobs()
        
        if results["stuck_jobs"]:
            logger.info(f"Found {len(results['stuck_jobs'])} stuck jobs")
            logger.info(f"Recovered: {results['recovered']}")
            logger.info(f"Failed to recover: {results['failed_to_recover']}")
        else:
            logger.info("No stuck jobs found")
        
        return json.dumps(results), 200, {"Content-Type": "application/json"}
        
    except Exception as e:
        logger.error(f"Error in batch monitor: {e}")
        return json.dumps({"error": str(e)}), 500, {"Content-Type": "application/json"}


def monitor_batch_jobs_pubsub(event, context):
    """
    Cloud Function entry point for Pub/Sub trigger.
    
    Args:
        event: Pub/Sub message
        context: Event metadata
        
    Returns:
        None
    """
    try:
        monitor = BatchHealthMonitor()
        results = monitor.auto_recover_stuck_jobs()
        
        if results["stuck_jobs"]:
            logger.info(f"Found {len(results['stuck_jobs'])} stuck jobs")
            logger.info(f"Recovered: {results['recovered']}")
            logger.info(f"Failed to recover: {results['failed_to_recover']}")
        else:
            logger.info("No stuck jobs found")
            
    except Exception as e:
        logger.error(f"Error in batch monitor: {e}")
        raise
