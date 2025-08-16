#!/bin/bash

# Setup GitHub Secrets for CI/CD Pipeline - Manual Version
# This script sets up GCP-related secrets automatically
# You'll need to add API keys manually through GitHub UI

set -e

echo "==================================="
echo "GitHub Secrets Setup for Draft Maker"
echo "==================================="

# Check if gh CLI is authenticated
if ! gh auth status &>/dev/null; then
    echo "❌ Error: GitHub CLI is not authenticated"
    echo ""
    echo "Please authenticate first with one of these methods:"
    echo "1. Browser authentication: gh auth login"
    echo "2. Token authentication: echo YOUR_GITHUB_TOKEN | gh auth login --with-token"
    echo ""
    exit 1
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "✅ Setting up secrets for repository: $REPO"
echo ""

# Function to set a secret
set_secret() {
    local name=$1
    local value=$2
    echo -n "  Setting $name... "
    if echo "$value" | gh secret set "$name" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ (Failed)"
        return 1
    fi
}

# GCP Configuration
echo "📦 Setting GCP Secrets..."
set_secret "GCP_PROJECT_ID" "draft-maker-468923"
set_secret "GCP_REGION" "us-central1"
set_secret "GCP_ARTIFACT_REGISTRY" "us-central1-docker.pkg.dev/draft-maker-468923/draft-maker"

# Service Account Key
if [ -f "/tmp/github-actions-sa-key.json" ]; then
    echo -n "  Setting GCP_SA_KEY... "
    SA_KEY_CONTENT=$(cat /tmp/github-actions-sa-key.json | base64 -w 0)
    if echo "$SA_KEY_CONTENT" | gh secret set "GCP_SA_KEY" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ (Failed)"
    fi
    echo ""
    echo "✅ GCP secrets configured successfully!"
else
    echo "❌ Warning: Service account key not found at /tmp/github-actions-sa-key.json"
    echo "   Please create it with:"
    echo "   gcloud iam service-accounts keys create /tmp/github-actions-sa-key.json --iam-account=github-actions@draft-maker-468923.iam.gserviceaccount.com"
    exit 1
fi

echo ""
echo "==================================="
echo "📝 Manual Steps Required"
echo "==================================="
echo ""
echo "Please add the following secrets manually in GitHub:"
echo "Go to: https://github.com/$(echo $REPO)/settings/secrets/actions"
echo ""
echo "Required API Keys:"
echo "  • EBAY_APP_ID - Your eBay App ID"
echo "  • EBAY_CERT_ID - Your eBay Certificate ID"
echo "  • EBAY_TOKEN - Your eBay Auth Token"
echo "  • MUSICBRAINZ_USER_AGENT - Format: AppName/Version (contact@email.com)"
echo "  • DISCOGS_TOKEN - Your Discogs personal access token"
echo "  • SPOTIFY_CLIENT_ID - Your Spotify app client ID"
echo "  • SPOTIFY_CLIENT_SECRET - Your Spotify app client secret"
echo ""
echo "Optional (for Docker Hub caching):"
echo "  • DOCKERHUB_USERNAME - Your Docker Hub username"
echo "  • DOCKERHUB_TOKEN - Your Docker Hub access token"
echo ""
echo "==================================="
echo "✅ Automated Setup Complete!"
echo "==================================="
echo ""
echo "Current secrets in repository:"
gh secret list
echo ""
echo "Next steps:"
echo "1. Add the API key secrets manually as listed above"
echo "2. Commit and push your changes"
echo "3. The CI/CD pipeline will run automatically"
