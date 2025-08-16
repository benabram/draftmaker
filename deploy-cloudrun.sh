#!/bin/bash

# eBay Draft Maker - Google Cloud Run Deployment
# Deploys as a Cloud Run Job with Cloud Scheduler for batch processing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ebay-draftmaker"
REGION="${REGION:-us-central1}"
SERVICE_ACCOUNT_NAME="${PROJECT_NAME}-sa"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_message $YELLOW "Checking prerequisites..."
    
    # Check gcloud CLI
    if ! command -v gcloud &> /dev/null; then
        print_message $RED "Error: gcloud CLI not found"
        print_message $YELLOW "Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_message $RED "Error: Docker not found"
        print_message $YELLOW "Install from: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # Check if logged in to gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
        print_message $YELLOW "Please authenticate with gcloud:"
        gcloud auth login
    fi
    
    # Get/Set project ID
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        print_message $YELLOW "No project set. Available projects:"
        gcloud projects list --format="table(projectId,name)"
        read -p "Enter project ID: " PROJECT_ID
        gcloud config set project $PROJECT_ID
    fi
    
    print_message $GREEN "Using project: $PROJECT_ID"
    print_message $GREEN "Prerequisites check passed"
}

# Enable required APIs
enable_apis() {
    print_message $YELLOW "Enabling required Google Cloud APIs..."
    
    gcloud services enable \
        run.googleapis.com \
        cloudbuild.googleapis.com \
        secretmanager.googleapis.com \
        artifactregistry.googleapis.com \
        storage.googleapis.com
    
    print_message $GREEN "APIs enabled"
}

