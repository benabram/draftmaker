#!/bin/bash

# Deploy Batch Monitor Cloud Function and Cloud Scheduler Job

set -e

PROJECT_ID="draft-maker-468923"
REGION="us-west1"
FUNCTION_NAME="batch-health-monitor"
SCHEDULER_NAME="batch-monitor-scheduler"
CLOUD_RUN_URL="https://draft-maker-541660382374.us-west1.run.app"

echo "🚀 Deploying Batch Health Monitor..."

# 1. Deploy the Cloud Function
echo "📦 Deploying Cloud Function..."
gcloud functions deploy $FUNCTION_NAME \
  --gen2 \
  --runtime=python311 \
  --region=$REGION \
  --source=functions/batch_monitor \
  --entry-point=monitor_batch_jobs \
  --trigger-http \
  --allow-unauthenticated \
  --timeout=540s \
  --memory=512MB \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,CLOUD_RUN_URL=$CLOUD_RUN_URL,TIMEOUT_MINUTES=10" \
  --project=$PROJECT_ID

# Get the function URL
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(serviceConfig.uri)")

echo "✅ Cloud Function deployed at: $FUNCTION_URL"

# 2. Create Cloud Scheduler job
echo "⏰ Creating Cloud Scheduler job..."

# Delete existing scheduler if it exists
gcloud scheduler jobs delete $SCHEDULER_NAME \
  --location=$REGION \
  --project=$PROJECT_ID \
  --quiet || true

# Create new scheduler job (runs every 10 minutes)
gcloud scheduler jobs create http $SCHEDULER_NAME \
  --location=$REGION \
  --schedule="*/10 * * * *" \
  --uri=$FUNCTION_URL \
  --http-method=GET \
  --attempt-deadline=540s \
  --project=$PROJECT_ID

echo "✅ Cloud Scheduler job created"

# 3. Create Cloud Tasks queue for batch processing
echo "📋 Creating Cloud Tasks queue..."

# Delete existing queue if it exists
gcloud tasks queues delete batch-processing \
  --location=$REGION \
  --project=$PROJECT_ID \
  --quiet || true

# Create new queue with appropriate settings
gcloud tasks queues create batch-processing \
  --location=$REGION \
  --max-dispatches-per-second=1 \
  --max-concurrent-dispatches=3 \
  --max-attempts=3 \
  --min-backoff=10s \
  --max-backoff=300s \
  --project=$PROJECT_ID

echo "✅ Cloud Tasks queue created"

echo "
========================================
✅ Batch Monitor Deployment Complete!
========================================

Cloud Function: $FUNCTION_URL
Scheduler: Runs every 10 minutes
Cloud Tasks Queue: batch-processing

To test the monitor manually:
  curl $FUNCTION_URL

To check scheduler status:
  gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID

To check Cloud Tasks queue:
  gcloud tasks queues describe batch-processing --location=$REGION --project=$PROJECT_ID
"
