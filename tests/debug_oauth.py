#!/usr/bin/env python3
"""
Debug script to test eBay OAuth configuration and identify issues.
"""

import sys
import os
import base64
from urllib.parse import urlencode, unquote
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def check_environment():
    """Check environment and configuration."""
    print("\n" + "=" * 60)
    print("eBay OAuth Configuration Debug")
    print("=" * 60 + "\n")

    print("1. Environment Variables:")
    print("-" * 40)
    print(f"Environment: {settings.environment}")
    print(f"GCP Project: {settings.gcp_project_id}")
    print()

    print("2. eBay API Credentials:")
    print("-" * 40)
    # Only show first/last few characters for security
    app_id = settings.ebay_app_id
    cert_id = settings.ebay_cert_id
    dev_id = settings.ebay_dev_id

    if app_id:
        print(f"App ID: {app_id[:8]}...{app_id[-4:]} (length: {len(app_id)})")
    else:
        print("App ID: NOT SET")

    if cert_id:
        print(f"Cert ID: {cert_id[:8]}...{cert_id[-4:]} (length: {len(cert_id)})")
    else:
        print("Cert ID: NOT SET")

    if dev_id:
        print(f"Dev ID: {dev_id[:8]}...{dev_id[-4:]} (length: {len(dev_id)})")
    else:
        print("Dev ID: NOT SET")
    print()

    print("3. OAuth URLs:")
    print("-" * 40)
    redirect_uri = "https://draft-maker-541660382374.us-west1.run.app/oauth/callback"
    print(f"Redirect URI: {redirect_uri}")
    print(f"Auth URL: https://auth.ebay.com/oauth2/authorize")
    print(f"Token URL: https://api.ebay.com/identity/v1/oauth2/token")
    print()


def generate_auth_url():
    """Generate the authorization URL."""
    redirect_uri = "https://draft-maker-541660382374.us-west1.run.app/oauth/callback"

    params = {
        "client_id": settings.ebay_app_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory",
        "prompt": "login",
    }

    auth_url = f"https://auth.ebay.com/oauth2/authorize?{urlencode(params)}"

    print("4. Generated Authorization URL:")
    print("-" * 40)
    print(auth_url)
    print()

    print("5. URL Components:")
    print("-" * 40)
    for key, value in params.items():
        print(f"{key}: {value}")
    print()

    return auth_url


def decode_auth_code(auth_code):
    """Decode and analyze the authorization code."""
    print("6. Authorization Code Analysis:")
    print("-" * 40)

    # URL decode the code
    decoded_code = unquote(auth_code)
    print(f"Original: {auth_code[:50]}...")
    print(f"Decoded: {decoded_code[:50]}...")
    print(f"Length: {len(auth_code)}")
    print()

    return decoded_code


def test_token_exchange(auth_code):
    """Show what will be sent for token exchange."""
    redirect_uri = "https://draft-maker-541660382374.us-west1.run.app/oauth/callback"

    print("7. Token Exchange Request:")
    print("-" * 40)

    # Prepare credentials
    credentials = f"{settings.ebay_app_id}:{settings.ebay_cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    print(f"Authorization Header: Basic {encoded_credentials[:20]}...")
    print(f"Content-Type: application/x-www-form-urlencoded")
    print()

    print("Request Body:")
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
    }

    for key, value in data.items():
        if key == "code":
            print(f"  {key}: {value[:50]}...")
        else:
            print(f"  {key}: {value}")
    print()


def main():
    """Main function."""
    check_environment()
    auth_url = generate_auth_url()

    print("INSTRUCTIONS:")
    print("-" * 40)
    print("1. Visit the authorization URL above")
    print("2. Log in with your eBay account")
    print("3. Grant permissions")
    print("4. Copy the ENTIRE URL from your browser after redirect")
    print("5. Paste it here to analyze")
    print()

    callback_url = input("Paste the full callback URL here: ").strip()

    if callback_url:
        # Extract the authorization code from the URL
        if "code=" in callback_url:
            code_part = callback_url.split("code=")[1]
            if "&" in code_part:
                auth_code = code_part.split("&")[0]
            else:
                auth_code = code_part

            print("\nExtracted Authorization Code:")
            print("-" * 40)
            print(f"Code: {auth_code[:50]}...")
            print()

            decoded_code = decode_auth_code(auth_code)
            test_token_exchange(auth_code)

            print("\nNEXT STEPS:")
            print("-" * 40)
            print(
                "1. Verify the redirect URI above matches EXACTLY what's in eBay Developer Account"
            )
            print("2. Make sure you're using the Production App ID, not Sandbox")
            print("3. The authorization code expires in 5 minutes - use it quickly")
            print(
                "4. If still failing, check eBay Developer Account for the RuName configuration"
            )
        else:
            print("\nERROR: No authorization code found in the URL")
            print("The URL should contain '?code=...' or '&code=...'")


if __name__ == "__main__":
    main()
