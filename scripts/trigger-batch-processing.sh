#!/bin/bash

# Script to trigger batch processing in the Draft Maker staging container
# Usage: ./trigger-batch-processing.sh [options]

set -e

# Default values
GCS_PATH=""
METHOD="docker"  # docker or api
CREATE_DRAFTS="true"
TEST_MODE="false"
CONTAINER_NAME="draft-maker-staging"
API_URL="http://localhost:8080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Trigger batch processing of UPC codes from Google Cloud Storage"
    echo ""
    echo "Options:"
    echo "  -g, --gcs-path PATH      GCS path to UPC file (e.g., gs://draft-maker-bucket/upcs.txt)"
    echo "  -m, --method METHOD      Method to use: 'docker' or 'api' (default: docker)"
    echo "  -d, --no-drafts          Don't create eBay drafts (only process metadata)"
    echo "  -t, --test               Run in test mode"
    echo "  -c, --container NAME     Docker container name (default: draft-maker-staging)"
    echo "  -u, --url URL            API URL (default: http://localhost:8080)"
    echo "  -s, --status JOB_ID      Check status of a specific job (API method only)"
    echo "  -l, --list               List all batch jobs (API method only)"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  # Process UPCs using Docker exec"
    echo "  $0 -g gs://draft-maker-bucket/upcs.txt"
    echo ""
    echo "  # Process UPCs using API"
    echo "  $0 -g gs://draft-maker-bucket/upcs.txt -m api"
    echo ""
    echo "  # Check job status"
    echo "  $0 -m api -s batch_20240318_143022_0"
    echo ""
    echo "  # List all jobs"
    echo "  $0 -m api -l"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--gcs-path)
            GCS_PATH="$2"
            shift 2
            ;;
        -m|--method)
            METHOD="$2"
            shift 2
            ;;
        -d|--no-drafts)
            CREATE_DRAFTS="false"
            shift
            ;;
        -t|--test)
            TEST_MODE="true"
            shift
            ;;
        -c|--container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -s|--status)
            JOB_ID="$2"
            METHOD="api"
            shift 2
            ;;
        -l|--list)
            LIST_JOBS="true"
            METHOD="api"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Function to trigger batch processing via Docker
trigger_via_docker() {
    print_info "Triggering batch processing via Docker exec..."
    
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        print_error "Container ${CONTAINER_NAME} is not running"
        print_info "Start the container first or use the API method"
        exit 1
    fi
    
    # Build the command
    CMD="python main.py \"$GCS_PATH\""
    
    if [ "$TEST_MODE" = "true" ]; then
        CMD="$CMD --test"
    fi
    
    if [ "$CREATE_DRAFTS" = "false" ]; then
        CMD="$CMD --no-drafts"
    fi
    
    print_info "Executing in container: $CMD"
    
    # Execute the command in the container
    docker exec -it "$CONTAINER_NAME" bash -c "$CMD"
    
    if [ $? -eq 0 ]; then
        print_success "Batch processing triggered successfully"
    else
        print_error "Failed to trigger batch processing"
        exit 1
    fi
}

# Function to trigger batch processing via API
trigger_via_api() {
    print_info "Triggering batch processing via API..."
    
    # Check if API is accessible
    if ! curl -s -f "${API_URL}/health" > /dev/null; then
        print_error "API is not accessible at ${API_URL}"
        print_info "Make sure the staging container is running"
        exit 1
    fi
    
    # Prepare JSON payload
    JSON_PAYLOAD=$(cat <<EOF
{
    "gcs_path": "${GCS_PATH}",
    "create_drafts": ${CREATE_DRAFTS},
    "test_mode": ${TEST_MODE}
}
EOF
)
    
    print_info "Sending request to API..."
    
    # Send POST request
    RESPONSE=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$JSON_PAYLOAD" \
        "${API_URL}/api/batch/process")
    
    if [ $? -eq 0 ]; then
        # Extract job ID from response
        JOB_ID=$(echo "$RESPONSE" | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)
        
        if [ -n "$JOB_ID" ]; then
            print_success "Batch job created successfully!"
            echo ""
            echo "Job ID: $JOB_ID"
            echo "GCS Path: $GCS_PATH"
            echo ""
            echo "To check status, run:"
            echo "  $0 -m api -s $JOB_ID"
            echo ""
            echo "Or view in browser:"
            echo "  ${API_URL}/api/batch/status/$JOB_ID"
        else
            print_warning "Job may have been created but couldn't extract job ID"
            echo "Response: $RESPONSE"
        fi
    else
        print_error "Failed to trigger batch processing via API"
        exit 1
    fi
}

# Function to check job status
check_job_status() {
    if [ -z "$JOB_ID" ]; then
        print_error "Job ID is required for status check"
        exit 1
    fi
    
    print_info "Checking status for job: $JOB_ID"
    
    RESPONSE=$(curl -s "${API_URL}/api/batch/status/${JOB_ID}")
    
    if [ $? -eq 0 ]; then
        # Pretty print the JSON response
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    else
        print_error "Failed to get job status"
        exit 1
    fi
}

# Function to list all jobs
list_all_jobs() {
    print_info "Listing all batch jobs..."
    
    RESPONSE=$(curl -s "${API_URL}/api/batch/jobs")
    
    if [ $? -eq 0 ]; then
        # Pretty print the JSON response
        echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    else
        print_error "Failed to list jobs"
        exit 1
    fi
}

# Main logic
if [ -n "$JOB_ID" ]; then
    # Check job status
    check_job_status
elif [ "$LIST_JOBS" = "true" ]; then
    # List all jobs
    list_all_jobs
else
    # Validate GCS path
    if [ -z "$GCS_PATH" ]; then
        print_error "GCS path is required"
        usage
        exit 1
    fi
    
    if [[ ! "$GCS_PATH" =~ ^gs:// ]]; then
        print_error "Invalid GCS path format. Must start with gs://"
        usage
        exit 1
    fi
    
    print_info "Configuration:"
    echo "  GCS Path: $GCS_PATH"
    echo "  Method: $METHOD"
    echo "  Create Drafts: $CREATE_DRAFTS"
    echo "  Test Mode: $TEST_MODE"
    
    if [ "$METHOD" = "docker" ]; then
        echo "  Container: $CONTAINER_NAME"
    else
        echo "  API URL: $API_URL"
    fi
    
    echo ""
    
    # Trigger processing based on method
    if [ "$METHOD" = "docker" ]; then
        trigger_via_docker
    elif [ "$METHOD" = "api" ]; then
        trigger_via_api
    else
        print_error "Invalid method: $METHOD"
        usage
        exit 1
    fi
fi
