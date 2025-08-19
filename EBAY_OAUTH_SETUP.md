# eBay OAuth Setup Instructions

## Overview
The eBay OAuth workflow has been successfully implemented and deployed to production. The application is now ready to receive authorization from your eBay account.

## Production Deployment Details
- **Service URL**: https://draft-maker-541660382374.us-west1.run.app
- **OAuth Callback URL**: https://draft-maker-541660382374.us-west1.run.app/oauth/callback
- **Status**: ✅ Live and ready for authorization

## Complete the OAuth Authorization

### Step 1: Start the Authorization Process
Visit the following URL in your web browser:
```
https://draft-maker-541660382374.us-west1.run.app/oauth/authorize
```

Or directly visit the eBay authorization URL:
```
https://auth.ebay.com/oauth2/authorize?client_id=Benjamin-valuefin-PRD-90b84f3d7-dc4df0a4&response_type=code&redirect_uri=https://draft-maker-541660382374.us-west1.run.app/oauth/callback&scope=https://api.ebay.com/oauth/api_scope/sell.inventory&prompt=login
```

### Step 2: Log into eBay
1. Enter your eBay username and password
2. Complete any two-factor authentication if enabled

### Step 3: Grant Permissions
1. Review the permissions requested by the application:
   - Access to Sell Inventory APIs
   - Ability to create and manage draft listings
2. Click "Agree" or "Allow" to grant these permissions

### Step 4: Automatic Token Storage
After granting permissions, you'll be automatically redirected to:
- `https://draft-maker-541660382374.us-west1.run.app/oauth/callback`
- The application will exchange the authorization code for tokens
- Tokens will be stored securely in Firestore
- You'll see a success message confirming the authorization

## Verify Token Status
After completing the authorization, you can verify the token status at:
```
https://draft-maker-541660382374.us-west1.run.app/oauth/status
```

This endpoint will show:
- Whether tokens are configured
- Token validity status
- Presence of refresh token
- Token expiration time

## Available Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Health check and welcome page with instructions |
| `/oauth/authorize` | Start the OAuth authorization flow |
| `/oauth/callback` | OAuth callback (handled automatically) |
| `/oauth/status` | Check current token status |

## Token Management
- **Access Token**: Valid for 2 hours, automatically refreshed
- **Refresh Token**: Valid for 18 months, used to obtain new access tokens
- **Storage**: Tokens are stored in Firestore collection `api_tokens`
- **Automatic Refresh**: The application automatically refreshes expired access tokens

## Troubleshooting

### If Authorization Fails
1. Check that you're logged into the correct eBay account
2. Ensure you have a seller account on eBay
3. Try clearing browser cookies and attempting again
4. Visit `/oauth/status` to check current token state

### Common Issues
- **"No authorization code provided"**: The OAuth flow was cancelled or interrupted
- **"Token exchange failed"**: Network issue or invalid credentials
- **"Permission denied"**: The eBay account may not have seller privileges

## Security Notes
- Tokens are encrypted and stored securely in Firestore
- The application uses HTTPS for all communications
- OAuth 2.0 authorization code flow ensures secure token exchange
- Refresh tokens allow long-term access without storing passwords

## Next Steps
Once authorization is complete:
1. The application can now create draft listings on eBay
2. Run batch processing to convert UPC codes to draft listings
3. Use the existing `main.py --batch` mode for processing

## Environment Variables Set
The following environment variables have been configured in Cloud Run:
- `EBAY_APP_ID`: Your eBay application ID
- `EBAY_CERT_ID`: Your eBay certificate ID
- `EBAY_DEV_ID`: Your eBay developer ID
- `EBAY_CLIENT_SECRET`: Your eBay client secret
- `APP_MODE`: Set to "web" for OAuth server
- `ENVIRONMENT`: Set to "production"
- `GCP_PROJECT_ID`: draft-maker-468923

## Monitoring
View logs and monitor the application:
```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=draft-maker" --limit 50 --format json

# Check service status
gcloud run services describe draft-maker --region us-west1
```

## Support
For any issues or questions:
1. Check the Cloud Run logs for detailed error messages
2. Verify token status at `/oauth/status`
3. Review the Firestore `api_tokens` collection for stored tokens
