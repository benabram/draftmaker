#!/bin/bash

# eBay Draft Maker - Simple Deployment Script for Single User
# Supports local Docker, systemd service, or Google Cloud Run

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="ebay-draftmaker"
INSTALL_DIR="${HOME}/.local/ebay-draftmaker"

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Install as local Docker container
install_docker() {
    print_message $YELLOW "Installing as Docker container..."
    
    # Build image
    docker build -f Dockerfile.production -t ${PROJECT_NAME}:latest .
    
    # Create local directories if they don't exist
    mkdir -p logs output .tokens
    
    # Stop existing container if running
    docker stop ${PROJECT_NAME} 2>/dev/null || true
    docker rm ${PROJECT_NAME} 2>/dev/null || true
    
    # Run container
    docker run -d \
        --name ${PROJECT_NAME} \
        --restart unless-stopped \
        -v $(pwd)/config.ini:/app/config.ini:ro \
        -v $(pwd)/.tokens:/app/.tokens \
        -v $(pwd)/logs:/app/logs \
        -v $(pwd)/output:/app/output \
        -v $(pwd)/data:/app/data:ro \
        ${PROJECT_NAME}:latest
    
    print_message $GREEN "Docker container installed and running"
    print_message $YELLOW "View logs: docker logs -f ${PROJECT_NAME}"
    print_message $YELLOW "Stop: docker stop ${PROJECT_NAME}"
}

# Install as systemd service (Linux)
install_systemd() {
    print_message $YELLOW "Installing as systemd service..."
    
    # Create installation directory
    mkdir -p ${INSTALL_DIR}
    
    # Copy files
    cp -r src ${INSTALL_DIR}/
    cp main.py ${INSTALL_DIR}/
    cp requirements.txt ${INSTALL_DIR}/
    cp config.ini ${INSTALL_DIR}/
    
    # Create directories
    mkdir -p ${INSTALL_DIR}/{logs,output,.tokens,data}
    
    # Install Python dependencies in virtual environment
    python3 -m venv ${INSTALL_DIR}/venv
    ${INSTALL_DIR}/venv/bin/pip install -r ${INSTALL_DIR}/requirements.txt
    
    # Create systemd service file
    cat > /tmp/ebay-draftmaker.service <<EOF
[Unit]
Description=eBay Draft Maker Service
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/main.py --daemon
Restart=on-failure
RestartSec=10
StandardOutput=append:${INSTALL_DIR}/logs/service.log
StandardError=append:${INSTALL_DIR}/logs/service_error.log

[Install]
WantedBy=multi-user.target
EOF
    
    # Install service
    sudo cp /tmp/ebay-draftmaker.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable ebay-draftmaker
    sudo systemctl start ebay-draftmaker
    
    print_message $GREEN "Systemd service installed and started"
    print_message $YELLOW "Check status: sudo systemctl status ebay-draftmaker"
    print_message $YELLOW "View logs: journalctl -u ebay-draftmaker -f"
}

# Install as cron job
install_cron() {
    print_message $YELLOW "Installing as cron job..."
    
    # Create installation directory
    mkdir -p ${INSTALL_DIR}
    
    # Copy files
    cp -r src ${INSTALL_DIR}/
    cp main.py ${INSTALL_DIR}/
    cp requirements.txt ${INSTALL_DIR}/
    cp config.ini ${INSTALL_DIR}/
    
    # Create directories
    mkdir -p ${INSTALL_DIR}/{logs,output,.tokens,data}
    
    # Install Python dependencies
    python3 -m venv ${INSTALL_DIR}/venv
    ${INSTALL_DIR}/venv/bin/pip install -r ${INSTALL_DIR}/requirements.txt
    
    # Create cron script
    cat > ${INSTALL_DIR}/run_batch.sh <<'EOF'
#!/bin/bash
cd ${HOME}/.local/ebay-draftmaker
./venv/bin/python main.py --upc-file data/daily_batch.txt >> logs/cron.log 2>&1
EOF
    chmod +x ${INSTALL_DIR}/run_batch.sh
    
    # Add to crontab (runs daily at 2 AM)
    (crontab -l 2>/dev/null; echo "0 2 * * * ${INSTALL_DIR}/run_batch.sh") | crontab -
    
    print_message $GREEN "Cron job installed"
    print_message $YELLOW "View crontab: crontab -l"
    print_message $YELLOW "Edit schedule: crontab -e"
}

