# Draft Maker Deployment Configuration

This document describes the deployment configuration for both staging and production environments.

## Overview

The Draft Maker application is configured to deploy to:
- **Staging**: Local Docker container (self-hosted runner)
- **Production**: Google Cloud Run

Both environments connect to the same Firestore database (`draft-maker-database`) in the `draft-maker-468923` project.

## Google Cloud Resources

### Project Information
- **Project ID**: `draft-maker-468923`
- **Region**: `us-west1`
- **Cloud Run URL**: https://draft-maker-541660382374.us-west1.run.app

### Resources
- **Firestore Database**: `draft-maker-database` (us-west1)
- **Storage Bucket**: `draft-maker-bucket` (us-west1)
- **Service Accounts**:
  - `draft-maker-identity@draft-maker-468923.iam.gserviceaccount.com` - Application service account
  - `github-actions@draft-maker-468923.iam.gserviceaccount.com` - CI/CD service account

## Environment Configuration

### Production Environment (`.env.production`)
The production environment file contains all necessary configuration for Cloud Run deployment:
- GCP project and region settings
- Firestore database and collection names
- API credentials (stored in Secret Manager for production)
- Application settings

### Staging Environment (`.env.staging`)
The staging environment file is similar to production but with `ENVIRONMENT="staging"` to differentiate logs and monitoring.

## Deployment Workflows

### Production Deployment
- **Trigger**: Push to `main` branch
- **Target**: Google Cloud Run
- **Workflow**: `.github/workflows/production-deploy.yml`
- **Features**:
  - Builds and pushes Docker image to Artifact Registry
  - Deploys to Cloud Run with environment variables
  - Uses Secret Manager for sensitive values
  - Service account: `draft-maker-identity@draft-maker-468923.iam.gserviceaccount.com`

### Staging Deployment
- **Trigger**: Push to `develop` branch
- **Target**: Local Docker container
- **Workflow**: `.github/workflows/staging-deploy.yml`
- **Features**:
  - Builds Docker image locally
  - Runs container with mounted environment file
  - Mounts service account key for GCP authentication
  - Port mapping: 8080:8080

## Setup Instructions

### 1. Initial Setup
Run the service account setup script to configure authentication:

```bash
./scripts/setup-service-accounts.sh
```

Choose option 6 for complete setup, which will:
- Create service account keys for staging
- Verify permissions
- Grant necessary IAM roles
- Setup secrets in Secret Manager

### 2. Service Account Permissions

Both service accounts require the following roles:

**draft-maker-identity** (Application):
- Cloud Datastore User
- Storage Object Admin
- Secret Manager Secret Accessor

**github-actions** (CI/CD):
- Cloud Run Admin
- Service Account User
- Artifact Registry Writer
- Secret Manager Secret Accessor

### 3. Secret Management

Secrets are stored in Google Secret Manager. The following secrets need to be configured:
- `DISCOGS_PERSONAL_ACCESS_TOKEN`
- `EBAY_APP_ID`
- `EBAY_DEV_ID`
- `EBAY_CERT_ID`
- `EBAY_CLIENT_SECRET`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`

To create/update secrets:
```bash
echo -n "secret-value" | gcloud secrets create SECRET_NAME --data-file=-
```

### 4. Local Development

For local development with GCP services:

1. Create service account key:
```bash
gcloud iam service-accounts keys create keys/draft-maker-identity-key.json \
  --iam-account=draft-maker-identity@draft-maker-468923.iam.gserviceaccount.com
```

2. Set environment variable:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/keys/draft-maker-identity-key.json"
```

3. Run the application:
```bash
python main.py
```

## Testing Database Connectivity

### Staging Environment
```bash
# Deploy to staging
git push origin develop

# Check logs
docker logs draft-maker-staging

# Test database connection
docker exec draft-maker-staging python -c "
from google.cloud import firestore
db = firestore.Client(project='draft-maker-468923', database='draft-maker-database')
print('Connected to Firestore')
"
```

### Production Environment
```bash
# Deploy to production
git push origin main

# Check Cloud Run logs
gcloud run services logs read draft-maker --region=us-west1

# Test via API endpoint
curl https://draft-maker-541660382374.us-west1.run.app/health
```

## Troubleshooting

### Common Issues

1. **Authentication Error in Staging**
   - Ensure service account key exists: `keys/draft-maker-identity-key.json`
   - Run setup script: `./scripts/setup-service-accounts.sh`

2. **Permission Denied for Firestore**
   - Verify service account has Cloud Datastore User role
   - Check project ID and database name in environment files

3. **Secret Manager Access Issues**
   - Ensure secrets exist in Secret Manager
   - Verify service accounts have Secret Accessor role

4. **Cloud Run Deployment Fails**
   - Check GitHub secrets are configured correctly
   - Verify Workload Identity Federation is set up
   - Ensure docker image builds successfully

## Monitoring

### Staging
- Docker logs: `docker logs -f draft-maker-staging`
- Container status: `docker ps`

### Production
- Cloud Run metrics: [Console](https://console.cloud.google.com/run)
- Logs: `gcloud run services logs read draft-maker --region=us-west1`
- Firestore usage: [Console](https://console.cloud.google.com/firestore)

## Security Notes

1. **Never commit service account keys** - Added to `.gitignore`
2. **Use Secret Manager** for all sensitive values in production
3. **Rotate service account keys** regularly
4. **Monitor IAM permissions** and follow principle of least privilege
5. **Enable audit logging** for production resources

## Contact

For issues or questions about deployment:
- Email: benjaminabramowitz@gmail.com
- Project: draft-maker-468923
