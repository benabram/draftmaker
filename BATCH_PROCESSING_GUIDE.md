# Batch Processing Guide - Draft Maker Production

## Overview
The Draft Maker application provides API endpoints to trigger batch processing of UPC codes stored in Google Cloud Storage (GCS). This guide shows you how to upload UPC files and trigger processing in the production environment.

## Prerequisites

1. **Production URL**: https://draft-maker-krce6hctoa-uw.a.run.app
2. **Google Cloud Storage Bucket**: `draft-maker-bucket`
3. **UPC file format**: Plain text file with one UPC per line

## Step 1: Prepare Your UPC File

Create a text file with UPC codes, one per line:

```
602537351169
828768352625
093624974680
602498815342
```

Save this as `upcs.txt` or any filename you prefer.

## Step 2: Upload File to Google Cloud Storage

### Option A: Using gsutil (Command Line)

```bash
# Upload to the draft-maker-bucket
gsutil cp upcs.txt gs://draft-maker-bucket/upcs.txt

# Or upload to a dated folder
gsutil cp upcs.txt gs://draft-maker-bucket/$(date +%Y%m%d)/upcs.txt
```

### Option B: Using Google Cloud Console

1. Go to https://console.cloud.google.com/storage/browser/draft-maker-bucket
2. Click "Upload Files"
3. Select your UPC file
4. Click "Upload"

## Step 3: Trigger Batch Processing

### Method 1: Using curl (Recommended)

```bash
# Basic batch processing request
curl -X POST https://draft-maker-krce6hctoa-uw.a.run.app/api/batch/process \
  -H "Content-Type: application/json" \
  -d '{
    "gcs_path": "gs://draft-maker-bucket/upcs.txt",
    "create_drafts": true,
    "test_mode": false
  }'
```

**Response Example:**
```json
{
  "job_id": "batch_20250819_013000_0",
  "status": "pending",
  "gcs_path": "gs://draft-maker-bucket/upcs.txt",
  "started_at": "2025-08-19T01:30:00",
  "total_upcs": null,
  "successful": null,
  "failed": null
}
```

### Method 2: Using the Trigger Script

If you're on your local machine with the repository:

```bash
# From the draftmaker directory
./scripts/trigger-batch-processing.sh \
  -g gs://draft-maker-bucket/upcs.txt \
  -m api \
  -u https://draft-maker-krce6hctoa-uw.a.run.app
```

### Method 3: Using Python

```python
import requests
import json

# API endpoint
url = "https://draft-maker-krce6hctoa-uw.a.run.app/api/batch/process"

# Request payload
payload = {
    "gcs_path": "gs://draft-maker-bucket/upcs.txt",
    "create_drafts": True,  # Set to False for metadata only
    "test_mode": False      # Set to True for testing without creating drafts
}

# Send request
response = requests.post(url, json=payload)

if response.status_code == 200:
    job_data = response.json()
    print(f"Job created: {job_data['job_id']}")
    print(f"Status: {job_data['status']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

## Step 4: Monitor Job Status

### Check Job Status

```bash
# Replace JOB_ID with the actual job ID from the response
curl https://draft-maker-krce6hctoa-uw.a.run.app/api/batch/status/batch_20250819_013000_0
```

**Response Example:**
```json
{
  "job_id": "batch_20250819_013000_0",
  "status": "completed",
  "gcs_path": "gs://draft-maker-bucket/upcs.txt",
  "started_at": "2025-08-19T01:30:00",
  "completed_at": "2025-08-19T01:32:45",
  "total_upcs": 50,
  "successful": 47,
  "failed": 3,
  "results": {
    "draft_ids": ["draft_1234", "draft_5678"],
    "errors": ["UPC 123456789012: Not found"]
  }
}
```

### List All Jobs

```bash
curl https://draft-maker-krce6hctoa-uw.a.run.app/api/batch/jobs
```

## Step 5: View Results

Results are stored in:
1. **Firestore Database**: Check the `draft_listings` collection
2. **Cloud Storage**: Output files in `gs://draft-maker-bucket/output/`
3. **eBay Account**: Draft listings appear in your eBay seller account

## API Parameters Explained

### BatchProcessRequest

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `gcs_path` | string | Yes | Full GCS path (must start with `gs://`) |
| `create_drafts` | boolean | No | Whether to create eBay drafts (default: true) |
| `test_mode` | boolean | No | Run in test mode without creating actual drafts (default: false) |

### Job Status Values

- **pending**: Job is queued for processing
- **running**: Currently processing UPCs
- **completed**: Successfully finished
- **failed**: Job failed with errors

## Automation Examples

### Scheduled Processing (using cron)

Add to your crontab to process daily at 2 AM:

```bash
0 2 * * * curl -X POST https://draft-maker-krce6hctoa-uw.a.run.app/api/batch/process \
  -H "Content-Type: application/json" \
  -d '{"gcs_path": "gs://draft-maker-bucket/daily/upcs.txt", "create_drafts": true}'
```

### Google Cloud Scheduler

Create a Cloud Scheduler job to trigger processing:

```bash
gcloud scheduler jobs create http trigger-draft-maker \
  --location=us-west1 \
  --schedule="0 2 * * *" \
  --uri="https://draft-maker-krce6hctoa-uw.a.run.app/api/batch/process" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"gcs_path":"gs://draft-maker-bucket/scheduled/upcs.txt","create_drafts":true}'
```

## Important Notes

1. **eBay OAuth**: Make sure eBay OAuth is configured by visiting:
   - https://draft-maker-krce6hctoa-uw.a.run.app/oauth/status
   - If not configured, visit: https://draft-maker-krce6hctoa-uw.a.run.app/oauth/authorize

2. **File Size Limits**: 
   - Maximum 10,000 UPCs per file recommended
   - Larger files may timeout (split into multiple files)

3. **Rate Limits**:
   - The application respects eBay API rate limits
   - Processing speed: ~1-2 UPCs per second

4. **Error Handling**:
   - Failed UPCs are logged but don't stop the batch
   - Check job status for detailed error information

## Troubleshooting

### Common Issues

1. **403 Forbidden Error**
   - The service is publicly accessible now
   - If you still get 403, check your request format

2. **File Not Found**
   - Verify the GCS path is correct
   - Ensure the file exists in the bucket
   - Check permissions on the bucket

3. **Job Stuck in Pending**
   - Check Cloud Run logs for errors
   - Verify service account permissions

### View Logs

```bash
# View Cloud Run logs
gcloud run services logs read draft-maker --region=us-west1 --limit=50

# View specific job logs (filter by job ID)
gcloud run services logs read draft-maker --region=us-west1 | grep "batch_20250819_013000_0"
```

## Support

For issues or questions:
- Check application status: https://draft-maker-krce6hctoa-uw.a.run.app/
- View API documentation: https://draft-maker-krce6hctoa-uw.a.run.app/docs
- Check OAuth status: https://draft-maker-krce6hctoa-uw.a.run.app/oauth/status
