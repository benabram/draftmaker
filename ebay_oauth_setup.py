#!/usr/bin/env python3
"""
Complete eBay OAuth Setup Script
This script handles the full OAuth flow for eBay API access.
"""

import sys
import os
import base64
import time
import json
from urllib.parse import urlencode, unquote, parse_qs, urlparse
import httpx
import asyncio
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import settings
from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# eBay OAuth endpoints (Production)
EBAY_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
REDIRECT_URI = "https://draft-maker-541660382374.us-west1.run.app/oauth/callback"

class EbayOAuthSetup:
    """Complete eBay OAuth setup handler."""
    
    def __init__(self):
        self.redirect_uri = REDIRECT_URI
        self.app_id = settings.ebay_app_id
        self.cert_id = settings.ebay_cert_id
        
    def generate_auth_url(self, state=None):
        """Generate the authorization URL with optional state parameter."""
        params = {
            "client_id": self.app_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory",
            "prompt": "login"
        }
        
        if state:
            params["state"] = state
            
        return f"{EBAY_AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, auth_code):
        """Exchange authorization code for access and refresh tokens."""
        # Prepare Basic Auth header
        credentials = f"{self.app_id}:{self.cert_id}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # Important: Use the URL-encoded version of the code directly
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,  # Pass the code as-is (already URL encoded)
            "redirect_uri": self.redirect_uri
        }
        
        logger.info(f"Exchanging code for tokens...")
        logger.debug(f"Using redirect_uri: {self.redirect_uri}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    EBAY_TOKEN_URL,
                    headers=headers,
                    data=data,
                    timeout=30.0
                )
                
                logger.debug(f"Token exchange response status: {response.status_code}")
                
                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"Token exchange failed with status {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f": {json.dumps(error_data, indent=2)}"
                    except:
                        error_msg += f": {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
            except httpx.TimeoutException:
                raise Exception("Token exchange request timed out")
            except Exception as e:
                logger.error(f"Token exchange error: {str(e)}")
                raise
    
    async def save_tokens(self, token_response):
        """Save tokens to Firestore."""
        token_manager = get_token_manager()
        
        await token_manager.set_initial_ebay_token(
            access_token=token_response["access_token"],
            refresh_token=token_response["refresh_token"],
            expires_in=token_response["expires_in"]
        )
        
        logger.info("Tokens successfully saved to Firestore")
        
    def extract_code_from_url(self, callback_url):
        """Extract authorization code from callback URL."""
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        
        if "code" not in params:
            if "error" in params:
                error = params.get("error", ["Unknown error"])[0]
                error_desc = params.get("error_description", ["No description"])[0]
                raise Exception(f"Authorization failed: {error} - {error_desc}")
            else:
                raise Exception("No authorization code found in callback URL")
        
        # Get the first code value (parse_qs returns lists)
        code = params["code"][0]
        expires_in = params.get("expires_in", ["300"])[0]
        
        return code, int(expires_in)

async def main():
    """Main setup flow."""
    print("\n" + "="*70)
    print("🔐 eBay OAuth Setup for Production")
    print("="*70 + "\n")
    
    setup = EbayOAuthSetup()
    
    print("📋 Configuration Details:")
    print("-" * 50)
    print(f"App ID: {setup.app_id[:8]}...{setup.app_id[-4:]}")
    print(f"Redirect URI: {setup.redirect_uri}")
    print(f"Environment: Production")
    print()
    
    # Generate state for security (optional but recommended)
    import secrets
    state = secrets.token_urlsafe(16)
    
    auth_url = setup.generate_auth_url(state)
    
    print("🌐 Step 1: Authorization")
    print("-" * 50)
    print("Please visit this URL to authorize the application:")
    print()
    print(auth_url)
    print()
    print("Instructions:")
    print("1. Open the URL above in your browser")
    print("2. Log in with your eBay seller account")
    print("3. Review and accept the permissions")
    print("4. You'll be redirected to a URL that may show an error page")
    print("5. Copy the ENTIRE URL from your browser's address bar")
    print()
    
    callback_url = input("Paste the complete callback URL here: ").strip()
    
    if not callback_url:
        print("\n❌ No URL provided. Exiting.")
        return
    
    try:
        # Extract authorization code
        auth_code, expires_in = setup.extract_code_from_url(callback_url)
        
        print(f"\n✅ Authorization code extracted (expires in {expires_in} seconds)")
        print(f"   Code: {auth_code[:30]}...")
        
        # Check if state matches (for security)
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)
        returned_state = params.get("state", [None])[0]
        
        if returned_state != state:
            print("\n⚠️  Warning: State parameter mismatch (possible security issue)")
            proceed = input("Continue anyway? (yes/no): ").strip().lower()
            if proceed != "yes":
                print("Aborting for security reasons.")
                return
        
        print("\n🔄 Step 2: Token Exchange")
        print("-" * 50)
        print("Exchanging authorization code for tokens...")
        
        # Exchange code for tokens
        token_response = await setup.exchange_code_for_tokens(auth_code)
        
        print("\n✅ Tokens received successfully!")
        print(f"   Access Token: {token_response['access_token'][:30]}...")
        print(f"   Refresh Token: {token_response['refresh_token'][:30]}...")
        print(f"   Expires in: {token_response['expires_in']} seconds")
        
        # Save tokens
        print("\n💾 Step 3: Saving Tokens")
        print("-" * 50)
        await setup.save_tokens(token_response)
        
        print("\n" + "="*70)
        print("🎉 SUCCESS! eBay OAuth setup is complete!")
        print("="*70)
        print("\nThe application can now:")
        print("✅ Create draft listings on eBay")
        print("✅ Access inventory management APIs")
        print("✅ Automatically refresh tokens when needed")
        print("\nTokens are stored in Firestore and will be automatically")
        print("refreshed before they expire.")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure you're using a fresh authorization code (they expire in 5 minutes)")
        print("2. Verify the redirect URI in eBay matches exactly:")
        print(f"   {setup.redirect_uri}")
        print("3. Check that you're using Production credentials, not Sandbox")
        print("4. Try generating a new authorization code and repeat the process")
        return

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
