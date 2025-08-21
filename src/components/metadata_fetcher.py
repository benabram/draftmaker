"""Metadata fetcher component for MusicBrainz and Discogs APIs."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
from urllib.parse import quote

from src.config import settings
from src.utils.logger import get_logger
from src.utils.cache_manager import get_cache_manager
from src.utils.token_manager import get_token_manager
from src.utils.error_sanitizer import sanitize_error_message

logger = get_logger(__name__)

# API endpoints
MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2"
DISCOGS_BASE_URL = "https://api.discogs.com"


class MetadataFetcher:
    """Fetches metadata from MusicBrainz and Discogs APIs."""
    
    def __init__(self):
        """Initialize the metadata fetcher."""
        self.cache_manager = get_cache_manager()
        self.token_manager = get_token_manager()
        self.musicbrainz_headers = {
            "User-Agent": settings.musicbrainz_user_agent,
            "Accept": "application/json"
        }
        
    async def fetch_metadata(self, upc: str) -> Dict[str, Any]:
        """
        Fetch metadata for a UPC from MusicBrainz and Discogs.
        
        Args:
            upc: The UPC barcode
            
        Returns:
            Combined metadata from both sources
        """
        logger.info(f"Fetching metadata for UPC: {upc}")
        
        # Check cache first
        cached_metadata = await self.cache_manager.get_metadata(upc)
        if cached_metadata:
            logger.info(f"Using cached metadata for UPC: {upc}")
            return cached_metadata
        
        # Fetch from MusicBrainz first (primary source)
        musicbrainz_data = await self._fetch_from_musicbrainz(upc)
        
        # Fetch from Discogs to supplement
        discogs_data = await self._fetch_from_discogs(upc)
        
        # Combine metadata
        metadata = self._combine_metadata(musicbrainz_data, discogs_data, upc)
        
        # Cache the MBID if found
        if metadata.get("mbid"):
            await self.cache_manager.set_mbid(upc, metadata["mbid"], metadata)
        
        return metadata
    
    async def _fetch_from_musicbrainz(self, upc: str) -> Dict[str, Any]:
        """
        Fetch metadata from MusicBrainz API.
        
        Args:
            upc: The UPC barcode
            
        Returns:
            MusicBrainz metadata
        """
        # Check if we have cached MBID
        mbid = await self.cache_manager.get_mbid(upc)
        
        if mbid:
            # Fetch full release data using MBID
            url = f"{MUSICBRAINZ_BASE_URL}/release/{mbid}"
            params = {
                "fmt": "json",
                "inc": "artists+labels+recordings+release-groups+media+discids"
            }
        else:
            # Search by barcode
            url = f"{MUSICBRAINZ_BASE_URL}/release"
            params = {
                "query": f"barcode:{upc}",
                "fmt": "json",
                "inc": "artists+labels+recordings+release-groups+media+discids"
            }
        
        try:
            async with httpx.AsyncClient() as client:
                # MusicBrainz rate limit: 1 request per second
                await asyncio.sleep(1.1)  # Add buffer to avoid rate limiting
                
                response = await client.get(
                    url,
                    params=params,
                    headers=self.musicbrainz_headers,
                    timeout=30.0
                )
                
                if response.status_code == 404:
                    logger.warning(f"No MusicBrainz release found for UPC: {upc}")
                    return {}
                
                if response.status_code == 503:
                    # Rate limited, wait and retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"MusicBrainz rate limited, waiting {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    return await self._fetch_from_musicbrainz(upc)  # Retry
                
                response.raise_for_status()
                data = response.json()
                
                # Extract the first release if searching
                if "releases" in data:
                    # Check if we have any releases
                    if not data["releases"]:
                        # No releases found - return empty dict to indicate no data
                        logger.info(f"No MusicBrainz releases found for UPC: {upc}")
                        return {}
                    
                    release = data["releases"][0]
                    
                    # Search results don't include full track data, need to fetch full release
                    release_mbid = release.get("id")
                    if release_mbid:
                        logger.debug(f"Fetching full release details for MBID: {release_mbid}")
                        await asyncio.sleep(1.1)  # Rate limit
                        
                        # Fetch full release with all details including tracks
                        full_url = f"{MUSICBRAINZ_BASE_URL}/release/{release_mbid}"
                        full_params = {
                            "fmt": "json",
                            "inc": "artists+labels+recordings+release-groups+media+discids"
                        }
                        
                        full_response = await client.get(
                            full_url,
                            params=full_params,
                            headers=self.musicbrainz_headers,
                            timeout=30.0
                        )
                        
                        if full_response.status_code == 200:
                            release = full_response.json()
                            logger.info(f"Fetched full release with tracks for UPC: {upc}")
                        else:
                            logger.warning(f"Could not fetch full release details, using search result")
                elif mbid:
                    # This was a direct MBID lookup, not a search
                    release = data
                else:
                    # Unexpected response format
                    logger.warning(f"Unexpected MusicBrainz response format for UPC: {upc}")
                    return {}
                
                return self._parse_musicbrainz_response(release)
                
        except httpx.TimeoutException:
            logger.error(f"MusicBrainz API timeout for UPC: {upc}")
            return {}
        except Exception as e:
            logger.error(f"Error fetching from MusicBrainz for UPC {upc}: {e}")
            return {}
    
    def _parse_musicbrainz_response(self, release: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse MusicBrainz release data.
        
        Args:
            release: Raw release data from MusicBrainz
            
        Returns:
            Parsed metadata
        """
        metadata = {
            "mbid": release.get("id"),
            "title": release.get("title"),
            "barcode": release.get("barcode"),
            "date": release.get("date"),
            "country": release.get("country"),
            "status": release.get("status"),
            "source": "musicbrainz"
        }
        
        # Parse artist information
        if "artist-credit" in release and release["artist-credit"]:
            artists = []
            for credit in release["artist-credit"]:
                if "artist" in credit:
                    artists.append({
                        "name": credit["artist"].get("name"),
                        "id": credit["artist"].get("id"),
                        "sort_name": credit["artist"].get("sort-name")
                    })
            metadata["artists"] = artists
            metadata["artist_name"] = artists[0]["name"] if artists else None
        
        # Parse label information
        if "label-info" in release and release["label-info"]:
            labels = []
            for info in release["label-info"]:
                if "label" in info and info["label"]:
                    labels.append({
                        "name": info["label"].get("name"),
                        "catalog_number": info.get("catalog-number")
                    })
            metadata["labels"] = labels
            if labels:
                metadata["label_name"] = labels[0]["name"]
                metadata["catalog_number"] = labels[0]["catalog_number"]
        
        # Parse release group information
        if "release-group" in release:
            rg = release["release-group"]
            metadata["release_group"] = {
                "id": rg.get("id"),
                "title": rg.get("title"),
                "type": rg.get("primary-type"),
                "secondary_types": rg.get("secondary-types", [])
            }
            metadata["release_type"] = rg.get("primary-type")
        
        # Parse media/track information
        if "media" in release and release["media"]:
            total_tracks = 0
            tracks = []
            for medium in release["media"]:
                medium_tracks = medium.get("tracks", [])
                total_tracks += len(medium_tracks)
                
                for track in medium_tracks:
                    tracks.append({
                        "position": track.get("position"),
                        "number": track.get("number"),
                        "title": track.get("title"),
                        "length": track.get("length")
                    })
            
            metadata["track_count"] = total_tracks
            metadata["tracks"] = tracks
            metadata["format"] = release["media"][0].get("format") if release["media"] else None
        
        return metadata
    
    async def _fetch_from_discogs(self, upc: str) -> Dict[str, Any]:
        """
        Fetch metadata from Discogs API.
        
        Args:
            upc: The UPC barcode
            
        Returns:
            Discogs metadata
        """
        # Check if personal access token is available
        if not settings.discogs_personal_access_token:
            logger.warning(f"Discogs Personal Access Token not configured, skipping Discogs search for UPC: {upc}")
            return {}
        
        # Search for release by barcode
        search_url = f"{DISCOGS_BASE_URL}/database/search"
        params = {
            "type": "release",
            "barcode": upc
        }
        
        # Prepare Discogs authentication using Personal Access Token
        headers = {
            "User-Agent": settings.musicbrainz_user_agent,
            "Authorization": f"Discogs token={settings.discogs_personal_access_token}"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                # Search for the release
                response = await client.get(
                    search_url,
                    params=params,
                    headers=headers,
                    timeout=30.0
                )
                
                if response.status_code == 429:
                    # Rate limited
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Discogs rate limited, waiting {retry_after} seconds")
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
                    timeout=30.0
                )
                
                response.raise_for_status()
                release_data = response.json()
                
                return self._parse_discogs_response(release_data)
                
        except httpx.TimeoutException:
            logger.error(f"Discogs API timeout for UPC: {upc}")
            return {}
        except Exception as e:
            # Sanitize error message to remove credentials
            sanitized_error = sanitize_error_message(e)
            logger.error(f"Error fetching from Discogs for UPC {upc}: {sanitized_error}")
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
            "source": "discogs"
        }
        
        # Parse artist information
        if "artists" in release and release["artists"]:
            artists = []
            for artist in release["artists"]:
                artists.append({
                    "name": artist.get("name"),
                    "id": artist.get("id")
                })
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
                labels.append({
                    "name": label.get("name"),
                    "catalog_number": label.get("catno")
                })
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
                    tracks.append({
                        "position": track.get("position"),
                        "title": track.get("title"),
                        "duration": track.get("duration")
                    })
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
                    "height": img.get("height")
                }
                for img in release["images"]
            ]
        
        # Additional metadata
        metadata["notes"] = release.get("notes")
        metadata["data_quality"] = release.get("data_quality")
        
        return metadata
    
    def _combine_metadata(self, musicbrainz_data: Dict[str, Any], 
                         discogs_data: Dict[str, Any],
                         upc: str) -> Dict[str, Any]:
        """
        Combine metadata from MusicBrainz and Discogs.
        
        Args:
            musicbrainz_data: Data from MusicBrainz
            discogs_data: Data from Discogs
            upc: The UPC code
            
        Returns:
            Combined metadata
        """
        # Start with MusicBrainz as the primary source
        combined = musicbrainz_data.copy() if musicbrainz_data else {}
        
        # Add UPC
        combined["upc"] = upc
        
        # Extract year from date if we don't have it (for MusicBrainz data)
        if not combined.get("year") and combined.get("date"):
            # Extract year from date field (MusicBrainz uses date, not year)
            date_str = combined.get("date", "")
            if len(date_str) >= 4:
                combined["year"] = date_str[:4]
                logger.debug(f"Extracted year {combined['year']} from date {date_str}")
        
        # Supplement with Discogs data where MusicBrainz is missing
        if discogs_data:
            # Add Discogs-specific fields
            combined["discogs_id"] = discogs_data.get("discogs_id")
            combined["genres"] = discogs_data.get("genres", [])
            combined["styles"] = discogs_data.get("styles", [])
            combined["discogs_images"] = discogs_data.get("discogs_images", [])
            
            # Fill in missing fields from Discogs
            if not combined.get("title"):
                combined["title"] = discogs_data.get("title")
            
            if not combined.get("artist_name"):
                combined["artist_name"] = discogs_data.get("artist_name")
            
            # Use Discogs year if we still don't have one
            if not combined.get("year") and discogs_data.get("year"):
                combined["year"] = str(discogs_data["year"])
                logger.debug(f"Using Discogs year: {combined['year']}")
            
            if not combined.get("label_name"):
                combined["label_name"] = discogs_data.get("label_name")
            
            if not combined.get("catalog_number"):
                combined["catalog_number"] = discogs_data.get("catalog_number")
            
            if not combined.get("format"):
                combined["format"] = discogs_data.get("format")
            
            if not combined.get("country"):
                combined["country"] = discogs_data.get("country")
            
            if not combined.get("tracks") and discogs_data.get("tracks"):
                combined["tracks"] = discogs_data["tracks"]
                combined["track_count"] = discogs_data.get("track_count")
            
            # Add producer if we found one from Discogs
            if not combined.get("producer") and discogs_data.get("producer"):
                combined["producer"] = discogs_data["producer"]
                logger.debug(f"Using Discogs producer: {combined['producer']}")
        
        # Add metadata sources - only include sources that actually provided data
        sources = []
        # Check if MusicBrainz provided actual data (not just empty/None values)
        if musicbrainz_data and (musicbrainz_data.get("title") or musicbrainz_data.get("artist_name") or musicbrainz_data.get("mbid")):
            sources.append("musicbrainz")
        if discogs_data and (discogs_data.get("title") or discogs_data.get("artist_name") or discogs_data.get("discogs_id")):
            sources.append("discogs")
        combined["metadata_sources"] = sources
        
        # Add fetch timestamp
        combined["fetched_at"] = datetime.utcnow().isoformat()
        
        # Ensure we have at least basic required fields
        combined["is_complete"] = all([
            combined.get("title"),
            combined.get("artist_name"),
            combined.get("upc")
        ])
        
        return combined


# Global metadata fetcher instance
_metadata_fetcher = None


def get_metadata_fetcher() -> MetadataFetcher:
    """Get the global metadata fetcher instance."""
    global _metadata_fetcher
    if _metadata_fetcher is None:
        _metadata_fetcher = MetadataFetcher()
    return _metadata_fetcher
