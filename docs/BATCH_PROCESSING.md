# Batch Processing from Google Cloud Storage

This guide explains how to trigger batch processing of UPC codes stored in Google Cloud Storage (GCS) files in the Draft Maker staging environment.

## Overview

The Draft Maker application can process batches of UPC codes from text files stored in Google Cloud Storage. The processing includes:
1. Fetching metadata from various music databases
2. Getting pricing information
3. Retrieving album artwork
4. Creating draft listings on eBay

## Prerequisites

- Staging Docker container running (`draft-maker-staging`)
- Valid GCS service account credentials mounted in the container
- UPC text file uploaded to GCS bucket (`draft-maker-bucket`)
- eBay OAuth tokens configured (if creating drafts)

## File Format

The UPC file should be a plain text file with one UPC per line:
```
722975007524
638812705228
724383030422
```

## Methods to Trigger Batch Processing

There are three ways to trigger batch processing:

### Method 1: Using the API (Recommended)

The web API provides the most flexible way to trigger and monitor batch processing.

#### Trigger Processing
```bash
# Using the helper script
./scripts/trigger-batch-processing.sh -g gs://draft-maker-bucket/upcs.txt -m api

# Using curl directly
curl -X POST http://localhost:8080/api/batch/process \
  -H "Content-Type: application/json" \
  -d '{
    "gcs_path": "gs://draft-maker-bucket/upcs.txt",
    "create_drafts": true,
    "test_mode": false
  }'
```

#### Check Job Status
```bash
# Using the helper script
./scripts/trigger-batch-processing.sh -m api -s batch_20240318_143022_0

# Using curl
curl http://localhost:8080/api/batch/status/batch_20240318_143022_0
```

#### List All Jobs
```bash
# Using the helper script
./scripts/trigger-batch-processing.sh -m api -l

# Using curl
curl http://localhost:8080/api/batch/jobs
```

### Method 2: Using Docker Exec

Execute batch processing directly in the running container:

```bash
# Using the helper script
./scripts/trigger-batch-processing.sh -g gs://draft-maker-bucket/upcs.txt

# Using docker exec directly
docker exec -it draft-maker-staging python main.py gs://draft-maker-bucket/upcs.txt
```

### Method 3: Restart Container with Batch Mode

Stop the web server and run in batch mode:

```bash
# Stop current container
docker stop draft-maker-staging
docker rm draft-maker-staging

# Run in batch mode
docker run --rm \
  --name draft-maker-staging-batch \
  -e MODE=batch \
  -e INPUT_SOURCE=gs://draft-maker-bucket/upcs.txt \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-key.json \
  -v $(pwd)/.env.staging:/app/.env:ro \
  -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/output:/app/output \
  draft-maker-staging:latest
```

## Helper Script Usage

The `scripts/trigger-batch-processing.sh` script provides a convenient interface:

### Basic Usage
```bash
# Process UPCs from GCS
./scripts/trigger-batch-processing.sh -g gs://draft-maker-bucket/upcs.txt

# Process without creating eBay drafts (metadata only)
./scripts/trigger-batch-processing.sh -g gs://draft-maker-bucket/upcs.txt -d

# Run in test mode
./scripts/trigger-batch-processing.sh -g gs://draft-maker-bucket/upcs.txt -t
```

### API Operations
```bash
# Trigger via API
./scripts/trigger-batch-processing.sh -g gs://draft-maker-bucket/upcs.txt -m api

# Check job status
./scripts/trigger-batch-processing.sh -m api -s batch_20240318_143022_0

# List all jobs
./scripts/trigger-batch-processing.sh -m api -l
```

