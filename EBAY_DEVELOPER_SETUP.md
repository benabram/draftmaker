# eBay Developer Account Configuration Guide

## Prerequisites
Before starting, ensure you have:
- An eBay Developer Account (https://developer.ebay.com)
- Your Production App created in the eBay Developer Program
- Access to your App ID, Cert ID, and Dev ID

## Step 1: Log into eBay Developer Account

1. Go to https://developer.ebay.com
2. Sign in with your developer account credentials
3. Navigate to "My Account" → "Application Keys"

## Step 2: Configure Production App OAuth Settings

### Navigate to User Tokens Section

1. In the Application Keys page, find your **Production** app (NOT Sandbox)
2. Look for the section titled "User Tokens" or "Auth'n'Auth"
3. Click on "Get a Token from eBay via Your Application" or "User token"

### Configure RuName (Redirect URL Name)

⚠️ **CRITICAL**: The redirect URI must match EXACTLY what your application uses.

1. Click on "Add eBay Redirect URL" or "RuName" configuration
2. Enter the following details:

   **Application/Display Name**: Draft Maker
   
   **Accept URL (MOST IMPORTANT)**: 
   ```
   https://draft-maker-541660382374.us-west1.run.app/oauth/callback
   ```
   
   **Decline URL**: 
   ```
   https://draft-maker-541660382374.us-west1.run.app/oauth/decline
   ```
   
   **Privacy Policy URL**: 
   ```
   https://draft-maker-541660382374.us-west1.run.app/privacy
   ```
   (Or use your actual privacy policy URL if you have one)

3. Click "Save" or "Generate RuName"

4. **IMPORTANT**: Copy and save the generated RuName. It will look something like:
   ```
   Benjamin-valuefin-PRD-90b84f3d7-dc4df0a4
   ```

## Step 3: Verify OAuth Scopes

Ensure your application has access to the required scopes:

1. In the Application Keys page, check the "OAuth Scope" section
2. Verify you have access to at least:
   - `https://api.ebay.com/oauth/api_scope/sell.inventory`
   - Additional scopes as needed for your application

If scopes are missing:
1. Click "Update Application"
2. Add the required scopes
3. Submit for approval (if required)

## Step 4: Test Your Configuration

### Using the CLI Setup Script

1. Activate your Python environment:
   ```bash
   cd /home/benbuntu/draftmaker
   source venv/bin/activate
   ```

2. Run the new OAuth setup script:
   ```bash
   python ebay_oauth_setup.py
   ```

3. Follow the prompts:
   - Open the generated URL in a browser
   - Log into eBay with your seller account
   - Grant the requested permissions
   - Copy the ENTIRE redirect URL (even if it shows an error page)
   - Paste it back into the script

### Common Issues and Solutions

#### Issue: "invalid_grant" error
**Causes:**
- Authorization code already used (they're single-use)
- Authorization code expired (5-minute expiry)
- Redirect URI mismatch

**Solution:**
1. Generate a new authorization code
2. Use it immediately (within 5 minutes)
3. Verify redirect URI matches exactly

#### Issue: "invalid_client" error
**Causes:**
- Wrong App ID or Cert ID
- Using Sandbox credentials for Production

**Solution:**
1. Verify you're using Production credentials
2. Check credentials in `.env` file match eBay Developer Account

#### Issue: Redirect shows error page
**Normal behavior** - Your Cloud Run app might not be running or accessible from your browser. This is OK! Just copy the URL with the authorization code.

## Step 5: Verify Token Storage

After successful OAuth setup:

1. Check Firestore to verify tokens are stored:
   ```bash
   gcloud firestore documents read api_tokens/ebay \
     --project=draft-maker-468923 \
     --database=(default)
   ```

2. Test token refresh capability:
   ```python
   from src.utils.token_manager import get_token_manager
   import asyncio
   
   async def test():
       tm = get_token_manager()
       token = await tm.get_ebay_token()
       print(f"Token retrieved: {token[:30]}...")
   
   asyncio.run(test())
   ```

## Important Notes

1. **Production vs Sandbox**: Always use Production environment for real listings
2. **Token Expiry**: Access tokens expire in 2 hours, refresh tokens in ~18 months
3. **Security**: Never share your refresh token or store it in code
4. **Rate Limits**: eBay has API rate limits - implement proper throttling

## Next Steps

Once OAuth is configured:
1. Test creating a draft listing
2. Set up automated token refresh
3. Monitor token expiry and refresh cycles
4. Implement error handling for token failures

## Support Resources

- eBay OAuth Guide: https://developer.ebay.com/api-docs/static/oauth-authorization-code-grant.html
- eBay Developer Forums: https://community.ebay.com/t5/Developer-Groups/ct-p/developergroup
- API Status: https://developer.ebay.com/support/api-status
