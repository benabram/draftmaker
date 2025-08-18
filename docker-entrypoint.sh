#!/bin/bash

# Docker entrypoint script for Draft Maker
# This script handles different modes of operation for the container

set -e

# Default values
MODE="${MODE:-batch}"
INPUT_SOURCE="${INPUT_SOURCE:-}"
LOCAL_FILE="${LOCAL_FILE:-false}"
TEST_MODE="${TEST_MODE:-false}"
SINGLE_UPC="${SINGLE_UPC:-}"

# Function to print colored output
print_info() {
    echo -e "\033[0;94m[INFO]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

# Set up environment
if [ -f /app/.env ]; then
    print_info "Loading environment from .env file"
    # Load environment variables more safely
    set -a
    source /app/.env
    set +a
fi

# Set Google Application Credentials if mounted
if [ -f /app/service-account-key.json ]; then
    export GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-key.json
    print_info "Service account credentials configured"
fi

case "$MODE" in
    "batch")
        if [ -z "$INPUT_SOURCE" ]; then
            print_error "INPUT_SOURCE environment variable is required for batch mode"
            print_info "Usage: docker run -e INPUT_SOURCE=gs://bucket/file.txt draft-maker"
            exit 1
        fi
        
        print_info "Running in batch mode with source: $INPUT_SOURCE"
        
        # Build command
        CMD="python main.py $INPUT_SOURCE"
        
        if [ "$LOCAL_FILE" = "true" ]; then
            CMD="$CMD --local"
        fi
        
        if [ "$TEST_MODE" = "true" ]; then
            CMD="$CMD --test"
        fi
        
        print_info "Executing: $CMD"
        exec $CMD
        ;;
        
    "single")
        if [ -z "$SINGLE_UPC" ]; then
            print_error "SINGLE_UPC environment variable is required for single mode"
            exit 1
        fi
        
        print_info "Processing single UPC: $SINGLE_UPC"
        exec python main.py dummy --single "$SINGLE_UPC"
        ;;
        
    "test")
        print_info "Running in test mode with sample UPCs"
        # Create a test file with sample UPCs
        echo "722975007524" > /tmp/test_upcs.txt
        echo "638812705228" >> /tmp/test_upcs.txt
        
        exec python main.py /tmp/test_upcs.txt --local --test
        ;;
        
    "shell")
        print_info "Starting interactive shell"
        exec /bin/bash
        ;;
        
    "sleep")
        print_info "Container will sleep indefinitely (for debugging)"
        exec sleep infinity
        ;;
        
    *)
        print_error "Unknown mode: $MODE"
        print_info "Valid modes: batch, single, test, shell, sleep"
        exit 1
        ;;
esac
