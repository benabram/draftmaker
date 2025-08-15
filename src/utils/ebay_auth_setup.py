#!/usr/bin/env python3
"""
CLI utility for setting up eBay OAuth tokens.

This script helps with the initial eBay OAuth setup by:
1. Generating the authorization URL for user consent
2. Processing the authorization code to get initial tokens
3. Storing the tokens in Firestore for future use
"""

import sys
import asyncio
import base64
from urllib.parse import urlencode
import httpx
from src.config import settings
from src.utils.token_manager import get_token_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# eBay OAuth endpoints (Production only - sandbox is broken)
EBAY_AUTH_URL = "https://auth.ebay.com/oauth2/authorize"
EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"


class EbayAuthSetup:
    """Helper class for eBay OAuth setup."""
    
    def __init__(self):
        """Initialize the auth setup."""
        self.auth_url = EBAY_AUTH_URL
        self.token_url = EBAY_TOKEN_URL
        self.redirect_uri = "https://localhost:3000/callback"  # Default redirect URI
        
    def generate_auth_url(self) -> str:
        """
        Generate the authorization URL for user consent.
        
        Returns:
            The authorization URL
        """
        params = {
            "client_id": settings.ebay_app_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory",
            "prompt": "login"
        }
        
        return f"{self.auth_url}?{urlencode(params)}"
        
    async def exchange_code_for_tokens(self, authorization_code: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            authorization_code: The authorization code from eBay
            
        Returns:
            Token response from eBay
        """
        # Prepare credentials
        credentials = f"{settings.ebay_app_id}:{settings.ebay_cert_id}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, headers=headers, data=data)
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise Exception(f"Failed to exchange code for tokens: {response.status_code}")
                
        return response.json()
        
    async def setup_initial_tokens(self, authorization_code: str):
        """
        Complete the initial token setup process.
        
        Args:
            authorization_code: The authorization code from eBay
        """
        try:
            # Exchange code for tokens
            logger.info("Exchanging authorization code for tokens...")
            token_response = await self.exchange_code_for_tokens(authorization_code)
            
            # Save tokens using token manager
            token_manager = get_token_manager()
            await token_manager.set_initial_ebay_token(
                access_token=token_response["access_token"],
                refresh_token=token_response["refresh_token"],
                expires_in=token_response["expires_in"]
            )
            
            logger.info("✅ eBay tokens successfully saved!")
            logger.info(f"Access token expires in {token_response['expires_in']} seconds")
            
        except Exception as e:
            logger.error(f"Failed to setup tokens: {e}")
            raise


async def main():
    """Main CLI function."""
    print("\n" + "="*60)
    print("eBay OAuth Setup Utility (Production)")
    print("="*60 + "\n")
    
    setup = EbayAuthSetup()
    
    print("Step 1: Authorization")
    print("-" * 40)
    print("Please visit the following URL to authorize the application:")
    print()
    auth_url = setup.generate_auth_url()
    print(auth_url)
    print()
    print("After authorizing, you will be redirected to a URL that looks like:")
    print("https://localhost:3000/callback?code=AUTHORIZATION_CODE&expires_in=299")
    print()
    
    # Get the authorization code from user
    auth_code = input("Enter the authorization code from the redirect URL: ").strip()
    
    if not auth_code:
        print("❌ No authorization code provided. Exiting.")
        sys.exit(1)
        
    print("\nStep 2: Token Exchange")
    print("-" * 40)
    
    await setup.setup_initial_tokens(auth_code)
    
    print("\n✅ Setup complete! The application can now use eBay APIs.")
    print("="*60 + "\n")


def run_cli():
    """Run the CLI utility."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Add parent directory to path for imports
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    run_cli()
