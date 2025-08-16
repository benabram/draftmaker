#!/bin/bash

# eBay Draft Maker - Production Deployment Script
# Supports deployment to Google Cloud Run, AWS ECS, or Kubernetes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ebay-draftmaker"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-production}"
VERSION="${VERSION:-latest}"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check required environment variables
check_env_vars() {
    local required_vars=("DEPLOYMENT_TYPE")
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            print_message $RED "Error: Required environment variable $var is not set"
            exit 1
        fi
    done
}

# Build Docker image
build_image() {
    print_message $YELLOW "Building Docker image..."
    
    docker build \
        -f Dockerfile.production \
        -t ${PROJECT_NAME}:${VERSION} \
        -t ${PROJECT_NAME}:latest \
        .
    
    print_message $GREEN "Docker image built successfully"
}

# Deploy to Google Cloud Run
deploy_gcloud() {
    print_message $YELLOW "Deploying to Google Cloud Run..."
    
    # Check if logged in to gcloud
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
        print_message $RED "Please authenticate with gcloud first: gcloud auth login"
        exit 1
    fi
    
    # Get project ID
    PROJECT_ID=$(gcloud config get-value project)
    if [ -z "$PROJECT_ID" ]; then
        print_message $RED "Please set a GCP project: gcloud config set project PROJECT_ID"
        exit 1
    fi
    
    # Configure artifact registry
    REPOSITORY="gcr.io/${PROJECT_ID}"
    IMAGE_URL="${REPOSITORY}/${PROJECT_NAME}:${VERSION}"
    
    # Tag and push image
    docker tag ${PROJECT_NAME}:${VERSION} ${IMAGE_URL}
    docker push ${IMAGE_URL}
    
    # Deploy to Cloud Run
    gcloud run deploy ${PROJECT_NAME} \
        --image ${IMAGE_URL} \
        --platform managed \
        --region ${REGION} \
        --allow-unauthenticated \
        --memory 2Gi \
        --cpu 2 \
        --timeout 3600 \
        --max-instances 10 \
        --set-env-vars "ENVIRONMENT=${ENVIRONMENT},LOG_LEVEL=INFO" \
        --set-secrets "SPOTIFY_CLIENT_ID=spotify-client-id:latest" \
        --set-secrets "SPOTIFY_CLIENT_SECRET=spotify-client-secret:latest" \
        --set-secrets "EBAY_APP_ID=ebay-app-id:latest" \
        --set-secrets "EBAY_CERT_ID=ebay-cert-id:latest" \
        --set-secrets "EBAY_DEV_ID=ebay-dev-id:latest" \
        --set-secrets "EBAY_REFRESH_TOKEN=ebay-refresh-token:latest"
    
    print_message $GREEN "Deployment to Cloud Run completed"
}

# Deploy to AWS ECS
deploy_aws() {
    print_message $YELLOW "Deploying to AWS ECS..."
    
    # Check AWS CLI configuration
    if ! aws sts get-caller-identity &>/dev/null; then
        print_message $RED "Please configure AWS CLI first: aws configure"
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REPOSITORY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION:-us-east-1}.amazonaws.com/${PROJECT_NAME}"
    
    # Login to ECR
    aws ecr get-login-password --region ${AWS_REGION:-us-east-1} | \
        docker login --username AWS --password-stdin ${ECR_REPOSITORY}
    
    # Create repository if it doesn't exist
    aws ecr describe-repositories --repository-names ${PROJECT_NAME} &>/dev/null || \
        aws ecr create-repository --repository-name ${PROJECT_NAME}
    
    # Tag and push image
    docker tag ${PROJECT_NAME}:${VERSION} ${ECR_REPOSITORY}:${VERSION}
    docker push ${ECR_REPOSITORY}:${VERSION}
    
    # Update ECS service (assumes task definition and service exist)
    aws ecs register-task-definition \
        --cli-input-json file://deploy/ecs-task-definition.json
    
    aws ecs update-service \
        --cluster ${ECS_CLUSTER:-default} \
        --service ${PROJECT_NAME} \
        --force-new-deployment
    
    print_message $GREEN "Deployment to AWS ECS completed"
}

# Deploy to Kubernetes
deploy_k8s() {
    print_message $YELLOW "Deploying to Kubernetes..."
    
    # Check kubectl configuration
    if ! kubectl cluster-info &>/dev/null; then
        print_message $RED "kubectl is not configured. Please configure kubectl first."
        exit 1
    fi
    
    # Apply Kubernetes manifests
    kubectl apply -f deploy/k8s/
    
    # Wait for deployment to be ready
    kubectl rollout status deployment/${PROJECT_NAME} -n ${NAMESPACE:-default}
    
    print_message $GREEN "Deployment to Kubernetes completed"
}

# Run tests before deployment
run_tests() {
    print_message $YELLOW "Running tests..."
    
    # Run unit tests
    python -m pytest tests/unit/ -v
    
    # Run integration tests if specified
    if [ "${RUN_INTEGRATION_TESTS}" = "true" ]; then
        python -m pytest tests/integration/ -v
    fi
    
    print_message $GREEN "All tests passed"
}

# Main deployment flow
main() {
    print_message $GREEN "Starting deployment of ${PROJECT_NAME}"
    
    # Check environment variables
    check_env_vars
    
    # Run tests if not skipped
    if [ "${SKIP_TESTS}" != "true" ]; then
        run_tests
    fi
    
    # Build Docker image
    build_image
    
    # Deploy based on target platform
    case "${DEPLOYMENT_TYPE}" in
        gcloud)
            deploy_gcloud
            ;;
        aws)
            deploy_aws
            ;;
        k8s)
            deploy_k8s
            ;;
        *)
            print_message $RED "Unknown deployment type: ${DEPLOYMENT_TYPE}"
            print_message $YELLOW "Valid options: gcloud, aws, k8s"
            exit 1
            ;;
    esac
    
    print_message $GREEN "Deployment completed successfully!"
}

# Run main function
main "$@"
