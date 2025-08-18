#!/bin/bash

# Manual Staging Deployment Script
# This script manually performs the staging deployment steps
# that would normally be run by the GitHub Actions self-hosted runner

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;94m'
NC='\033[0m' # No Color

# Function to print colored output
print_colored() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_colored $BLUE "========================================="
print_colored $BLUE "  Draft Maker - Manual Staging Deployment"
print_colored $BLUE "========================================="
echo

# Change to project directory
cd /home/benbuntu/draftmaker

# Step 1: Check current branch
print_colored $YELLOW "Step 1: Checking current branch..."
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "develop" ]; then
    print_colored $RED "Warning: You are not on the develop branch (current: $CURRENT_BRANCH)"
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    print_colored $GREEN "✓ On develop branch"
fi

# Step 2: Pull latest changes
print_colored $YELLOW "Step 2: Pulling latest changes..."
git pull origin develop
print_colored $GREEN "✓ Latest changes pulled"

# Step 3: Build Docker image
print_colored $YELLOW "Step 3: Building Docker image..."
docker build -f Dockerfile.production -t draft-maker-staging .
print_colored $GREEN "✓ Docker image built successfully"

# Step 4: Stop and remove old container
print_colored $YELLOW "Step 4: Stopping and removing old container (if exists)..."
if [ $(docker ps -q -f name=draft-maker-staging) ]; then
    docker stop draft-maker-staging
    docker rm draft-maker-staging
    print_colored $GREEN "✓ Old container stopped and removed"
else
    print_colored $BLUE "  No existing container found"
fi

# Step 5: Check for service account key
print_colored $YELLOW "Step 5: Checking for service account key..."
if [ -f "keys/draft-maker-identity-key.json" ]; then
    SA_MOUNT="-v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro"
    print_colored $GREEN "✓ Service account key found"
else
    print_colored $RED "Warning: Service account key not found at keys/draft-maker-identity-key.json"
    print_colored $YELLOW "  Run scripts/setup-service-accounts.sh to create it"
    print_colored $YELLOW "  Continuing without service account mount..."
    SA_MOUNT=""
fi

# Step 6: Check for required files
print_colored $YELLOW "Step 6: Checking for required files..."
MISSING_FILES=""

if [ ! -f ".env.staging" ]; then
    MISSING_FILES="$MISSING_FILES .env.staging"
fi

if [ -n "$MISSING_FILES" ]; then
    print_colored $RED "Error: Required files missing:$MISSING_FILES"
    exit 1
else
    print_colored $GREEN "✓ All required files present"
fi

# Step 7: Create necessary directories
print_colored $YELLOW "Step 7: Creating necessary directories..."
mkdir -p logs output data
print_colored $GREEN "✓ Directories created"

# Step 8: Run new container
print_colored $YELLOW "Step 8: Starting new container..."
docker run -d \
    --name draft-maker-staging \
    -p 8080:8080 \
    -v $(pwd)/.env.staging:/app/.env:ro \
    -v $(pwd)/logs:/app/logs \
    -v $(pwd)/output:/app/output \
    -v $(pwd)/data:/app/data:ro \
    ${SA_MOUNT} \
    --env-file .env.staging \
    --env GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-key.json \
    draft-maker-staging

# Check if container started successfully
sleep 2
if [ $(docker ps -q -f name=draft-maker-staging) ]; then
    print_colored $GREEN "✓ Container started successfully"
    echo
    print_colored $BLUE "Container Information:"
    docker ps --filter name=draft-maker-staging --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo
    print_colored $YELLOW "To view logs:"
    print_colored $NC "  docker logs -f draft-maker-staging"
    echo
    print_colored $YELLOW "To stop the container:"
    print_colored $NC "  docker stop draft-maker-staging"
    echo
    print_colored $YELLOW "To test the application:"
    print_colored $NC "  curl http://localhost:8080/health"
else
    print_colored $RED "✗ Container failed to start"
    print_colored $YELLOW "Checking container logs..."
    docker logs draft-maker-staging
    exit 1
fi

print_colored $GREEN "========================================="
print_colored $GREEN "  Deployment Complete!"
print_colored $GREEN "========================================="
