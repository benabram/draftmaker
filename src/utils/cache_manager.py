"""Cache management for MusicBrainz IDs and other frequently accessed data."""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from src.config import settings, is_development
from src.utils.logger import get_logger

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except Exception:
    FIRESTORE_AVAILABLE = False

logger = get_logger(__name__)


class CacheManager:
    """Manages caching of MBIDs and other metadata."""
    
    def __init__(self):
        """Initialize cache manager."""
        self._memory_cache = {}  # In-memory cache
        
        # Use local storage in development, Firestore in production
        if is_development():
            self.cache_dir = Path(__file__).parent.parent.parent / ".cache"
            self.cache_dir.mkdir(exist_ok=True)
            self.use_local_storage = True
            
            # Add to .gitignore
            gitignore_path = Path(__file__).parent.parent.parent / ".gitignore"
            if gitignore_path.exists():
                with open(gitignore_path, 'r') as f:
                    content = f.read()
                if '.cache/' not in content:
                    with open(gitignore_path, 'a') as f:
                        f.write('\n# Cache storage (local development)\n.cache/\n')
        else:
            if FIRESTORE_AVAILABLE:
                self.db = firestore.Client(project=settings.gcp_project_id)
                self.collection = settings.firestore_collection_mbid
                self.use_local_storage = False
            else:
                raise Exception("Firestore is not available in production environment")
    
    async def get_mbid(self, upc: str) -> Optional[str]:
        """
        Get cached MBID for a UPC.
        
        Args:
            upc: The UPC code
            
        Returns:
            MBID if found in cache, None otherwise
        """
        # Check memory cache first
        if upc in self._memory_cache:
            cached_data = self._memory_cache[upc]
            if self._is_cache_valid(cached_data):
                logger.debug(f"MBID found in memory cache for UPC {upc}")
                return cached_data.get("mbid")
        
        # Check persistent storage
        if self.use_local_storage:
            cached_data = self._load_from_local(upc)
        else:
            cached_data = await self._load_from_firestore(upc)
        
        if cached_data and self._is_cache_valid(cached_data):
            self._memory_cache[upc] = cached_data
            logger.debug(f"MBID found in persistent cache for UPC {upc}")
            return cached_data.get("mbid")
        
        return None
    
    async def set_mbid(self, upc: str, mbid: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Cache MBID for a UPC.
        
        Args:
            upc: The UPC code
            mbid: The MusicBrainz ID
            metadata: Optional additional metadata to cache
        """
        cache_data = {
            "mbid": mbid,
            "upc": upc,
            "cached_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=30),  # Cache for 30 days
        }
        
        if metadata:
            cache_data["metadata"] = metadata
        
        # Save to memory cache
        self._memory_cache[upc] = cache_data
        
        # Save to persistent storage
        if self.use_local_storage:
            self._save_to_local(upc, cache_data)
        else:
            await self._save_to_firestore(upc, cache_data)
        
        logger.info(f"Cached MBID {mbid} for UPC {upc}")
    
    async def get_metadata(self, upc: str) -> Optional[Dict[str, Any]]:
        """
        Get cached metadata for a UPC.
        
        Args:
            upc: The UPC code
            
        Returns:
            Metadata if found in cache, None otherwise
        """
        # Check memory cache first
        if upc in self._memory_cache:
            cached_data = self._memory_cache[upc]
            if self._is_cache_valid(cached_data):
                return cached_data.get("metadata")
        
        # Check persistent storage
        if self.use_local_storage:
            cached_data = self._load_from_local(upc)
        else:
            cached_data = await self._load_from_firestore(upc)
        
        if cached_data and self._is_cache_valid(cached_data):
            self._memory_cache[upc] = cached_data
            return cached_data.get("metadata")
        
        return None
    
    def _is_cache_valid(self, cache_data: Dict[str, Any]) -> bool:
        """
        Check if cached data is still valid.
        
        Args:
            cache_data: The cached data
            
        Returns:
            True if cache is still valid
        """
        if "expires_at" not in cache_data:
            return False
        
        expires_at = cache_data["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        return datetime.utcnow() < expires_at
    
    def _save_to_local(self, upc: str, data: Dict[str, Any]):
        """Save data to local cache file."""
        file_path = self.cache_dir / f"{upc}.json"
        
        # Convert datetime objects to ISO format
        serializable_data = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                serializable_data[key] = value.isoformat()
            else:
                serializable_data[key] = value
        
        try:
            with open(file_path, 'w') as f:
                json.dump(serializable_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache for UPC {upc}: {e}")
    
    def _load_from_local(self, upc: str) -> Optional[Dict[str, Any]]:
        """Load data from local cache file."""
        file_path = self.cache_dir / f"{upc}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Convert ISO format strings back to datetime
            for key in ['cached_at', 'expires_at']:
                if key in data and isinstance(data[key], str):
                    data[key] = datetime.fromisoformat(data[key])
            
            return data
        except Exception as e:
            logger.error(f"Error loading cache for UPC {upc}: {e}")
            return None
    
    async def _save_to_firestore(self, upc: str, data: Dict[str, Any]):
        """Save data to Firestore."""
        try:
            doc_ref = self.db.collection(self.collection).document(upc)
            doc_ref.set(data, merge=True)
        except Exception as e:
            logger.error(f"Error saving cache to Firestore for UPC {upc}: {e}")
    
    async def _load_from_firestore(self, upc: str) -> Optional[Dict[str, Any]]:
        """Load data from Firestore."""
        try:
            doc_ref = self.db.collection(self.collection).document(upc)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error loading cache from Firestore for UPC {upc}: {e}")
            return None


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
