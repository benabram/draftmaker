#!/bin/bash

# Deploy Token Refresh Cloud Function and Scheduler
# This script deploys the automatic token refresh infrastructure

set -e

PROJECT_ID="draft-maker-468923"
REGION="us-west1"
FUNCTION_NAME="token-refresh"
SCHEDULER_JOB_NAME="token-refresh-scheduler"
SERVICE_ACCOUNT="draft-maker-identity@${PROJECT_ID}.iam.gserviceaccount.com"

echo "================================================"
echo "🚀 Deploying Token Refresh Infrastructure"
echo "================================================"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Set project
echo "Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Deploy Cloud Function
echo ""
echo "📦 Deploying Cloud Function..."
echo "--------------------------------"

cd functions/token_refresh

gcloud functions deploy ${FUNCTION_NAME} \
    --runtime python311 \
    --trigger-http \
    --entry-point token_refresh \
    --region ${REGION} \
    --service-account ${SERVICE_ACCOUNT} \
    --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID}" \
    --timeout 60s \
    --memory 256MB \
    --allow-unauthenticated

echo "✅ Cloud Function deployed successfully"

# Get the function URL
FUNCTION_URL=$(gcloud functions describe ${FUNCTION_NAME} --region ${REGION} --format="value(httpsTrigger.url)")
echo "Function URL: ${FUNCTION_URL}"

# Create Cloud Scheduler job
echo ""
echo "⏰ Setting up Cloud Scheduler..."
echo "--------------------------------"

# Enable Cloud Scheduler API if not already enabled
gcloud services enable cloudscheduler.googleapis.com

# Check if scheduler job exists
if gcloud scheduler jobs describe ${SCHEDULER_JOB_NAME} --location=${REGION} &>/dev/null; then
    echo "Updating existing scheduler job..."
    gcloud scheduler jobs update http ${SCHEDULER_JOB_NAME} \
        --location=${REGION} \
        --schedule="0 */1 * * *" \
        --uri="${FUNCTION_URL}" \
        --http-method=GET \
        --oidc-service-account-email=${SERVICE_ACCOUNT} \
        --description="Refresh OAuth tokens every hour"
else
    echo "Creating new scheduler job..."
    gcloud scheduler jobs create http ${SCHEDULER_JOB_NAME} \
        --location=${REGION} \
        --schedule="0 */1 * * *" \
        --uri="${FUNCTION_URL}" \
        --http-method=GET \
        --oidc-service-account-email=${SERVICE_ACCOUNT} \
        --description="Refresh OAuth tokens every hour"
fi

echo "✅ Cloud Scheduler job configured"

# Test the function
echo ""
echo "🧪 Testing the function..."
echo "--------------------------------"
echo "Would you like to test the token refresh function now? (y/n)"
read -r response

if [[ "$response" == "y" ]]; then
    echo "Triggering manual refresh..."
    curl -X GET "${FUNCTION_URL}"
    echo ""
    echo "✅ Test completed. Check logs for results:"
    echo "gcloud functions logs read ${FUNCTION_NAME} --region ${REGION}"
fi

echo ""
echo "================================================"
echo "✅ Deployment Complete!"
echo "================================================"
echo ""
echo "Token refresh infrastructure is now deployed:"
echo "• Cloud Function: ${FUNCTION_NAME}"
echo "• Scheduler Job: ${SCHEDULER_JOB_NAME}"
echo "• Schedule: Every hour at minute 0"
echo "• Function URL: ${FUNCTION_URL}"
echo ""
echo "To view logs:"
echo "  gcloud functions logs read ${FUNCTION_NAME} --region ${REGION}"
echo ""
echo "To manually trigger refresh:"
echo "  gcloud scheduler jobs run ${SCHEDULER_JOB_NAME} --location=${REGION}"
echo ""