# Create service account
setup_service_account() {
    print_message $YELLOW "Setting up service account..."
    
    # Create service account if it doesn't exist
    if ! gcloud iam service-accounts describe ${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com &>/dev/null; then
        gcloud iam service-accounts create ${SERVICE_ACCOUNT_NAME} \
            --display-name="eBay Draft Maker Service Account"
    fi
    
    # Grant necessary roles
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/run.invoker" \
        --condition=None
    
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/storage.objectViewer" \
        --condition=None
    
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor" \
        --condition=None
    
    print_message $GREEN "Service account configured"
}

# Setup secrets in Secret Manager
setup_secrets() {
    print_message $YELLOW "Setting up secrets in Secret Manager..."
    
    # Function to create or update a secret
    create_secret() {
        local secret_name=$1
        local prompt_text=$2
        
        # Check if secret exists
        if gcloud secrets describe $secret_name &>/dev/null; then
            print_message $BLUE "Secret $secret_name already exists"
            read -p "Update it? (y/n): " update_secret
            if [ "$update_secret" != "y" ]; then
                return
            fi
        else
            gcloud secrets create $secret_name --replication-policy="automatic"
        fi
        
        # Get secret value
        read -sp "$prompt_text: " secret_value
        echo
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    }
    
    # Create each required secret
    create_secret "spotify-client-id" "Enter Spotify Client ID"
    create_secret "spotify-client-secret" "Enter Spotify Client Secret"
    create_secret "ebay-app-id" "Enter eBay App ID"
    create_secret "ebay-cert-id" "Enter eBay Cert ID"
    create_secret "ebay-dev-id" "Enter eBay Dev ID"
    create_secret "ebay-refresh-token" "Enter eBay Refresh Token"
    
    print_message $GREEN "Secrets configured"
}

# Setup GCS bucket for UPC files
setup_storage() {
    print_message $YELLOW "Configuring Cloud Storage bucket..."
    
    # Ask for bucket name
    print_message $BLUE "Enter your existing GCS bucket name (or press Enter for default):"
    read -p "Bucket name [${PROJECT_ID}-${PROJECT_NAME}-data]: " USER_BUCKET
    BUCKET_NAME="${USER_BUCKET:-${PROJECT_ID}-${PROJECT_NAME}-data}"
    
    # Check if bucket exists
    if gsutil ls -b gs://${BUCKET_NAME} &>/dev/null; then
        print_message $GREEN "Using existing bucket: gs://${BUCKET_NAME}"
    else
        print_message $YELLOW "Bucket not found. Create it? (y/n)"
        read -p "Create bucket: " create_bucket
        if [ "$create_bucket" = "y" ]; then
            gsutil mb -p ${PROJECT_ID} -l ${REGION} gs://${BUCKET_NAME}
            print_message $GREEN "Created bucket: gs://${BUCKET_NAME}"
        else
            print_message $RED "Bucket required for deployment. Exiting."
            exit 1
        fi
    fi
    
    # Ensure directories exist
    echo "" > /tmp/empty.txt
    gsutil -q cp /tmp/empty.txt gs://${BUCKET_NAME}/upcs/ 2>/dev/null || true
    gsutil -q cp /tmp/empty.txt gs://${BUCKET_NAME}/output/ 2>/dev/null || true
    rm /tmp/empty.txt
    
    # Upload sample UPC file if it exists
    if [ -f "data/test_upcs.txt" ]; then
        gsutil cp data/test_upcs.txt gs://${BUCKET_NAME}/upcs/sample.txt
        print_message $GREEN "Uploaded sample UPC file to gs://${BUCKET_NAME}/upcs/sample.txt"
    fi
    
    # Export for use in other functions
    export BUCKET_NAME
    
    print_message $GREEN "Storage bucket configured"
}

# Build and push Docker image
build_and_push_image() {
    print_message $YELLOW "Building and pushing Docker image..."
    
    # Configure docker for gcloud
    gcloud auth configure-docker ${REGION}-docker.pkg.dev
    
    # Create Artifact Registry repository if it doesn't exist
    REPOSITORY="cloud-run-source-deploy"
    if ! gcloud artifacts repositories describe $REPOSITORY --location=$REGION &>/dev/null; then
        gcloud artifacts repositories create $REPOSITORY \
            --repository-format=docker \
            --location=$REGION
    fi
    
    # Build and push image
    IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${PROJECT_NAME}:latest"
    
    docker build -f Dockerfile.production -t ${IMAGE_URL} .
    docker push ${IMAGE_URL}
    
    print_message $GREEN "Docker image pushed: ${IMAGE_URL}"
}

# Deploy Cloud Run Job
deploy_cloud_run_job() {
    print_message $YELLOW "Deploying Cloud Run Job..."
    
    IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${PROJECT_NAME}:latest"
    
    # Use the bucket name from setup_storage or ask for it
    if [ -z "$BUCKET_NAME" ]; then
        print_message $BLUE "Enter your GCS bucket name:"
        read -p "Bucket name: " BUCKET_NAME
    fi
    
    # Create or update the job
    gcloud run jobs create ${PROJECT_NAME}-job \
        --image=${IMAGE_URL} \
        --region=${REGION} \
        --memory=2Gi \
        --cpu=2 \
        --task-timeout=3600 \
        --max-retries=1 \
        --parallelism=1 \
        --service-account=${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
        --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO,GCS_BUCKET=${BUCKET_NAME}" \
        --set-secrets="SPOTIFY_CLIENT_ID=spotify-client-id:latest" \
        --set-secrets="SPOTIFY_CLIENT_SECRET=spotify-client-secret:latest" \
        --set-secrets="EBAY_APP_ID=ebay-app-id:latest" \
        --set-secrets="EBAY_CERT_ID=ebay-cert-id:latest" \
        --set-secrets="EBAY_DEV_ID=ebay-dev-id:latest" \
        --set-secrets="EBAY_REFRESH_TOKEN=ebay-refresh-token:latest" \
        --args="--gcs-path,gs://${BUCKET_NAME}/upcs/batch.txt" \
        || \
    gcloud run jobs update ${PROJECT_NAME}-job \
        --image=${IMAGE_URL} \
        --region=${REGION} \
        --memory=2Gi \
        --cpu=2 \
        --task-timeout=3600 \
        --max-retries=1 \
        --parallelism=1 \
        --service-account=${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
        --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO,GCS_BUCKET=${BUCKET_NAME}" \
        --set-secrets="SPOTIFY_CLIENT_ID=spotify-client-id:latest" \
        --set-secrets="SPOTIFY_CLIENT_SECRET=spotify-client-secret:latest" \
        --set-secrets="EBAY_APP_ID=ebay-app-id:latest" \
        --set-secrets="EBAY_CERT_ID=ebay-cert-id:latest" \
        --set-secrets="EBAY_DEV_ID=ebay-dev-id:latest" \
        --set-secrets="EBAY_REFRESH_TOKEN=ebay-refresh-token:latest" \
        --args="--gcs-path,gs://${BUCKET_NAME}/upcs/batch.txt"
    
    print_message $GREEN "Cloud Run Job deployed"
}

# Note: Scheduler removed per user request - job will be run manually

# Run the job manually
run_job() {
    print_message $YELLOW "Running Cloud Run Job manually..."
    
    gcloud run jobs execute ${PROJECT_NAME}-job \
        --region=${REGION} \
        --wait
    
    print_message $GREEN "Job execution completed"
}

# Show deployment info
show_info() {
    print_message $BLUE "\n=== Deployment Information ==="
    print_message $GREEN "Project ID: ${PROJECT_ID}"
    print_message $GREEN "Region: ${REGION}"
    print_message $GREEN "Bucket: gs://${BUCKET_NAME}"
    print_message $GREEN "Job Name: ${PROJECT_NAME}-job"
    
    print_message $BLUE "\n=== Useful Commands ==="
    print_message $YELLOW "Run job:"
    echo "  gcloud run jobs execute ${PROJECT_NAME}-job --region=${REGION}"
    
    print_message $YELLOW "Run with wait (see output):"
    echo "  gcloud run jobs execute ${PROJECT_NAME}-job --region=${REGION} --wait"
    
    print_message $YELLOW "View job logs:"
    echo "  gcloud logging read \"resource.type=cloud_run_job AND resource.labels.job_name=${PROJECT_NAME}-job\" --limit=50"
    
    print_message $YELLOW "Stream logs during execution:"
    echo "  gcloud alpha run jobs logs tail ${PROJECT_NAME}-job --region=${REGION}"
    
    print_message $YELLOW "Upload UPC file:"
    echo "  gsutil cp your_upcs.txt gs://${BUCKET_NAME}/upcs/batch.txt"
    
    print_message $YELLOW "Download results:"
    echo "  gsutil cp -r gs://${BUCKET_NAME}/output/ ."
    
    print_message $YELLOW "List recent outputs:"
    echo "  gsutil ls -l gs://${BUCKET_NAME}/output/ | head -20"
}

# Main deployment flow
main() {
    print_message $GREEN "🚀 Starting Cloud Run deployment for ${PROJECT_NAME}"
    
    check_prerequisites
    PROJECT_ID=$(gcloud config get-value project)
    
    # Ask what to deploy
    print_message $BLUE "\nWhat would you like to do?"
    echo "1) Full deployment (recommended for first time)"
    echo "2) Update code only"
    echo "3) Update secrets only"
    echo "4) Configure storage bucket"
    echo "5) Run job now"
    echo "6) Show deployment info"
    read -p "Enter choice (1-6): " choice
    
    case $choice in
        1)
            enable_apis
            setup_service_account
            setup_secrets
            setup_storage
            build_and_push_image
            deploy_cloud_run_job
            show_info
            print_message $BLUE "\n📝 Remember to upload your UPC file before running:"
            echo "  gsutil cp your_upcs.txt gs://${BUCKET_NAME}/upcs/batch.txt"
            ;;
        2)
            setup_storage  # Need bucket name for deployment
            build_and_push_image
            deploy_cloud_run_job
            print_message $GREEN "Code updated successfully"
            ;;
        3)
            setup_secrets
            print_message $GREEN "Secrets updated successfully"
            ;;
        4)
            setup_storage
            ;;
        5)
            run_job
            ;;
        6)
            setup_storage  # Need bucket name for info display
            show_info
            ;;
        *)
            print_message $RED "Invalid choice"
            exit 1
            ;;
    esac
    
    print_message $GREEN "\n✅ Cloud Run deployment completed!"
}

# Run main function
main "$@"
