from google.cloud import firestore
from datetime import datetime

# Initialize Firestore
db = firestore.Client(project="draft-maker-468923")

# Get the batch job
job_id = "batch_20250821_153635_286507"
doc_ref = db.collection("batch_jobs").document(job_id)

# Update status to failed so we can recover it
doc_ref.update({
    "status": "failed",
    "error": "Instance terminated during processing - manual recovery",
    "updated_at": datetime.utcnow()
})

print(f"Updated job {job_id} status to 'failed' - now recovering...")

# Now trigger recovery
import requests
response = requests.post(f"https://draft-maker-541660382374.us-west1.run.app/api/batch/recover/{job_id}")
print(f"Recovery response: {response.status_code}")
if response.status_code == 200:
    print("Job recovery initiated successfully!")
    print(response.json())
else:
    print(f"Failed to recover: {response.text}")
