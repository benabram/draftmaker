# Staging Deployment with Self-Hosted GitHub Actions Runner

## Overview

This document describes the staging deployment setup using a self-hosted GitHub Actions runner on a local Ubuntu machine. The deployment uses Docker containers and is triggered automatically when code is pushed to the `develop` branch.

## Architecture

- **Self-Hosted Runner**: DESKTOP-RURNGT7 (Ubuntu Linux)
- **Container**: Docker container running the Draft Maker application
- **Port**: 8080 (http://localhost:8080)
- **Trigger**: Push to `develop` branch
- **Service Account**: draft-maker-identity (stored in `keys/` directory)

## Setup Components

### 1. GitHub Actions Runner

The self-hosted runner is installed at `/home/benbuntu/actions-runner/` and configured with:
- **Name**: DESKTOP-RURNGT7
- **Labels**: self-hosted, Linux, X64
- **Repository**: https://github.com/benabram/draftmaker

### 2. Workflow Configuration

The staging deployment workflow (`.github/workflows/staging-deploy.yml`) includes:
- Automatic Docker image cleanup to prevent disk space issues
- Container health checks
- Volume mounts for configuration and service account keys
- Automatic restart policy

### 3. Environment Configuration

- **Config File**: `.env.staging`
- **Service Account Key**: `keys/draft-maker-identity-key.json`
- **GCP Project**: draft-maker-468923
- **Environment**: staging

## Managing the Runner

Use the helper script `scripts/manage-github-runner.sh` to manage the runner:

```bash
# Install as systemd service (recommended for auto-start)
./scripts/manage-github-runner.sh install

# Check runner status
./scripts/manage-github-runner.sh status

# View runner logs
./scripts/manage-github-runner.sh logs

# Restart the runner
./scripts/manage-github-runner.sh restart

# Stop the runner
./scripts/manage-github-runner.sh stop

# Start the runner
./scripts/manage-github-runner.sh start
```

## Deployment Process

### Automatic Deployment

1. Make changes to your code
2. Commit and push to the `develop` branch:
   ```bash
   git add .
   git commit -m "Your changes"
   git push origin develop
   ```
3. The workflow automatically:
   - Builds a new Docker image
   - Stops and removes the old container
   - Starts a new container with updated code
   - Verifies the deployment

### Manual Deployment

To manually deploy or redeploy:

```bash
# Build the Docker image
docker build -f Dockerfile.production -t draft-maker-staging:latest .

# Stop existing container
docker stop draft-maker-staging || true
docker rm draft-maker-staging || true

# Run new container
docker run -d \
  --name draft-maker-staging \
  --restart unless-stopped \
  -p 8080:8080 \
  -v $(pwd)/.env.staging:/app/.env:ro \
  -v $(pwd)/keys/draft-maker-identity-key.json:/app/service-account-key.json:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/data:/app/data:ro \
  --env-file .env.staging \
  --env GOOGLE_APPLICATION_CREDENTIALS=/app/service-account-key.json \
  draft-maker-staging:latest
```

## Monitoring

### Check Container Status
```bash
docker ps | grep draft-maker-staging
```

### View Container Logs
```bash
docker logs -f draft-maker-staging
```

### Check Application Health
```bash
curl http://localhost:8080
```

### View GitHub Actions Logs
```bash
# If running as systemd service
sudo journalctl -u actions.runner.draftmaker.DESKTOP-RURNGT7.service -f

# If running as process
tail -f /home/benbuntu/actions-runner/runner.log
```

## Troubleshooting

### Runner Not Starting

1. Check if another instance is running:
   ```bash
   ps aux | grep Runner.Listener
   ```

2. Kill any existing processes:
   ```bash
   pkill -f Runner.Listener
   ```

3. Restart the runner:
   ```bash
   ./scripts/manage-github-runner.sh restart
   ```

### Container Not Starting

1. Check for port conflicts:
   ```bash
   sudo lsof -i :8080
   ```

2. Check Docker logs:
   ```bash
   docker logs draft-maker-staging
   ```

3. Verify environment file exists:
   ```bash
   ls -la .env.staging
   ```

4. Verify service account key exists:
   ```bash
   ls -la keys/draft-maker-identity-key.json
   ```

### Deployment Failures

1. Check GitHub Actions tab in the repository
2. Review workflow logs in the Actions tab
3. Check runner logs locally
4. Verify Docker daemon is running:
   ```bash
   sudo systemctl status docker
   ```

## Maintenance

### Clean Up Old Docker Images
```bash
docker image prune -f
docker container prune -f
```

### Update Runner
```bash
cd /home/benbuntu/actions-runner
./scripts/manage-github-runner.sh stop
# Download new runner version from GitHub
# Extract and configure
./scripts/manage-github-runner.sh start
```

### Backup Configuration
Important files to backup:
- `.env.staging`
- `keys/draft-maker-identity-key.json`
- `/home/benbuntu/actions-runner/.runner`
- `/home/benbuntu/actions-runner/.credentials`

## Security Notes

1. The `.env.staging` file contains sensitive credentials and should never be committed to git
2. The service account key in `keys/` directory has restricted permissions (600)
3. The Docker container runs as a non-root user (appuser)
4. Volumes are mounted as read-only where possible
5. The runner should only be accessible from the local network

## Additional Resources

- [GitHub Actions Self-Hosted Runners Documentation](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Docker Documentation](https://docs.docker.com/)
- [Google Cloud Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
