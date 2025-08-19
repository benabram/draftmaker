#!/bin/bash

# Docker Staging Management Script
# This script helps manage the Docker staging environment

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

# Function to show usage
show_usage() {
    print_colored $BLUE "Docker Staging Management Script"
    echo
    print_colored $YELLOW "Usage: $0 [command] [options]"
    echo
    print_colored $YELLOW "Commands:"
    echo "  build           - Build the Docker image"
    echo "  run-test        - Run container in test mode"
    echo "  run-batch FILE  - Process a batch file"
    echo "  run-single UPC  - Process a single UPC"
    echo "  run-shell       - Start interactive shell in container"
    echo "  run-debug       - Start container in sleep mode for debugging"
    echo "  start-scheduler - Start the batch scheduler service"
    echo "  stop            - Stop all containers"
    echo "  logs [container]- View container logs"
    echo "  status          - Show container status"
    echo "  clean           - Remove containers and images"
    echo
    print_colored $YELLOW "Examples:"
    echo "  $0 build                                    # Build the image"
    echo "  $0 run-test                                 # Run in test mode"
    echo "  $0 run-batch gs://bucket/file.txt          # Process GCS file"
    echo "  $0 run-batch /app/data/local.txt --local   # Process local file"
    echo "  $0 run-single 722975007524                 # Process single UPC"
    echo "  $0 start-scheduler                         # Start batch scheduler"
    echo "  $0 logs draft-maker-staging                # View logs"
}

# Change to project directory
cd /home/benbuntu/draftmaker

case "$1" in
    build)
        print_colored $YELLOW "Building Docker image..."
        docker build -f Dockerfile.production -t draft-maker-staging:latest .
        print_colored $GREEN "✓ Image built successfully"
        ;;
        
    run-test)
        print_colored $YELLOW "Running in test mode..."
        docker run --rm \
            --name draft-maker-test \
            -e MODE=test \
            -v $(pwd)/.env.staging:/app/.env:ro \
            -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
            -v $(pwd)/logs:/app/logs \
            -v $(pwd)/output:/app/output \
            -v $(pwd)/data:/app/data:ro \
            draft-maker-staging:latest
        ;;
        
    run-batch)
        if [ -z "$2" ]; then
            print_colored $RED "Error: Input source required"
            echo "Usage: $0 run-batch <file-path>"
            exit 1
        fi
        
        INPUT_SOURCE="$2"
        LOCAL_FLAG=""
        
        if [ "$3" == "--local" ]; then
            LOCAL_FLAG="-e LOCAL_FILE=true"
        fi
        
        print_colored $YELLOW "Processing batch file: $INPUT_SOURCE"
        docker run --rm \
            --name draft-maker-batch \
            -e MODE=batch \
            -e INPUT_SOURCE="$INPUT_SOURCE" \
            $LOCAL_FLAG \
            -v $(pwd)/.env.staging:/app/.env:ro \
            -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
            -v $(pwd)/logs:/app/logs \
            -v $(pwd)/output:/app/output \
            -v $(pwd)/data:/app/data:ro \
            draft-maker-staging:latest
        ;;
        
    run-single)
        if [ -z "$2" ]; then
            print_colored $RED "Error: UPC required"
            echo "Usage: $0 run-single <upc>"
            exit 1
        fi
        
        print_colored $YELLOW "Processing single UPC: $2"
        docker run --rm \
            --name draft-maker-single \
            -e MODE=single \
            -e SINGLE_UPC="$2" \
            -v $(pwd)/.env.staging:/app/.env:ro \
            -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
            -v $(pwd)/logs:/app/logs \
            -v $(pwd)/output:/app/output \
            draft-maker-staging:latest
        ;;
        
    run-shell)
        print_colored $YELLOW "Starting interactive shell..."
        docker run -it --rm \
            --name draft-maker-shell \
            -e MODE=shell \
            -v $(pwd)/.env.staging:/app/.env:ro \
            -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
            -v $(pwd)/logs:/app/logs \
            -v $(pwd)/output:/app/output \
            -v $(pwd)/data:/app/data:ro \
            draft-maker-staging:latest
        ;;
        
    run-debug)
        print_colored $YELLOW "Starting container in debug mode (will sleep)..."
        docker run -d \
            --name draft-maker-debug \
            -e MODE=sleep \
            -v $(pwd)/.env.staging:/app/.env:ro \
            -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
            -v $(pwd)/logs:/app/logs \
            -v $(pwd)/output:/app/output \
            -v $(pwd)/data:/app/data:ro \
            draft-maker-staging:latest
        print_colored $GREEN "✓ Debug container started"
        print_colored $YELLOW "To connect: docker exec -it draft-maker-debug /bin/bash"
        ;;
        
    start-scheduler)
        print_colored $YELLOW "Starting batch scheduler..."
        docker-compose -f docker-compose.staging.yml up -d draft-maker-scheduler
        print_colored $GREEN "✓ Scheduler started"
        print_colored $YELLOW "Place batch files in data/batch.txt for processing"
        ;;
        
    stop)
        print_colored $YELLOW "Stopping all containers..."
        docker-compose -f docker-compose.staging.yml down
        docker stop draft-maker-test draft-maker-batch draft-maker-single draft-maker-debug 2>/dev/null || true
        print_colored $GREEN "✓ All containers stopped"
        ;;
        
    logs)
        CONTAINER="${2:-draft-maker-staging}"
        print_colored $YELLOW "Showing logs for: $CONTAINER"
        docker logs -f $CONTAINER
        ;;
        
    status)
        print_colored $YELLOW "Container Status:"
        docker ps -a --filter "name=draft-maker" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
        ;;
        
    clean)
        print_colored $YELLOW "Cleaning up containers and images..."
        docker-compose -f docker-compose.staging.yml down -v
        docker rm -f $(docker ps -a -q -f name=draft-maker) 2>/dev/null || true
        docker rmi draft-maker-staging:latest 2>/dev/null || true
        print_colored $GREEN "✓ Cleanup complete"
        ;;
        
    *)
        show_usage
        ;;
esac