### Options
- `-g, --gcs-path`: GCS path to UPC file (required)
- `-m, --method`: Method to use: 'docker' or 'api' (default: docker)
- `-d, --no-drafts`: Don't create eBay drafts
- `-t, --test`: Run in test mode
- `-c, --container`: Docker container name (default: draft-maker-staging)
- `-u, --url`: API URL (default: http://localhost:8080)
- `-s, --status`: Check status of a specific job
- `-l, --list`: List all batch jobs
- `-h, --help`: Show help message

## Uploading Files to GCS

### Using gsutil
```bash
# Install gsutil if not already installed
# https://cloud.google.com/storage/docs/gsutil_install

# Authenticate
gcloud auth login

# Upload file
gsutil cp local_upcs.txt gs://draft-maker-bucket/upcs.txt

# List files in bucket
gsutil ls gs://draft-maker-bucket/
```

### Using gcloud CLI
```bash
# Upload file
gcloud storage cp local_upcs.txt gs://draft-maker-bucket/upcs.txt

# List files
gcloud storage ls gs://draft-maker-bucket/
```

## Monitoring Progress

### Via Container Logs
```bash
# Follow container logs
docker logs -f draft-maker-staging

# View last 100 lines
docker logs --tail 100 draft-maker-staging
```

### Via API Status Endpoint
```bash
# Check specific job
curl http://localhost:8080/api/batch/status/JOB_ID | python3 -m json.tool
```

### Output Files
Results are saved to the `output/` directory:
```bash
# List output files
ls -la output/

# View results
cat output/batch_results_TIMESTAMP.json
```

## Results Structure

The batch processing returns a JSON structure with:
```json
{
  "job_id": "batch_20240318_143022_0",
  "status": "completed",
  "gcs_path": "gs://draft-maker-bucket/upcs.txt",
  "started_at": "2024-03-18T14:30:22.123Z",
  "completed_at": "2024-03-18T14:35:45.678Z",
  "total_upcs": 10,
  "successful": 8,
  "failed": 2,
  "results": {
    "input_source": "gs://draft-maker-bucket/upcs.txt",
    "source_type": "gcs",
    "success_rate": 80.0,
    "processing_time_seconds": 323.5,
    "results": [...]
  }
}
```

## Troubleshooting

### Container Not Running
```bash
# Check container status
docker ps -a | grep draft-maker

# Start container if stopped
docker start draft-maker-staging

# View container logs
docker logs draft-maker-staging
```

### Authentication Issues
```bash
# Verify service account key is mounted
docker exec draft-maker-staging ls -la /app/service-account-key.json

# Check environment variable
docker exec draft-maker-staging env | grep GOOGLE_APPLICATION_CREDENTIALS
```

### GCS Access Issues
```bash
# Test GCS access from container
docker exec draft-maker-staging python -c "
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('draft-maker-bucket')
for blob in bucket.list_blobs():
    print(blob.name)
"
```

### API Not Responding
```bash
# Check if web server is running
curl http://localhost:8080/health

# Restart container
docker restart draft-maker-staging

# Check port binding
docker port draft-maker-staging
```

## Best Practices

1. **File Size**: Keep UPC files under 1000 entries for optimal processing
2. **Rate Limiting**: The system includes delays between API calls to avoid rate limiting
3. **Error Handling**: Failed UPCs are logged but don't stop the batch
4. **Testing**: Always test with a small batch first using `-t` flag
5. **Monitoring**: Use the API status endpoint to monitor long-running jobs

## Security Notes

- Service account credentials are mounted read-only
- API endpoints are only accessible locally (not exposed externally)
- Sensitive data in logs is minimized
- GCS bucket should have appropriate IAM permissions

## Examples

### Complete Workflow Example
```bash
# 1. Upload UPC file to GCS
gsutil cp my_upcs.txt gs://draft-maker-bucket/batch_$(date +%Y%m%d).txt

# 2. Trigger processing via API
./scripts/trigger-batch-processing.sh \
  -g gs://draft-maker-bucket/batch_$(date +%Y%m%d).txt \
  -m api

# 3. Monitor progress (replace with actual job ID)
./scripts/trigger-batch-processing.sh -m api -s batch_20240318_143022_0

# 4. Check results
ls -la output/
cat output/batch_results_*.json | jq '.summary'
```

### Test Mode Example
```bash
# Create test file with a few UPCs
echo "722975007524" > test_upcs.txt
echo "638812705228" >> test_upcs.txt

# Upload to GCS
gsutil cp test_upcs.txt gs://draft-maker-bucket/test.txt

# Run in test mode
./scripts/trigger-batch-processing.sh \
  -g gs://draft-maker-bucket/test.txt \
  -t
```

## Related Documentation

- [Staging Deployment Guide](STAGING_DEPLOYMENT.md)
- [Google Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [Draft Maker API Reference](API_REFERENCE.md)
