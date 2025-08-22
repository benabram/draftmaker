#!/usr/bin/env python3
"""
Manually mark a frozen batch job as failed and trigger recovery.
"""

import sys
from google.cloud import firestore
from datetime import datetime, timezone

# Initialize Firestore
db = firestore.Client(project="draft-maker-468923")

job_id = "batch_20250821_194312_619194"

# Update job status to failed
doc_ref = db.collection("batch_jobs").document(job_id)
doc_ref.update({
    "status": "failed",
    "error": "Job frozen - manually marked for recovery",
    "updated_at": datetime.now(timezone.utc)
})

print(f"Marked job {job_id} as failed for recovery")

# Now trigger recovery via API
import requests

recovery_url = f"https://draft-maker-541660382374.us-west1.run.app/api/batch/recover/{job_id}"
response = requests.post(recovery_url)

if response.status_code == 200:
    print(f"Successfully triggered recovery for job {job_id}")
    print(response.json())
else:
    print(f"Failed to trigger recovery: {response.status_code}")
    print(response.text)
