# Docker Staging Deployment Guide

## Overview

The staging Docker container is configured to run as a **batch processing job** rather than a continuously running service. This is because the Draft Maker application is designed to process UPC codes from input files and create eBay draft listings.

## Why Staging Deployment Wasn't Working

1. **No GitHub Actions Self-Hosted Runner**: The `.github/workflows/staging-deploy.yml` workflow requires a self-hosted runner that wasn't installed
2. **Application Design**: The application expects command-line arguments (input file path), making it unsuitable as a persistent service

## Solutions Implemented

### 1. Docker Entrypoint Script
Created `docker-entrypoint.sh` that supports multiple operation modes:
- **batch**: Process a batch file (local or GCS)
- **single**: Process a single UPC
- **test**: Run with sample UPCs
- **shell**: Interactive shell for debugging
- **sleep**: Keep container running for debugging

### 2. Docker Management Script
Created `scripts/docker-staging.sh` for easy container management:

```bash
# Build the Docker image
./scripts/docker-staging.sh build

# Run in test mode
./scripts/docker-staging.sh run-test

# Process a batch file
./scripts/docker-staging.sh run-batch data/upcs.txt --local
./scripts/docker-staging.sh run-batch gs://bucket/file.txt

# Process a single UPC
./scripts/docker-staging.sh run-single 722975007524

# Start interactive shell
./scripts/docker-staging.sh run-shell

# Check status
./scripts/docker-staging.sh status
```

### 3. Docker Compose Setup
Created `docker-compose.staging.yml` for advanced deployments with a scheduler that monitors for batch files.

## How to Use

### Option 1: Manual Batch Processing

```bash
# Build the image
./scripts/docker-staging.sh build

# Create a file with UPC codes
echo "722975007524" > data/batch.txt
echo "638812705228" >> data/batch.txt

# Process the batch
./scripts/docker-staging.sh run-batch /app/data/batch.txt --local
```

### Option 2: Scheduled Processing

```bash
# Start the scheduler (checks every 5 minutes for data/batch.txt)
./scripts/docker-staging.sh start-scheduler

# Place UPC codes in data/batch.txt
echo "722975007524" > data/batch.txt

# The scheduler will automatically process it
```

### Option 3: Install GitHub Actions Runner

To enable automatic deployment on push to develop branch:

```bash
# Run the setup script
./scripts/setup-github-runner.sh

# Follow the prompts to register the runner
# Once installed, pushing to develop will trigger automatic deployment
```

## Environment Variables

The container uses environment variables from `.env.staging`:
- `GCP_PROJECT_ID`: Google Cloud project ID
- `FIRESTORE_DATABASE_NAME`: Firestore database (default)
- `STORAGE_BUCKET_NAME`: GCS bucket for files
- API credentials for Discogs, eBay, Spotify, etc.

## Service Account

Ensure the service account key exists:
```bash
ls -la keys/draft-maker-identity-key.json
```

If missing, run:
```bash
./scripts/setup-service-accounts.sh
```

## Debugging

### View Container Logs
```bash
# For running containers
docker logs -f draft-maker-staging

# For completed runs
docker logs draft-maker-test
```

### Interactive Debugging
```bash
# Start container with shell
./scripts/docker-staging.sh run-shell

# Or start in sleep mode and exec into it
./scripts/docker-staging.sh run-debug
docker exec -it draft-maker-debug /bin/bash
```

### Check Container Status
```bash
./scripts/docker-staging.sh status
```

## Deployment Workflow

### Development Workflow
1. Make changes to code
2. Build Docker image: `./scripts/docker-staging.sh build`
3. Test locally: `./scripts/docker-staging.sh run-test`
4. Commit and push to develop branch

### With GitHub Actions Runner (Recommended)
1. Install runner: `./scripts/setup-github-runner.sh`
2. Push to develop branch
3. Runner automatically builds and deploys

### Without GitHub Actions Runner
1. Pull latest changes: `git pull origin develop`
2. Run manual deployment: `./scripts/deploy-staging-local.sh`
3. Or use Docker commands: `./scripts/docker-staging.sh build`

## Architecture Notes

- **Batch Processing**: The application processes UPC codes from files
- **Not a Web Service**: No HTTP endpoints or persistent server
- **Firestore Backend**: Uses Google Firestore for data storage
- **API Integrations**: Calls MusicBrainz, Discogs, Spotify, and eBay APIs

## Troubleshooting

### Container Exits Immediately
- The application requires an input file argument
- Use one of the provided modes (test, batch, single, shell, sleep)

### Permission Denied
```bash
chmod +x scripts/*.sh docker-entrypoint.sh
```

### Service Account Issues
```bash
# Check if key exists
ls -la keys/draft-maker-identity-key.json

# Create if missing
./scripts/setup-service-accounts.sh
```

### Build Failures
```bash
# Clean and rebuild
./scripts/docker-staging.sh clean
./scripts/docker-staging.sh build
```

## Next Steps

For a production-ready staging environment, consider:

1. **Install GitHub Actions Runner** for automatic deployments
2. **Set up Cloud Scheduler** for periodic batch processing
3. **Add monitoring** with logs aggregation
4. **Implement a queue system** for processing requests
5. **Create a web API** if real-time processing is needed
