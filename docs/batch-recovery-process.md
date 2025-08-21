# Batch Processing Recovery Documentation

## Overview
This document describes the batch processing recovery mechanisms implemented to handle Cloud Run instance terminations and other failure scenarios.

## Problem Statement
Previously, batch processing jobs were stored in memory, causing complete data loss when Cloud Run instances terminated. This resulted in:
- Incomplete batch processing (only 9 out of 42 UPCs processed in batch_20250821_145610_0)
- No way to resume interrupted batches
- Lost job status and results

## Solution Architecture

### 1. Firestore Persistence
All batch job state is now stored in Firestore under the `batch_jobs` collection with the following schema:

```json
{
  "job_id": "batch_20250821_145610_0",
  "status": "running|pending|completed|failed",
  "gcs_path": "gs://draft-maker-bucket/file.txt",
  "total_upcs": 42,
  "processed_upcs": 9,
  "successful_upcs": 3,
  "failed_upcs": 6,
  "last_processed_index": 8,
  "created_at": "2025-08-21T14:56:10Z",
  "started_at": "2025-08-21T14:56:10Z",
  "completed_at": null,
  "error": null,
  "results": [],
  "failed_upc_list": [],
  "checkpoints": []
}
```

### 2. Checkpointing System
- After each UPC is processed, a checkpoint is saved to Firestore
- Tracks `last_processed_index` to know where to resume
- Stores individual results and failed UPC list for retry

### 3. Resume Capability
When a batch job is restarted:
1. System checks `last_processed_index` from Firestore
2. Skips already processed UPCs
3. Continues processing from the next unprocessed UPC

## Recovery Procedures

### Automatic Recovery
If an instance terminates during processing:
1. New instance starts when API is called
2. Job state is retrieved from Firestore
3. Processing resumes from last checkpoint automatically

### Manual Recovery
To manually recover a failed or interrupted batch:

```bash
# 1. Check batch status
curl https://draft-maker-541660382374.us-west1.run.app/api/batch/status/{job_id}

# 2. List all batch jobs
curl https://draft-maker-541660382374.us-west1.run.app/api/batch/jobs

# 3. Recover a specific batch
curl -X POST https://draft-maker-541660382374.us-west1.run.app/api/batch/recover/{job_id}
```

### Creating a New Batch from Failed UPCs
If you need to reprocess only the failed UPCs:

1. Get the list of failed UPCs from the job:
```bash
curl https://draft-maker-541660382374.us-west1.run.app/api/batch/status/{job_id} \
  | jq '.results.failed_upc_list'
```

2. Create a new file with failed UPCs and upload to GCS
3. Start a new batch with the failed UPCs file

## API Endpoints

### Health Check
```
GET /health
```
Returns service health and Firestore connectivity status.

### Batch Processing
```
POST /api/batch/process
{
  "gcs_path": "gs://bucket/file.txt",
  "create_drafts": true,
  "test_mode": false
}
```
Starts a new batch processing job.

### Batch Status
```
GET /api/batch/status/{job_id}
```
Gets the current status and progress of a batch job.

### List Batch Jobs
```
GET /api/batch/jobs?limit=10&status=running
```
Lists all batch jobs with optional filtering.

### Recover Batch
```
POST /api/batch/recover/{job_id}
```
Manually recovers and restarts a failed or interrupted batch job.

## Monitoring

### Check Logs
```bash
# View Cloud Run logs
gcloud logging read 'resource.type="cloud_run_revision" AND jsonPayload.job_id="batch_id"' \
  --project=draft-maker-468923 --limit=50

# Check for errors
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=draft-maker-468923 --limit=20
```

### Firestore Console
View batch jobs directly in Firestore:
1. Go to [Firebase Console](https://console.firebase.google.com)
2. Select project `draft-maker-468923`
3. Navigate to Firestore Database
4. Browse `batch_jobs` collection

## Best Practices

1. **Monitor Long-Running Batches**: Check status periodically for batches with many UPCs
2. **Handle API Failures**: The system now handles Discogs 401 errors and eBay 500 errors gracefully
3. **Use Test Mode**: For testing, set `test_mode: true` to skip draft creation
4. **Batch Size**: Consider splitting very large batches (>1000 UPCs) into smaller chunks

## Troubleshooting

### Batch Stuck in "Running" State
If a batch shows as "running" but no progress is being made:
1. Check Cloud Run logs for errors
2. Use the recovery endpoint to restart the batch
3. The system will resume from the last checkpoint

### Missing Batch Jobs
If old batch jobs don't appear:
- Jobs created before the Firestore implementation were stored in memory and are lost
- Create a new batch with the same UPC file to reprocess

### Firestore Connection Issues
If health check shows Firestore as "disconnected":
1. Check service account permissions
2. Verify Firestore database exists in the correct region
3. Check Cloud Run service configuration

## Recovery Example: batch_20250821_145610_0

The original failed batch that prompted this implementation:
- Started: 2025-08-21 14:56:10 UTC
- Failed at: UPC index 8 (9th UPC)
- Total UPCs: 42
- Processed: 9 (3 successful, 6 failed)
- Unprocessed: 33

To recover this specific batch (if it existed in Firestore):
```bash
curl -X POST https://draft-maker-541660382374.us-west1.run.app/api/batch/recover/batch_20250821_145610_0
```

Since this batch was lost due to in-memory storage, you would need to:
1. Create a new batch with the same UPC file (gs://draft-maker-bucket/exu2.txt)
2. The new batch will process all 42 UPCs with proper persistence
