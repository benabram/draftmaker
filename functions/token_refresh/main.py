"""
Google Cloud Function for automatic OAuth token refresh.
This function should be triggered by Cloud Scheduler every hour to ensure tokens stay fresh.
"""

import os
import base64
import json
import logging
from datetime import datetime, timedelta
import httpx
from google.cloud import firestore
from google.cloud import secretmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
db = firestore.Client()
secrets_client = secretmanager.SecretManagerServiceClient()

PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'draft-maker-468923')
COLLECTION_NAME = 'api_tokens'

def get_secret(secret_name):
    """Retrieve secret from Secret Manager."""
    try:
        name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
        response = secrets_client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Failed to get secret {secret_name}: {e}")
        raise

async def refresh_ebay_token():
    """Refresh eBay access token using refresh token."""
    try:
        # Get current token from Firestore
        doc_ref = db.collection(COLLECTION_NAME).document('ebay')
        doc = doc_ref.get()
        
        if not doc.exists:
            logger.error("No eBay token document found in Firestore")
            return False
        
        token_data = doc.to_dict()
        
        # Check if token needs refresh (refresh if expires in less than 30 minutes)
        expires_at = token_data.get('expires_at')
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        # Handle Firestore timestamp objects
        if hasattr(expires_at, '_seconds'):
            expires_at = datetime.fromtimestamp(expires_at._seconds)
        
        # Use timezone-aware datetime for comparison
        from datetime import timezone
        now_utc = datetime.now(timezone.utc) if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo else datetime.utcnow()
        time_until_expiry = expires_at - now_utc
        
        if time_until_expiry > timedelta(minutes=30):
            logger.info(f"eBay token still valid for {time_until_expiry}. Skipping refresh.")
            return True
        
        # Get credentials from Secret Manager
        app_id = get_secret('EBAY_APP_ID')
        cert_id = get_secret('EBAY_CERT_ID')
        
        # Prepare refresh request
        refresh_token = token_data.get('refresh_token')
        if not refresh_token:
            logger.error("No refresh token found")
            return False
        
        # Prepare Basic Auth header
        credentials = f"{app_id}:{cert_id}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory"
        }
        
        # Make refresh request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.ebay.com/identity/v1/oauth2/token",
                headers=headers,
                data=data,
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to refresh eBay token: {response.text}")
                return False
            
            new_token_data = response.json()
        
        # Update Firestore with new token
        updated_data = {
            "access_token": new_token_data["access_token"],
            "refresh_token": refresh_token,  # Refresh token doesn't change
            "token_type": new_token_data["token_type"],
            "expires_at": datetime.utcnow() + timedelta(seconds=new_token_data["expires_in"]),
            "updated_at": datetime.utcnow()
        }
        
        doc_ref.set(updated_data, merge=True)
        logger.info("✅ eBay token refreshed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error refreshing eBay token: {e}")
        return False

async def refresh_spotify_token():
    """Refresh Spotify access token."""
    try:
        # Get credentials from Secret Manager
        client_id = get_secret('SPOTIFY_CLIENT_ID')
        client_secret = get_secret('SPOTIFY_CLIENT_SECRET')
        
        # Prepare client credentials
        client_credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(client_credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials"
        }
        
        # Make token request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.spotify.com/api/token",
                headers=headers,
                data=data,
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to refresh Spotify token: {response.text}")
                return False
            
            token_response = response.json()
        
        # Update Firestore with new token
        doc_ref = db.collection(COLLECTION_NAME).document('spotify')
        token_data = {
            "access_token": token_response["access_token"],
            "token_type": token_response["token_type"],
            "expires_at": datetime.utcnow() + timedelta(seconds=token_response["expires_in"]),
            "updated_at": datetime.utcnow()
        }
        
        doc_ref.set(token_data, merge=True)
        logger.info("✅ Spotify token refreshed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error refreshing Spotify token: {e}")
        return False

def token_refresh(request):
    """
    HTTP Cloud Function entry point.
    Can be triggered by Cloud Scheduler or manual HTTP request.
    """
    import asyncio
    
    logger.info("Starting token refresh process...")
    
    # Create event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Refresh both tokens
        ebay_result = loop.run_until_complete(refresh_ebay_token())
        spotify_result = loop.run_until_complete(refresh_spotify_token())
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "ebay_refresh": "success" if ebay_result else "failed",
            "spotify_refresh": "success" if spotify_result else "failed"
        }
        
        if ebay_result and spotify_result:
            logger.info("✅ All tokens refreshed successfully")
            return (json.dumps(results), 200)
        elif ebay_result or spotify_result:
            logger.warning("⚠️ Partial token refresh completed")
            return (json.dumps(results), 206)  # Partial Content
        else:
            logger.error("❌ Token refresh failed")
            return (json.dumps(results), 500)
            
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return (json.dumps({"error": str(e)}), 500)
    finally:
        loop.close()
