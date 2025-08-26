"""Image fetcher component for Spotify and Discogs APIs."""

import asyncio
from typing import Dict, Any, Optional, List
import httpx
from urllib.parse import quote

from src.config import settings
from src.utils.logger import get_logger
from src.utils.token_manager import get_token_manager

logger = get_logger(__name__)

# API endpoints
SPOTIFY_BASE_URL = "https://api.spotify.com/v1"


class ImageFetcher:
    """Fetches album artwork from Spotify and Discogs."""

    def __init__(self):
        """Initialize the image fetcher."""
        self.token_manager = get_token_manager()

    async def fetch_images(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch images for an album using metadata.

        Args:
            metadata: Album metadata containing UPC and other info

        Returns:
            Dictionary containing image URLs and metadata
        """
        upc = metadata.get("upc")

        logger.info(f"Fetching images for UPC: {upc}")

        images_result = {
            "upc": upc,
            "images": [],
            "primary_image": None,
            "sources": [],
        }

        # Try Spotify first (primary source for images)
        if upc:
            logger.info(f"Fetching images from Spotify for UPC: {upc}")
            spotify_images = await self._fetch_from_spotify(upc, metadata)

            if spotify_images:
                images_result["images"].extend(spotify_images)
                images_result["sources"].append("spotify")

                # Set primary image from Spotify
                if spotify_images:
                    images_result["primary_image"] = spotify_images[0]["url"]
                    logger.info(
                        f"Found {len(spotify_images)} images from Spotify for UPC: {upc}"
                    )

        # If no Spotify images, check if we have Discogs images in metadata
        if not images_result["primary_image"] and metadata.get("discogs_images"):
            logger.info(f"Using Discogs images from metadata for UPC: {upc}")
            discogs_images = self._process_discogs_images(metadata["discogs_images"])
            
            if discogs_images:
                images_result["images"].extend(discogs_images)
                images_result["sources"].append("discogs")
                
                # Set primary image from Discogs
                if discogs_images:
                    images_result["primary_image"] = discogs_images[0]["url"]
                    logger.info(
                        f"Found {len(discogs_images)} images from Discogs for UPC: {upc}"
                    )

        # Log summary
        total_images = len(images_result["images"])
        if total_images > 0:
            logger.info(
                f"Found {total_images} total images from {', '.join(images_result['sources'])}"
            )
        else:
            logger.warning(f"No images found for UPC: {upc}")

        return images_result

    def _process_discogs_images(self, discogs_images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process Discogs images from metadata into a standard format.

        Args:
            discogs_images: List of Discogs image dictionaries from metadata

        Returns:
            List of processed image dictionaries
        """
        processed_images = []
        
        for img in discogs_images:
            # Use the main URI or the 150px thumbnail
            url = img.get("uri") or img.get("uri150")
            if url:
                image_info = {
                    "url": url,
                    "width": img.get("width"),
                    "height": img.get("height"),
                    "type": img.get("type", "primary"),
                    "source": "discogs",
                    "ebay_url": url,  # Use for eBay
                }
                
                # Mark the first "primary" type image as the front
                if img.get("type") == "primary":
                    image_info["is_front"] = True
                    image_info["size_category"] = "large"
                else:
                    image_info["is_front"] = False
                    image_info["size_category"] = "medium"
                
                processed_images.append(image_info)
        
        # Sort by type (primary first)
        processed_images.sort(key=lambda x: (x.get("type") != "primary", x.get("type", "")))
        
        return processed_images

    async def _fetch_from_spotify(
        self, upc: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
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
            "Accept": "application/json",
        }

        # Try different search strategies
        search_strategies = [
            f"upc:{upc}",  # Direct UPC search
            f'tag:upc "{upc}"',  # Tag search
            upc,  # Plain UPC
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
                        "market": "US",
                    }

                    response = await client.get(
                        search_url, params=params, headers=headers, timeout=30.0
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
                                "ebay_url": img.get("url"),  # Use full URL for eBay
                            }

                            # Categorize by size
                            if img.get("height") and img.get("height") >= 600:
                                image_info["size_category"] = "large"
                                image_info["is_front"] = (
                                    True  # Assume first large image is front
                                )
                            elif img.get("height") and img.get("height") >= 300:
                                image_info["size_category"] = "medium"
                            else:
                                image_info["size_category"] = "small"

                            images.append(image_info)

                        # Sort by size (largest first)
                        images.sort(key=lambda x: x.get("height", 0), reverse=True)

                        logger.info(
                            f"Found {len(images)} images from Spotify for UPC: {upc}"
                        )
                        return images

                except httpx.TimeoutException:
                    logger.warning(f"Spotify timeout for search query: {search_query}")
                    continue
                except Exception as e:
                    logger.warning(
                        f"Spotify search failed for query '{search_query}': {e}"
                    )
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
