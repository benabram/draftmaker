"""OAuth token management for eBay and Spotify APIs."""

import base64
import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx
from src.config import settings, is_development
from src.utils.logger import get_logger

try:
    from google.cloud import firestore
    from google.cloud.firestore_v1 import FieldFilter
    FIRESTORE_AVAILABLE = True
except Exception:
    FIRESTORE_AVAILABLE = False

logger = get_logger(__name__)


class TokenManager:
    """Manages OAuth tokens for various APIs."""
    
    def __init__(self):
        """Initialize the token manager."""
        self._token_cache = {}  # In-memory cache for tokens
        
        # Use local storage in development, Firestore in production
        if is_development():
            from src.utils.local_token_storage import LocalTokenStorage
            self.storage = LocalTokenStorage()
            self.use_local_storage = True
        else:
            if FIRESTORE_AVAILABLE:
                self.db = firestore.Client(project=settings.gcp_project_id)
                self.collection = settings.firestore_collection_tokens
                self.use_local_storage = False
            else:
                raise Exception("Firestore is not available in production environment")
        
    async def get_spotify_token(self) -> str:
        """
        Get a valid Spotify access token.
        
        Returns:
            Valid Spotify access token
            
        Raises:
            Exception: If unable to obtain a valid token
        """
        # Check cache first
        if self._is_token_valid_in_cache("spotify"):
            return self._token_cache["spotify"]["access_token"]
            
        # Check Firestore
        token_data = await self._get_token_from_firestore("spotify")
        if token_data and self._is_token_still_valid(token_data):
            self._token_cache["spotify"] = token_data
            return token_data["access_token"]
            
        # Need to get a new token
        logger.info("Fetching new Spotify access token")
        new_token = await self._fetch_spotify_token()
        await self._save_token_to_firestore("spotify", new_token)
        self._token_cache["spotify"] = new_token
        return new_token["access_token"]
        
    async def get_ebay_token(self) -> str:
        """
        Get a valid eBay access token.
        
        Returns:
            Valid eBay access token
            
        Raises:
            Exception: If unable to obtain a valid token
        """
        # Check cache first
        if self._is_token_valid_in_cache("ebay"):
            return self._token_cache["ebay"]["access_token"]
            
        # Check Firestore
        token_data = await self._get_token_from_firestore("ebay")
        if token_data and self._is_token_still_valid(token_data):
            self._token_cache["ebay"] = token_data
            return token_data["access_token"]
            
        # Need to refresh the token
        if not token_data or "refresh_token" not in token_data:
            raise Exception(
                "No eBay refresh token found. Please provide an initial access token "
                "to establish the refresh token flow."
            )
            
        logger.info("Refreshing eBay access token")
        new_token = await self._refresh_ebay_token(token_data["refresh_token"])
        await self._save_token_to_firestore("ebay", new_token)
        self._token_cache["ebay"] = new_token
        return new_token["access_token"]
        
    async def set_initial_ebay_token(self, access_token: str, refresh_token: str, expires_in: int):
        """
        Set the initial eBay tokens (called when user provides first token).
        
        Args:
            access_token: The initial access token
            refresh_token: The refresh token for future use
            expires_in: Token expiry time in seconds
        """
        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
            "token_type": "Bearer",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await self._save_token_to_firestore("ebay", token_data)
        self._token_cache["ebay"] = token_data
        logger.info("Initial eBay tokens saved successfully")
        
    async def _fetch_spotify_token(self) -> Dict[str, Any]:
        """
        Fetch a new Spotify access token using client credentials flow.
        
        Returns:
            Token data dictionary
        """
        url = "https://accounts.spotify.com/api/token"
        
        # Prepare client credentials
        client_credentials = f"{settings.spotify_client_id}:{settings.spotify_client_secret}"
        encoded_credentials = base64.b64encode(client_credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            response.raise_for_status()
            
        token_response = response.json()
        
        # Format token data for storage
        return {
            "access_token": token_response["access_token"],
            "token_type": token_response["token_type"],
            "expires_at": datetime.utcnow() + timedelta(seconds=token_response["expires_in"]),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
    async def _refresh_ebay_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh eBay access token using refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            Token data dictionary
        """
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        
        # Prepare client credentials
        client_credentials = f"{settings.ebay_app_id}:{settings.ebay_cert_id}"
        encoded_credentials = base64.b64encode(client_credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            
            if response.status_code != 200:
                logger.error(f"eBay token refresh failed: {response.text}")
                raise Exception(f"Failed to refresh eBay token: {response.status_code}")
                
        token_response = response.json()
        
        # Format token data for storage
        return {
            "access_token": token_response["access_token"],
            "refresh_token": refresh_token,  # Refresh token doesn't change
            "token_type": token_response["token_type"],
            "expires_at": datetime.utcnow() + timedelta(seconds=token_response["expires_in"]),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
    async def _get_token_from_firestore(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve token from storage.
        
        Args:
            api_name: The API name (spotify or ebay)
            
        Returns:
            Token data or None if not found
        """
        if self.use_local_storage:
            return self.storage.load_token(api_name)
        else:
            try:
                doc_ref = self.db.collection(self.collection).document(api_name)
                doc = doc_ref.get()
                
                if doc.exists:
                    return doc.to_dict()
                return None
            except Exception as e:
                logger.error(f"Error retrieving {api_name} token from Firestore: {e}")
                return None
            
    async def _save_token_to_firestore(self, api_name: str, token_data: Dict[str, Any]):
        """
        Save token to storage.
        
        Args:
            api_name: The API name (spotify or ebay)
            token_data: Token data to save
        """
        if self.use_local_storage:
            self.storage.save_token(api_name, token_data)
        else:
            try:
                doc_ref = self.db.collection(self.collection).document(api_name)
                doc_ref.set(token_data, merge=True)
                logger.info(f"Saved {api_name} token to Firestore")
            except Exception as e:
                logger.error(f"Error saving {api_name} token to Firestore: {e}")
                raise
            
    def _is_token_valid_in_cache(self, api_name: str) -> bool:
        """
        Check if cached token is still valid.
        
        Args:
            api_name: The API name
            
        Returns:
            True if token exists in cache and is valid
        """
        if api_name not in self._token_cache:
            return False
            
        token_data = self._token_cache[api_name]
        return self._is_token_still_valid(token_data)
        
    def _is_token_still_valid(self, token_data: Dict[str, Any]) -> bool:
        """
        Check if token is still valid based on expiry time.
        
        Args:
            token_data: Token data dictionary
            
        Returns:
            True if token is still valid
        """
        if "expires_at" not in token_data:
            return False
            
        # Check if token expires in more than 5 minutes (buffer for safety)
        expires_at = token_data["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        # Handle both offset-naive and offset-aware datetimes
        # If expires_at has timezone info, use timezone-aware comparison
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo is not None:
            from datetime import timezone
            buffer_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        else:
            buffer_time = datetime.utcnow() + timedelta(minutes=5)
            
        return expires_at > buffer_time


# Global token manager instance
_token_manager = None


def get_token_manager() -> TokenManager:
    """
    Get the global token manager instance.
    
    Returns:
        TokenManager instance
    """
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
