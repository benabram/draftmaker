# Google Cloud Run Deployment - Manual Execution

## Overview

Deploy the eBay Draft Maker to Google Cloud Run as a manually-triggered job. This is perfect for:

- **On-demand processing** - Run whenever you have new UPCs to process
- **Cost efficiency** - Only pay when the job runs (typically < $0.10 per run)
- **No maintenance** - Serverless, no infrastructure to manage
- **Secure** - API keys stored in Google Secret Manager

## Quick Start

### Prerequisites

1. **Google Cloud Account** with billing enabled
2. **Local tools installed:**
   ```bash
   # Install gcloud CLI
   curl https://sdk.cloud.google.com | bash
   
   # Install Docker Desktop
   # Visit: https://docs.docker.com/get-docker/
   ```
3. **API Keys ready:**
   - Spotify Client ID & Secret
   - eBay App ID, Cert ID, Dev ID, and Refresh Token

### Deploy in 5 Minutes

```bash
# Clone the repository
git clone <repository-url>
cd draftmaker

# Make deployment script executable
chmod +x deploy-cloudrun.sh

# Run deployment (choose option 1 for first time)
./deploy-cloudrun.sh
```

The script will:
1. Check prerequisites
2. Enable required Google Cloud APIs
3. Securely store your API keys
4. Ask for your existing GCS bucket name
5. Build and deploy the container
6. Show you how to run the job

## Usage

### 1. Upload Your UPC File

Create a text file with one UPC per line:
```
602537351169
828768352625
093624974680
```

Upload to your bucket:
```bash
gsutil cp your_upcs.txt gs://YOUR_BUCKET/upcs/batch.txt
```

### 2. Run the Job

```bash
# Quick run (returns immediately)
gcloud run jobs execute ebay-draftmaker-job --region=us-central1

# Run and wait for completion (see output)
gcloud run jobs execute ebay-draftmaker-job --region=us-central1 --wait
```

### 3. Get Results

```bash
# List output files
gsutil ls -l gs://YOUR_BUCKET/output/

# Download all results
gsutil -m cp -r gs://YOUR_BUCKET/output/ ./results/

# Download specific file
gsutil cp gs://YOUR_BUCKET/output/drafts_20240115_143022.json .
```

## Monitoring

### View Logs

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=ebay-draftmaker-job" --limit=50

# Stream logs during execution
gcloud alpha run jobs logs tail ebay-draftmaker-job --region=us-central1
```

### Check Job Status

```bash
# View job details
gcloud run jobs describe ebay-draftmaker-job --region=us-central1

# List recent executions
gcloud run jobs executions list --job=ebay-draftmaker-job --region=us-central1
```

## Common Tasks

### Update Code

After making changes to your code:
```bash
./deploy-cloudrun.sh
# Choose option 2: Update code only
```

### Update API Keys

If you need to change API credentials:
```bash
./deploy-cloudrun.sh
# Choose option 3: Update secrets only
```

### Process Different UPC Files

You can have multiple UPC files in your bucket:
```bash
# Upload different files
gsutil cp music_upcs.txt gs://YOUR_BUCKET/upcs/music_batch.txt
gsutil cp vinyl_upcs.txt gs://YOUR_BUCKET/upcs/vinyl_batch.txt

# Update job to process different file
gcloud run jobs update ebay-draftmaker-job \
    --args="--gcs-path,gs://YOUR_BUCKET/upcs/music_batch.txt" \
    --region=us-central1

# Run the job
gcloud run jobs execute ebay-draftmaker-job --region=us-central1
```

## Cost Optimization

### Typical Costs

- **Per run**: ~$0.05-0.10 for 100 UPCs
- **Storage**: ~$0.02/GB per month
- **Secrets**: Free (up to 6 secrets)

### Tips to Minimize Costs

1. **Process in batches** - Combine UPCs into larger files
2. **Clean up old results** - Delete processed output files
   ```bash
   # Delete files older than 30 days
   gsutil -m rm gs://YOUR_BUCKET/output/**_2024*.json
   ```
3. **Optimize resources** - Adjust memory if needed
   ```bash
   gcloud run jobs update ebay-draftmaker-job --memory=1Gi
   ```

## Troubleshooting

### Job Fails Immediately

Check logs for the specific error:
```bash
gcloud logging read "resource.type=cloud_run_job" --limit=100 --format=json | jq '.textPayload'
```

### Permission Errors

Ensure service account has necessary permissions:
```bash
# Grant storage access
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:ebay-draftmaker-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

### Timeout Issues

Increase timeout if processing large batches:
```bash
gcloud run jobs update ebay-draftmaker-job --task-timeout=3600
```

### API Rate Limiting

Reduce batch size in config.ini before rebuilding:
```ini
[Processing]
batch_size = 5  # Reduce from 10
max_workers = 2  # Reduce from 4
```

## Cleanup

To remove all resources:

```bash
# Delete the job
gcloud run jobs delete ebay-draftmaker-job --region=us-central1

# Delete secrets (optional - you might want to keep these)
gcloud secrets delete spotify-client-id
gcloud secrets delete spotify-client-secret
gcloud secrets delete ebay-app-id
gcloud secrets delete ebay-cert-id
gcloud secrets delete ebay-dev-id
gcloud secrets delete ebay-refresh-token

# Note: Keep your GCS bucket as it likely contains other data
```

## Advanced Usage

### Running with Different Parameters

You can override the default batch.txt file:

```bash
# Create a custom execution
gcloud run jobs execute ebay-draftmaker-job \
    --region=us-central1 \
    --args="--gcs-path,gs://YOUR_BUCKET/upcs/custom.txt" \
    --wait
```

### Parallel Processing

For very large batches, you can run multiple jobs:

```bash
# Split your UPC file into parts
split -l 100 large_upcs.txt part_

# Upload parts
for file in part_*; do
    gsutil cp $file gs://YOUR_BUCKET/upcs/
done

# Run multiple jobs
for file in part_*; do
    gcloud run jobs execute ebay-draftmaker-job \
        --region=us-central1 \
        --args="--gcs-path,gs://YOUR_BUCKET/upcs/$file" &
done
```

## Support

1. Check the logs first - they usually indicate the issue
2. Verify your API keys are correct and not expired
3. Ensure your GCS bucket has the correct structure
4. Review Google Cloud Status: https://status.cloud.google.com/
