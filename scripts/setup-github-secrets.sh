#!/bin/bash

# Setup GitHub Secrets for CI/CD Pipeline
# This script configures all necessary secrets for the GitHub Actions workflow

set -e

echo "==================================="
echo "GitHub Secrets Setup for Draft Maker"
echo "==================================="

# Check if gh CLI is authenticated
if ! gh auth status &>/dev/null; then
    echo "Error: GitHub CLI is not authenticated"
    echo "Please run: gh auth login"
    exit 1
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Setting up secrets for repository: $REPO"

# Function to set a secret
set_secret() {
    local name=$1
    local value=$2
    echo -n "Setting $name... "
    if echo "$value" | gh secret set "$name" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ (Failed)"
        return 1
    fi
}

# GCP Configuration
echo -e "\n📦 Setting GCP Secrets..."
set_secret "GCP_PROJECT_ID" "draft-maker-468923"
set_secret "GCP_REGION" "us-central1"
set_secret "GCP_ARTIFACT_REGISTRY" "us-central1-docker.pkg.dev/draft-maker-468923/draft-maker"

# Service Account Key
if [ -f "/tmp/github-actions-sa-key.json" ]; then
    echo -n "Setting GCP_SA_KEY... "
    SA_KEY_CONTENT=$(cat /tmp/github-actions-sa-key.json | base64 -w 0)
    if echo "$SA_KEY_CONTENT" | gh secret set "GCP_SA_KEY" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ (Failed)"
    fi
else
    echo "Warning: Service account key not found at /tmp/github-actions-sa-key.json"
    echo "Please create it with: gcloud iam service-accounts keys create /tmp/github-actions-sa-key.json --iam-account=github-actions@draft-maker-468923.iam.gserviceaccount.com"
fi

# API Keys - These need to be provided by the user
echo -e "\n🔑 Setting API Keys..."
echo "Please enter your API keys (they will not be displayed):"

read -s -p "EBAY_APP_ID: " EBAY_APP_ID
echo
if [ -n "$EBAY_APP_ID" ]; then
    set_secret "EBAY_APP_ID" "$EBAY_APP_ID"
fi

read -s -p "EBAY_CERT_ID: " EBAY_CERT_ID
echo
if [ -n "$EBAY_CERT_ID" ]; then
    set_secret "EBAY_CERT_ID" "$EBAY_CERT_ID"
fi

read -s -p "EBAY_TOKEN: " EBAY_TOKEN
echo
if [ -n "$EBAY_TOKEN" ]; then
    set_secret "EBAY_TOKEN" "$EBAY_TOKEN"
fi

read -s -p "MUSICBRAINZ_USER_AGENT: " MUSICBRAINZ_USER_AGENT
echo
if [ -n "$MUSICBRAINZ_USER_AGENT" ]; then
    set_secret "MUSICBRAINZ_USER_AGENT" "$MUSICBRAINZ_USER_AGENT"
fi

read -s -p "DISCOGS_TOKEN: " DISCOGS_TOKEN
echo
if [ -n "$DISCOGS_TOKEN" ]; then
    set_secret "DISCOGS_TOKEN" "$DISCOGS_TOKEN"
fi

read -s -p "SPOTIFY_CLIENT_ID: " SPOTIFY_CLIENT_ID
echo
if [ -n "$SPOTIFY_CLIENT_ID" ]; then
    set_secret "SPOTIFY_CLIENT_ID" "$SPOTIFY_CLIENT_ID"
fi

read -s -p "SPOTIFY_CLIENT_SECRET: " SPOTIFY_CLIENT_SECRET
echo
if [ -n "$SPOTIFY_CLIENT_SECRET" ]; then
    set_secret "SPOTIFY_CLIENT_SECRET" "$SPOTIFY_CLIENT_SECRET"
fi

# Optional: Docker Hub credentials for caching
echo -e "\n🐳 Docker Hub Configuration (optional, press Enter to skip):"
read -s -p "DOCKERHUB_USERNAME: " DOCKERHUB_USERNAME
echo
if [ -n "$DOCKERHUB_USERNAME" ]; then
    set_secret "DOCKERHUB_USERNAME" "$DOCKERHUB_USERNAME"
    
    read -s -p "DOCKERHUB_TOKEN: " DOCKERHUB_TOKEN
    echo
    if [ -n "$DOCKERHUB_TOKEN" ]; then
        set_secret "DOCKERHUB_TOKEN" "$DOCKERHUB_TOKEN"
    fi
fi

echo -e "\n==================================="
echo "✅ GitHub Secrets Setup Complete!"
echo "==================================="
echo ""
echo "You can verify the secrets with:"
echo "  gh secret list"
echo ""
echo "Next steps:"
echo "1. Commit and push your changes"
echo "2. The CI/CD pipeline will run automatically on push"
echo "3. You can manually deploy using GitHub Actions"
