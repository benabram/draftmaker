"""Metadata fetcher component for Discogs API."""

import asyncio
from typing import Dict, Any
from datetime import datetime
import httpx

from src.config import settings
from src.utils.logger import get_logger
from src.utils.cache_manager import get_cache_manager
from src.utils.token_manager import get_token_manager
from src.utils.error_sanitizer import sanitize_error_message

logger = get_logger(__name__)

# API endpoints
DISCOGS_BASE_URL = "https://api.discogs.com"


class MetadataFetcher:
    """Fetches metadata from Discogs API."""

    def __init__(self):
        """Initialize the metadata fetcher."""
        self.cache_manager = get_cache_manager()
        self.token_manager = get_token_manager()

    async def fetch_metadata(self, upc: str) -> Dict[str, Any]:
        """
        Fetch metadata for a UPC from Discogs.

        Args:
            upc: The UPC barcode

        Returns:
            Metadata from Discogs
        """
        logger.info(f"Fetching metadata for UPC: {upc}")

        # Check cache first
        cached_metadata = await self.cache_manager.get_metadata(upc)
        if cached_metadata:
            logger.info(f"Using cached metadata for UPC: {upc}")
            return cached_metadata

        # Fetch from Discogs
        metadata = await self._fetch_from_discogs(upc)

        # Add UPC and metadata completeness check
        if metadata:
            metadata["upc"] = upc
            metadata["is_complete"] = all([
                metadata.get("title"),
                metadata.get("artist_name"),
                metadata.get("upc")
            ])
            metadata["fetched_at"] = datetime.utcnow().isoformat()
            metadata["metadata_sources"] = ["discogs"] if metadata.get("discogs_id") else []

            # Cache the metadata if it's complete
            if metadata.get("is_complete"):
                await self.cache_manager.set_metadata(upc, metadata)
                logger.debug(f"Cached metadata for UPC {upc}")
            else:
                logger.debug(f"Not caching incomplete metadata for UPC {upc}")
        else:
            # Return empty metadata structure if nothing found
            metadata = {
                "upc": upc,
                "is_complete": False,
                "fetched_at": datetime.utcnow().isoformat(),
                "metadata_sources": [],
                "error": "No metadata found"
            }

        return metadata


    async def _fetch_from_discogs(
        self, upc: str, retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Fetch metadata from Discogs API.

        Args:
            upc: The UPC barcode
            retry_count: Current retry attempt

        Returns:
            Discogs metadata
        """
        # Check if personal access token is available
        if not settings.discogs_personal_access_token:
            logger.warning(
                f"Discogs Personal Access Token not configured, skipping Discogs search for UPC: {upc}"
            )
            return {}

        # Search for release by barcode
        search_url = f"{DISCOGS_BASE_URL}/database/search"
        params = {"type": "release", "barcode": upc}

        # Prepare Discogs authentication using Personal Access Token
        headers = {
            "User-Agent": "draftmaker/1.0 (benjaminabramowitz@gmail.com)",
            "Authorization": f"Discogs token={settings.discogs_personal_access_token}",
        }

        try:
            async with httpx.AsyncClient() as client:
                # Search for the release
                response = await client.get(
                    search_url, params=params, headers=headers, timeout=30.0
                )

                if response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Discogs rate limited, waiting {retry_after} seconds"
                    )
                    await asyncio.sleep(retry_after)
                    return await self._fetch_from_discogs(upc)  # Retry

                response.raise_for_status()
                search_data = response.json()

                if not search_data.get("results"):
                    logger.warning(f"No Discogs release found for UPC: {upc}")
                    return {}

                # Get the first result's ID
                release_id = search_data["results"][0]["id"]

                # Fetch detailed release information
                release_url = f"{DISCOGS_BASE_URL}/releases/{release_id}"

                await asyncio.sleep(1)  # Rate limiting

                response = await client.get(
                    release_url,
                    headers=headers,  # Headers already contain the Authorization token
                    timeout=30.0,
                )

                response.raise_for_status()
                release_data = response.json()

                return self._parse_discogs_response(release_data)

        except httpx.TimeoutException:
            logger.error(f"Discogs API timeout for UPC: {upc}")
            return {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Try to reload secrets in case token was updated
                if retry_count == 0 and settings.environment.lower() == "production":
                    logger.info(
                        "Discogs 401 error, attempting to reload token from Secret Manager"
                    )
                    try:
                        from src.utils.secrets_loader import get_secrets_loader

                        loader = get_secrets_loader()
                        new_token = loader.get_secret("DISCOGS_PERSONAL_ACCESS_TOKEN")
                        if (
                            new_token
                            and new_token != settings.discogs_personal_access_token
                        ):
                            settings.discogs_personal_access_token = new_token
                            logger.info("Reloaded Discogs token, retrying request")
                            return await self._fetch_from_discogs(upc, retry_count=1)
                    except Exception as reload_error:
                        logger.warning(
                            f"Failed to reload Discogs token: {reload_error}"
                        )

                logger.error(
                    f"Discogs API authentication failed for UPC {upc}: 401 Unauthorized"
                )
            elif e.response.status_code == 500 and retry_count < 2:
                # Retry on 500 errors with exponential backoff
                wait_time = (2**retry_count) * 2
                logger.warning(
                    f"Discogs API 500 error, retrying in {wait_time}s "
                    f"(attempt {retry_count + 1}/2)"
                )
                await asyncio.sleep(wait_time)
                return await self._fetch_from_discogs(upc, retry_count + 1)
            else:
                logger.error(
                    f"Discogs API HTTP error for UPC {upc}: {e.response.status_code}"
                )
            return {}
        except Exception as e:
            # Sanitize error message to remove credentials
            sanitized_error = sanitize_error_message(str(e))
            logger.error(
                f"Error fetching from Discogs for UPC {upc}: {sanitized_error}"
            )
            return {}

    def _parse_discogs_response(self, release: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Discogs release data.

        Args:
            release: Raw release data from Discogs

        Returns:
            Parsed metadata
        """
        metadata = {
            "discogs_id": release.get("id"),
            "title": release.get("title"),
            "year": release.get("year"),
            "country": release.get("country"),
            "genres": release.get("genres", []),
            "styles": release.get("styles", []),
            "source": "discogs",
        }

        # Parse artist information
        if "artists" in release and release["artists"]:
            artists = []
            for artist in release["artists"]:
                artists.append({"name": artist.get("name"), "id": artist.get("id")})
            metadata["artists"] = artists
            metadata["artist_name"] = artists[0]["name"] if artists else None

        # Parse extraartists (producers, engineers, etc.)
        if "extraartists" in release and release["extraartists"]:
            producers = []
            for extra in release["extraartists"]:
                role = extra.get("role", "").lower()
                # Check for producer roles
                if "producer" in role or "produced by" in role:
                    producers.append(extra.get("name"))

            if producers:
                # Join multiple producers with comma
                metadata["producer"] = ", ".join(producers)
                logger.debug(f"Found producer(s) from Discogs: {metadata['producer']}")

        # Parse label information
        if "labels" in release and release["labels"]:
            labels = []
            for label in release["labels"]:
                labels.append(
                    {"name": label.get("name"), "catalog_number": label.get("catno")}
                )
            metadata["labels"] = labels
            if labels:
                metadata["label_name"] = labels[0]["name"]
                metadata["catalog_number"] = labels[0]["catalog_number"]

        # Parse format information
        if "formats" in release and release["formats"]:
            formats = release["formats"][0]
            metadata["format"] = formats.get("name")
            metadata["format_descriptions"] = formats.get("descriptions", [])

        # Parse tracklist
        if "tracklist" in release:
            tracks = []
            for track in release["tracklist"]:
                if track.get("type_") == "track":  # Skip headings
                    tracks.append(
                        {
                            "position": track.get("position"),
                            "title": track.get("title"),
                            "duration": track.get("duration"),
                        }
                    )
            metadata["tracks"] = tracks
            metadata["track_count"] = len(tracks)

        # Images (we'll handle these in the image_fetcher)
        if "images" in release and release["images"]:
            metadata["discogs_images"] = [
                {
                    "type": img.get("type"),
                    "uri": img.get("uri"),
                    "uri150": img.get("uri150"),
                    "width": img.get("width"),
                    "height": img.get("height"),
                }
                for img in release["images"]
            ]

        # Additional metadata
        metadata["notes"] = release.get("notes")
        metadata["data_quality"] = release.get("data_quality")

        return metadata



# Global metadata fetcher instance
_metadata_fetcher = None


def get_metadata_fetcher() -> MetadataFetcher:
    """Get the global metadata fetcher instance."""
    global _metadata_fetcher
    if _metadata_fetcher is None:
        _metadata_fetcher = MetadataFetcher()
    return _metadata_fetcher