# Deploy to Google Cloud Run for scheduled jobs
deploy_gcloud_scheduled() {
    print_message $YELLOW "Deploying to Cloud Run with Cloud Scheduler..."
    
    # Check gcloud
    if ! command -v gcloud &> /dev/null; then
        print_message $RED "gcloud CLI not found. Please install it first."
        exit 1
    fi
    
    PROJECT_ID=$(gcloud config get-value project)
    if [ -z "$PROJECT_ID" ]; then
        print_message $RED "Please set a GCP project: gcloud config set project PROJECT_ID"
        exit 1
    fi
    
    # Build and push image
    IMAGE_URL="gcr.io/${PROJECT_ID}/${PROJECT_NAME}:latest"
    docker build -f Dockerfile.production -t ${IMAGE_URL} .
    docker push ${IMAGE_URL}
    
    # Deploy Cloud Run job (not service)
    gcloud run jobs create ${PROJECT_NAME}-batch \
        --image ${IMAGE_URL} \
        --region us-central1 \
        --memory 2Gi \
        --cpu 2 \
        --task-timeout 3600 \
        --max-retries 1 \
        --parallelism 1 \
        --set-env-vars "ENVIRONMENT=production,LOG_LEVEL=INFO" \
        --set-secrets "SPOTIFY_CLIENT_ID=spotify-client-id:latest" \
        --set-secrets "SPOTIFY_CLIENT_SECRET=spotify-client-secret:latest" \
        --set-secrets "EBAY_APP_ID=ebay-app-id:latest" \
        --set-secrets "EBAY_CERT_ID=ebay-cert-id:latest" \
        --set-secrets "EBAY_DEV_ID=ebay-dev-id:latest" \
        --set-secrets "EBAY_REFRESH_TOKEN=ebay-refresh-token:latest" \
        --args="--gcs-path,gs://${GCS_BUCKET}/upcs/batch.txt"
    
    # Create Cloud Scheduler job
    gcloud scheduler jobs create http ${PROJECT_NAME}-scheduler \
        --location us-central1 \
        --schedule "0 2 * * *" \
        --uri "https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${PROJECT_NAME}-batch:run" \
        --http-method POST \
        --oauth-service-account-email "${PROJECT_ID}@appspot.gserviceaccount.com"
    
    print_message $GREEN "Cloud Run job deployed with scheduler"
}

# Uninstall
uninstall() {
    print_message $YELLOW "Uninstalling eBay Draft Maker..."
    
    # Stop and remove Docker container
    docker stop ${PROJECT_NAME} 2>/dev/null || true
    docker rm ${PROJECT_NAME} 2>/dev/null || true
    
    # Stop and remove systemd service
    sudo systemctl stop ebay-draftmaker 2>/dev/null || true
    sudo systemctl disable ebay-draftmaker 2>/dev/null || true
    sudo rm -f /etc/systemd/system/ebay-draftmaker.service
    
    # Remove from crontab
    crontab -l 2>/dev/null | grep -v "ebay-draftmaker" | crontab - || true
    
    # Remove installation directory
    rm -rf ${INSTALL_DIR}
    
    print_message $GREEN "Uninstalled successfully"
}

# Show usage
usage() {
    echo "Usage: $0 [OPTION]"
    echo "Deploy eBay Draft Maker application"
    echo ""
    echo "Options:"
    echo "  docker      Install as local Docker container"
    echo "  systemd     Install as systemd service (Linux)"
    echo "  cron        Install as cron job"
    echo "  gcloud      Deploy to Google Cloud Run with scheduler"
    echo "  uninstall   Remove installation"
    echo "  help        Show this help message"
}

# Main
case "${1}" in
    docker)
        install_docker
        ;;
    systemd)
        install_systemd
        ;;
    cron)
        install_cron
        ;;
    gcloud)
        deploy_gcloud_scheduled
        ;;
    uninstall)
        uninstall
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        usage
        exit 1
        ;;
esac
