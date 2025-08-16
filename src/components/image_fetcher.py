"""Image fetcher component for Cover Art Archive and Spotify APIs."""

import asyncio
from typing import Dict, Any, Optional, List
import httpx
from urllib.parse import quote

from src.config import settings
from src.utils.logger import get_logger
from src.utils.token_manager import get_token_manager

logger = get_logger(__name__)

# API endpoints
COVER_ART_ARCHIVE_BASE_URL = "https://coverartarchive.org"
SPOTIFY_BASE_URL = "https://api.spotify.com/v1"


class ImageFetcher:
    """Fetches album artwork from Cover Art Archive and Spotify."""
    
    def __init__(self):
        """Initialize the image fetcher."""
        self.token_manager = get_token_manager()
        
    async def fetch_images(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch images for an album using metadata.
        
        Args:
            metadata: Album metadata containing MBID and/or UPC
            
        Returns:
            Dictionary containing image URLs and metadata
        """
        upc = metadata.get("upc")
        mbid = metadata.get("mbid")
        
        logger.info(f"Fetching images for UPC: {upc}, MBID: {mbid}")
        
        images_result = {
            "upc": upc,
            "mbid": mbid,
            "images": [],
            "primary_image": None,
            "sources": []
        }
        
        # If we have MBID, try Cover Art Archive first
        if mbid:
            logger.info(f"Attempting to fetch images from Cover Art Archive for MBID: {mbid}")
            cover_art_images = await self._fetch_from_cover_art_archive(mbid)
            
            if cover_art_images:
                images_result["images"].extend(cover_art_images)
                images_result["sources"].append("cover_art_archive")
                
                # Set primary image from Cover Art Archive if available
                for img in cover_art_images:
                    if img.get("is_front"):
                        images_result["primary_image"] = img["url"]
                        break
                
                # If we found good images from Cover Art Archive, we can return
                if images_result["primary_image"]:
                    logger.info(f"Found primary image from Cover Art Archive for MBID: {mbid}")
                    return images_result
        else:
            logger.info(f"No MBID available for UPC: {upc}, skipping Cover Art Archive")
        
        # If no MBID or no images from Cover Art Archive, try Spotify
        if upc:
            logger.info(f"Fetching images from Spotify for UPC: {upc}")
            spotify_images = await self._fetch_from_spotify(upc, metadata)
            
            if spotify_images:
                images_result["images"].extend(spotify_images)
                images_result["sources"].append("spotify")
                
                # Set primary image from Spotify if not already set
                if not images_result["primary_image"] and spotify_images:
                    images_result["primary_image"] = spotify_images[0]["url"]
        
        # Log summary
        total_images = len(images_result["images"])
        logger.info(f"Found {total_images} total images from {', '.join(images_result['sources'])}")
        
        return images_result
    
    async def _fetch_from_cover_art_archive(self, mbid: str) -> List[Dict[str, Any]]:
        """
        Fetch images from Cover Art Archive.
        
        Args:
            mbid: MusicBrainz Release ID
            
        Returns:
            List of image dictionaries
        """
        url = f"{COVER_ART_ARCHIVE_BASE_URL}/release/{mbid}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": settings.musicbrainz_user_agent},
                    timeout=30.0,
                    follow_redirects=True
                )
                
                if response.status_code == 404:
                    logger.warning(f"No cover art found for MBID: {mbid}")
                    return []
                
                if response.status_code == 503:
                    logger.warning(f"Cover Art Archive unavailable for MBID: {mbid}")
                    return []
                
                response.raise_for_status()
                data = response.json()
                
                # Parse the response
                images = []
                for img in data.get("images", []):
                    image_info = {
                        "url": img.get("image"),  # Full size image
                        "thumbnail_500": img.get("thumbnails", {}).get("500"),
                        "thumbnail_250": img.get("thumbnails", {}).get("250"),
                        "thumbnail_large": img.get("thumbnails", {}).get("large"),
                        "thumbnail_small": img.get("thumbnails", {}).get("small"),
                        "is_front": img.get("front", False),
                        "is_back": img.get("back", False),
                        "comment": img.get("comment", ""),
                        "types": img.get("types", []),
                        "approved": img.get("approved", False),
                        "source": "cover_art_archive"
                    }
                    
                    # Prefer 500px thumbnail for eBay listings
                    if image_info["thumbnail_500"]:
                        image_info["ebay_url"] = image_info["thumbnail_500"]
                    elif image_info["thumbnail_large"]:
                        image_info["ebay_url"] = image_info["thumbnail_large"]
                    else:
                        image_info["ebay_url"] = image_info["url"]
                    
                    images.append(image_info)
                
                # Sort images: front first, approved first
                images.sort(key=lambda x: (
                    not x.get("is_front", False),
                    not x.get("approved", False)
                ))
                
                return images
                
        except httpx.TimeoutException:
            logger.error(f"Cover Art Archive timeout for MBID: {mbid}")
            return []
        except Exception as e:
            logger.error(f"Error fetching from Cover Art Archive for MBID {mbid}: {e}")
            return []
    
    async def _fetch_from_spotify(self, upc: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch images from Spotify.
        
        Args:
            upc: The UPC barcode
            metadata: Album metadata for additional search context
            
        Returns:
            List of image dictionaries
        """
        # Get Spotify access token
        try:
            access_token = await self.token_manager.get_spotify_token()
        except Exception as e:
            logger.error(f"Failed to get Spotify token: {e}")
            return []
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        # Try different search strategies
        search_strategies = [
            f"upc:{upc}",  # Direct UPC search
            f'tag:upc "{upc}"',  # Tag search
            upc  # Plain UPC
        ]
        
        # Add artist/album search as fallback if metadata available
        if metadata.get("artist_name") and metadata.get("title"):
            artist = metadata["artist_name"]
            album = metadata["title"]
            search_strategies.append(f'artist:"{artist}" album:"{album}"')
        
        async with httpx.AsyncClient() as client:
            for search_query in search_strategies:
                try:
                    # Search for the album
                    search_url = f"{SPOTIFY_BASE_URL}/search"
                    params = {
                        "q": search_query,
                        "type": "album",
                        "limit": 5,
                        "market": "US"
                    }
                    
                    response = await client.get(
                        search_url,
                        params=params,
                        headers=headers,
                        timeout=30.0
                    )
                    
                    if response.status_code == 401:
                        # Token expired, try to refresh
                        logger.warning("Spotify token expired, refreshing...")
                        access_token = await self.token_manager.get_spotify_token()
                        headers["Authorization"] = f"Bearer {access_token}"
                        continue
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    albums = data.get("albums", {}).get("items", [])
                    
                    if albums:
                        # Use the first matching album
                        album = albums[0]
                        images = []
                        
                        for img in album.get("images", []):
                            image_info = {
                                "url": img.get("url"),
                                "height": img.get("height"),
                                "width": img.get("width"),
                                "source": "spotify",
                                "album_name": album.get("name"),
                                "album_id": album.get("id"),
                                "ebay_url": img.get("url")  # Use full URL for eBay
                            }
                            
                            # Categorize by size
                            if img.get("height") and img.get("height") >= 600:
                                image_info["size_category"] = "large"
                                image_info["is_front"] = True  # Assume first large image is front
                            elif img.get("height") and img.get("height") >= 300:
                                image_info["size_category"] = "medium"
                            else:
                                image_info["size_category"] = "small"
                            
                            images.append(image_info)
                        
                        # Sort by size (largest first)
                        images.sort(key=lambda x: x.get("height", 0), reverse=True)
                        
                        logger.info(f"Found {len(images)} images from Spotify for UPC: {upc}")
                        return images
                        
                except httpx.TimeoutException:
                    logger.warning(f"Spotify timeout for search query: {search_query}")
                    continue
                except Exception as e:
                    logger.warning(f"Spotify search failed for query '{search_query}': {e}")
                    continue
        
        logger.warning(f"No images found on Spotify for UPC: {upc}")
        return []


# Global image fetcher instance
_image_fetcher = None


def get_image_fetcher() -> ImageFetcher:
    """Get the global image fetcher instance."""
    global _image_fetcher
    if _image_fetcher is None:
        _image_fetcher = ImageFetcher()
    return _image_fetcher
