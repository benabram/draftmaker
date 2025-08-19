#!/bin/bash

# GitHub Actions Self-Hosted Runner Setup Script
# This script installs and configures a self-hosted runner for the staging deployment

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

print_colored $BLUE "==========================================="
print_colored $BLUE "  GitHub Actions Self-Hosted Runner Setup"
print_colored $BLUE "==========================================="
echo

# Configuration
RUNNER_DIR="$HOME/actions-runner"
GITHUB_OWNER="benabram"  # Update this with your GitHub username or org
GITHUB_REPO="draftmaker"
RUNNER_NAME="staging-docker-runner"
RUNNER_LABELS="self-hosted,Linux,X64,staging"

print_colored $YELLOW "This script will install a GitHub Actions self-hosted runner for:"
print_colored $NC "  Repository: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"
print_colored $NC "  Runner name: ${RUNNER_NAME}"
print_colored $NC "  Labels: ${RUNNER_LABELS}"
echo

print_colored $RED "You will need:"
print_colored $NC "  1. Admin access to the repository"
print_colored $NC "  2. A GitHub Personal Access Token (PAT) with 'repo' scope"
echo

read -p "Do you want to continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Step 1: Create runner directory
print_colored $YELLOW "Step 1: Creating runner directory..."
mkdir -p $RUNNER_DIR
cd $RUNNER_DIR
print_colored $GREEN "✓ Directory created: $RUNNER_DIR"

# Step 2: Download runner
print_colored $YELLOW "Step 2: Downloading GitHub Actions runner..."
RUNNER_VERSION="2.319.1"  # Update this to latest version if needed
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
    https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
print_colored $GREEN "✓ Runner downloaded"

# Step 3: Extract runner
print_colored $YELLOW "Step 3: Extracting runner..."
tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
print_colored $GREEN "✓ Runner extracted"

# Step 4: Get registration token
print_colored $YELLOW "Step 4: Getting registration token..."
echo
print_colored $YELLOW "Please go to: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/settings/actions/runners/new"
print_colored $YELLOW "And copy the registration token from the page"
echo
read -p "Enter the registration token: " RUNNER_TOKEN
echo

# Step 5: Configure runner
print_colored $YELLOW "Step 5: Configuring runner..."
./config.sh \
    --url https://github.com/${GITHUB_OWNER}/${GITHUB_REPO} \
    --token ${RUNNER_TOKEN} \
    --name ${RUNNER_NAME} \
    --labels ${RUNNER_LABELS} \
    --work _work \
    --unattended \
    --replace

print_colored $GREEN "✓ Runner configured"

# Step 6: Install as service
print_colored $YELLOW "Step 6: Installing runner as a service..."
sudo ./svc.sh install
print_colored $GREEN "✓ Service installed"

# Step 7: Start service
print_colored $YELLOW "Step 7: Starting runner service..."
sudo ./svc.sh start
print_colored $GREEN "✓ Service started"

# Check status
print_colored $YELLOW "Step 8: Checking service status..."
sudo ./svc.sh status

echo
print_colored $GREEN "==========================================="
print_colored $GREEN "  Runner Installation Complete!"
print_colored $GREEN "==========================================="
echo
print_colored $YELLOW "Useful commands:"
print_colored $NC "  Check status:  sudo $RUNNER_DIR/svc.sh status"
print_colored $NC "  View logs:     sudo journalctl -u actions.runner.${GITHUB_OWNER}-${GITHUB_REPO}.${RUNNER_NAME} -f"
print_colored $NC "  Stop runner:   sudo $RUNNER_DIR/svc.sh stop"
print_colored $NC "  Start runner:  sudo $RUNNER_DIR/svc.sh start"
echo
print_colored $BLUE "Your staging deployment will now work automatically when you push to the develop branch!"
