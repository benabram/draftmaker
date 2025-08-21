"""
Batch job manager with Firestore persistence.
Handles storage and retrieval of batch processing jobs in Firestore.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
import json

from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)


class BatchJobManager:
    """Manages batch job state in Firestore."""
    
    def __init__(self):
        """Initialize Firestore client and collection reference."""
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.collection_name = "batch_jobs"
        self.collection = self.db.collection(self.collection_name)
        
    def create_job(
        self,
        job_id: str,
        gcs_path: str,
        total_upcs: int = 0,
        create_drafts: bool = True,
        test_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new batch job in Firestore.
        
        Args:
            job_id: Unique identifier for the job
            gcs_path: GCS path to the UPC file
            total_upcs: Total number of UPCs to process
            create_drafts: Whether to create eBay drafts
            test_mode: Whether running in test mode
            
        Returns:
            The created job document
        """
        job_data = {
            "job_id": job_id,
            "status": "pending",
            "gcs_path": gcs_path,
            "total_upcs": total_upcs,
            "processed_upcs": 0,
            "successful_upcs": 0,
            "failed_upcs": 0,
            "last_processed_index": -1,
            "create_drafts": create_drafts,
            "test_mode": test_mode,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "error": None,
            "results": [],
            "failed_upc_list": [],
            "checkpoints": []
        }
        
        try:
            # Create document with job_id as document ID
            self.collection.document(job_id).set(job_data)
            logger.info(f"Created batch job {job_id} in Firestore")
            return job_data
        except Exception as e:
            logger.error(f"Failed to create batch job {job_id}: {e}")
            raise
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a batch job from Firestore.
        
        Args:
            job_id: The job ID to retrieve
            
        Returns:
            Job document or None if not found
        """
        try:
            doc = self.collection.document(job_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve batch job {job_id}: {e}")
            return None
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a batch job in Firestore.
        
        Args:
            job_id: The job ID to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Always update the updated_at timestamp
            updates["updated_at"] = datetime.utcnow()
            
            self.collection.document(job_id).update(updates)
            logger.debug(f"Updated batch job {job_id} with {list(updates.keys())}")
            return True
        except Exception as e:
            logger.error(f"Failed to update batch job {job_id}: {e}")
            return False
    
    def update_job_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None
    ) -> bool:
        """
        Update the status of a batch job.
        
        Args:
            job_id: The job ID to update
            status: New status (pending, running, completed, failed, paused)
            error: Optional error message if status is failed
            
        Returns:
            True if successful, False otherwise
        """
        updates = {"status": status}
        
        if status == "running" and self.get_job(job_id).get("started_at") is None:
            updates["started_at"] = datetime.utcnow()
        elif status in ["completed", "failed"]:
            updates["completed_at"] = datetime.utcnow()
        
        if error:
            updates["error"] = error
            
        return self.update_job(job_id, updates)
    
    def add_checkpoint(
        self,
        job_id: str,
        upc_index: int,
        upc: str,
        success: bool,
        result: Dict[str, Any]
    ) -> bool:
        """
        Add a checkpoint after processing a UPC.
        
        Args:
            job_id: The job ID
            upc_index: Index of the UPC in the batch
            upc: The UPC that was processed
            success: Whether processing was successful
            result: Processing result for the UPC
            
        Returns:
            True if successful, False otherwise
        """
        try:
            job = self.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found for checkpoint")
                return False
            
            # Update counters
            updates = {
                "processed_upcs": job.get("processed_upcs", 0) + 1,
                "last_processed_index": upc_index
            }
            
            if success:
                updates["successful_upcs"] = job.get("successful_upcs", 0) + 1
            else:
                updates["failed_upcs"] = job.get("failed_upcs", 0) + 1
                # Add to failed UPC list for potential retry
                self.collection.document(job_id).update({
                    "failed_upc_list": firestore.ArrayUnion([{
                        "upc": upc,
                        "index": upc_index,
                        "error": result.get("error"),
                        "timestamp": datetime.utcnow()
                    }])
                })
            
            # Add result to results array
            self.collection.document(job_id).update({
                "results": firestore.ArrayUnion([result])
            })
            
            # Update main counters
            self.update_job(job_id, updates)
            
            # Add checkpoint record
            checkpoint = {
                "upc_index": upc_index,
                "upc": upc,
                "success": success,
                "timestamp": datetime.utcnow()
            }
            
            self.collection.document(job_id).update({
                "checkpoints": firestore.ArrayUnion([checkpoint])
            })
            
            logger.debug(f"Added checkpoint for job {job_id} at index {upc_index}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add checkpoint for job {job_id}: {e}")
            return False
    
    def get_resume_index(self, job_id: str) -> int:
        """
        Get the index to resume processing from.
        
        Args:
            job_id: The job ID
            
        Returns:
            Index to resume from (last_processed_index + 1), or 0 if starting fresh
        """
        job = self.get_job(job_id)
        if not job:
            return 0
        
        last_index = job.get("last_processed_index", -1)
        return last_index + 1
    
    def list_jobs(
        self,
        limit: int = 10,
        status: Optional[str] = None,
        order_by: str = "created_at",
        descending: bool = True
    ) -> List[Dict[str, Any]]:
        """
        List batch jobs with optional filtering.
        
        Args:
            limit: Maximum number of jobs to return
            status: Optional status filter
            order_by: Field to order by
            descending: Whether to order descending
            
        Returns:
            List of job documents
        """
        try:
            query = self.collection
            
            if status:
                query = query.where(filter=FieldFilter("status", "==", status))
            
            # Firestore ordering
            direction = firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING
            query = query.order_by(order_by, direction=direction)
            
            if limit > 0:
                query = query.limit(limit)
            
            jobs = []
            for doc in query.stream():
                job_data = doc.to_dict()
                # Convert datetime objects to ISO format strings for JSON serialization
                for field in ["created_at", "updated_at", "started_at", "completed_at"]:
                    if field in job_data and job_data[field]:
                        if hasattr(job_data[field], 'isoformat'):
                            job_data[field] = job_data[field].isoformat()
                jobs.append(job_data)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to list batch jobs: {e}")
            return []
    
    def get_failed_upcs(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get list of failed UPCs for a job.
        
        Args:
            job_id: The job ID
            
        Returns:
            List of failed UPC records
        """
        job = self.get_job(job_id)
        if not job:
            return []
        
        return job.get("failed_upc_list", [])
    
    def mark_job_for_recovery(self, job_id: str) -> bool:
        """
        Mark a job for recovery/retry.
        
        Args:
            job_id: The job ID to mark for recovery
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_job_status(job_id, "pending", error=None)


# Singleton instance
_batch_job_manager = None


def get_batch_job_manager() -> BatchJobManager:
    """Get or create the singleton BatchJobManager instance."""
    global _batch_job_manager
    if _batch_job_manager is None:
        _batch_job_manager = BatchJobManager()
    return _batch_job_manager
