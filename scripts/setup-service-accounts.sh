#!/bin/bash

# Service Account Setup Script for Draft Maker
# This script helps configure service account credentials for both staging and production environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="draft-maker-468923"
PRODUCTION_SA="draft-maker-identity@${PROJECT_ID}.iam.gserviceaccount.com"
GITHUB_SA="github-actions@${PROJECT_ID}.iam.gserviceaccount.com"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to check if gcloud is installed
check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        print_message $RED "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
}

# Function to check authentication
check_auth() {
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
        print_message $YELLOW "Authenticating with Google Cloud..."
        gcloud auth login
    fi
    
    # Set the project
    gcloud config set project ${PROJECT_ID}
}

# Function to create service account key for staging
create_staging_key() {
    print_message $YELLOW "Creating service account key for staging environment..."
    
    # Create keys directory if it doesn't exist
    mkdir -p keys
    
    # Generate key for draft-maker-identity service account
    gcloud iam service-accounts keys create \
        keys/draft-maker-identity-key.json \
        --iam-account=${PRODUCTION_SA}
    
    print_message $GREEN "Service account key created at: keys/draft-maker-identity-key.json"
    print_message $YELLOW "Add this to .gitignore to prevent accidental commits!"
}

# Function to verify service account permissions
verify_permissions() {
    print_message $YELLOW "Verifying service account permissions..."
    
    # Check production service account roles
    print_message $YELLOW "Roles for ${PRODUCTION_SA}:"
    gcloud projects get-iam-policy ${PROJECT_ID} \
        --flatten="bindings[].members" \
        --format="table(bindings.role)" \
        --filter="bindings.members:${PRODUCTION_SA}"
    
    # Check GitHub Actions service account roles
    print_message $YELLOW "Roles for ${GITHUB_SA}:"
    gcloud projects get-iam-policy ${PROJECT_ID} \
        --flatten="bindings[].members" \
        --format="table(bindings.role)" \
        --filter="bindings.members:${GITHUB_SA}"
}

# Function to grant necessary permissions
grant_permissions() {
    print_message $YELLOW "Granting necessary permissions to service accounts..."
    
    # Permissions for production service account
    for role in \
        "roles/datastore.user" \
        "roles/storage.objectAdmin" \
        "roles/secretmanager.secretAccessor"
    do
        gcloud projects add-iam-policy-binding ${PROJECT_ID} \
            --member="serviceAccount:${PRODUCTION_SA}" \
            --role="${role}" \
            --quiet
    done
    
    # Additional permissions for GitHub Actions service account
    for role in \
        "roles/run.admin" \
        "roles/iam.serviceAccountUser" \
        "roles/artifactregistry.writer"
    do
        gcloud projects add-iam-policy-binding ${PROJECT_ID} \
            --member="serviceAccount:${GITHUB_SA}" \
            --role="${role}" \
            --quiet
    done
    
    print_message $GREEN "Permissions granted successfully"
}

# Function to setup secrets in Secret Manager
setup_secrets() {
    print_message $YELLOW "Setting up secrets in Secret Manager..."
    
    # List of secrets to create (if they don't exist)
    declare -a secrets=(
        "DISCOGS_CONSUMER_KEY"
        "DISCOGS_CONSUMER_SECRET"
        "EBAY_APP_ID"
        "EBAY_DEV_ID"
        "EBAY_CERT_ID"
        "EBAY_CLIENT_SECRET"
        "SPOTIFY_CLIENT_ID"
        "SPOTIFY_CLIENT_SECRET"
    )
    
    for secret in "${secrets[@]}"; do
        # Check if secret exists
        if ! gcloud secrets describe ${secret} --project=${PROJECT_ID} &>/dev/null; then
            print_message $YELLOW "Creating secret: ${secret}"
            
            # Read value from .env.production file if it exists
            if [ -f ".env.production" ]; then
                value=$(grep "^${secret}=" .env.production | cut -d'=' -f2- | tr -d '"')
                if [ ! -z "$value" ]; then
                    echo -n "$value" | gcloud secrets create ${secret} \
                        --data-file=- \
                        --project=${PROJECT_ID}
                    
                    # Grant access to service accounts
                    gcloud secrets add-iam-policy-binding ${secret} \
                        --member="serviceAccount:${PRODUCTION_SA}" \
                        --role="roles/secretmanager.secretAccessor" \
                        --project=${PROJECT_ID}
                    
                    gcloud secrets add-iam-policy-binding ${secret} \
                        --member="serviceAccount:${GITHUB_SA}" \
                        --role="roles/secretmanager.secretAccessor" \
                        --project=${PROJECT_ID}
                else
                    print_message $YELLOW "No value found for ${secret} in .env.production, skipping..."
                fi
            fi
        else
            print_message $GREEN "Secret ${secret} already exists"
        fi
    done
}

# Function to update staging deployment to use service account
update_staging_deployment() {
    print_message $YELLOW "Updating staging deployment configuration..."
    
    # Update staging workflow to mount the service account key
    if [ -f ".github/workflows/staging-deploy.yml" ]; then
        print_message $GREEN "Staging workflow already updated to use service account"
    fi
    
    print_message $YELLOW "Remember to mount the service account key in your staging Docker container:"
    print_message $NC "  -v \$(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro"
}

# Main menu
show_menu() {
    echo ""
    print_message $GREEN "=== Draft Maker Service Account Setup ==="
    echo "1. Check gcloud authentication"
    echo "2. Create service account key for staging"
    echo "3. Verify service account permissions"
    echo "4. Grant necessary permissions"
    echo "5. Setup secrets in Secret Manager"
    echo "6. Run complete setup"
    echo "0. Exit"
    echo ""
    read -p "Choose an option: " choice
    
    case $choice in
        1)
            check_gcloud
            check_auth
            ;;
        2)
            check_gcloud
            check_auth
            create_staging_key
            ;;
        3)
            check_gcloud
            check_auth
            verify_permissions
            ;;
        4)
            check_gcloud
            check_auth
            grant_permissions
            ;;
        5)
            check_gcloud
            check_auth
            setup_secrets
            ;;
        6)
            check_gcloud
            check_auth
            create_staging_key
            verify_permissions
            grant_permissions
            setup_secrets
            update_staging_deployment
            print_message $GREEN "Setup complete!"
            ;;
        0)
            exit 0
            ;;
        *)
            print_message $RED "Invalid option"
            ;;
    esac
}

# Run the menu
while true; do
    show_menu
done
