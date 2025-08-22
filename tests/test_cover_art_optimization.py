"""Unit tests for optimized Cover Art Archive image fetching."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.components.image_fetcher import ImageFetcher


class TestCoverArtOptimization:
    """Test the optimized Cover Art Archive API implementation."""
    
    @pytest.fixture
    def image_fetcher(self):
        """Create an ImageFetcher instance for testing."""
        return ImageFetcher()
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        with patch('src.components.image_fetcher.settings') as mock:
            mock.musicbrainz_user_agent = "TestAgent/1.0"
            yield mock
    
    @pytest.mark.asyncio
    async def test_fetch_500px_success(self, image_fetcher, mock_settings):
        """Test successful fetch of 500px image (highest priority)."""
        mbid = "test-mbid-123"
        
        # Mock the HTTP client
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # Mock successful 500px response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            
            # Call the method
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify the results
            assert len(result) == 1
            assert result[0]["url"] == f"https://coverartarchive.org/release/{mbid}/front-500.jpg"
            assert result[0]["thumbnail_500"] == result[0]["url"]
            assert result[0]["thumbnail_250"] is None
            assert result[0]["thumbnail_large"] is None
            assert result[0]["is_front"] is True
            assert result[0]["size_px"] == 500
            assert result[0]["ebay_url"] == result[0]["url"]
            
            # Verify only one API call was made (no fallback needed)
            assert mock_client.get.call_count == 1
            mock_client.get.assert_called_with(
                f"https://coverartarchive.org/release/{mbid}/front-500.jpg",
                headers={"User-Agent": "TestAgent/1.0"},
                timeout=10.0,
                follow_redirects=True
            )
    
    @pytest.mark.asyncio
    async def test_fallback_to_250px(self, image_fetcher, mock_settings):
        """Test fallback to 250px when 500px is not available."""
        mbid = "test-mbid-456"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # Mock responses: 500px fails, 250px succeeds
            responses = [
                MagicMock(status_code=404),  # 500px not found
                MagicMock(status_code=200),  # 250px found
            ]
            mock_client.get.side_effect = responses
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify fallback worked
            assert len(result) == 1
            assert result[0]["url"] == f"https://coverartarchive.org/release/{mbid}/front-250.jpg"
            assert result[0]["thumbnail_250"] == result[0]["url"]
            assert result[0]["thumbnail_500"] is None
            assert result[0]["size_px"] == 250
            
            # Verify two API calls were made
            assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_fallback_to_1000px(self, image_fetcher, mock_settings):
        """Test fallback to 1000px when both 500px and 250px are not available."""
        mbid = "test-mbid-789"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # Mock responses: 500px and 250px fail, 1000px succeeds
            responses = [
                MagicMock(status_code=404),  # 500px not found
                MagicMock(status_code=404),  # 250px not found
                MagicMock(status_code=200),  # 1000px found
            ]
            mock_client.get.side_effect = responses
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify fallback worked
            assert len(result) == 1
            assert result[0]["url"] == f"https://coverartarchive.org/release/{mbid}/front-1000.jpg"
            assert result[0]["thumbnail_large"] == result[0]["url"]
            assert result[0]["thumbnail_500"] is None
            assert result[0]["thumbnail_250"] is None
            assert result[0]["size_px"] == 1000
            
            # Verify three API calls were made
            assert mock_client.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_images_available(self, image_fetcher, mock_settings):
        """Test when no images are available at any resolution."""
        mbid = "test-mbid-none"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # All sizes return 404
            responses = [
                MagicMock(status_code=404),  # 500px not found
                MagicMock(status_code=404),  # 250px not found
                MagicMock(status_code=404),  # 1000px not found
            ]
            mock_client.get.side_effect = responses
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify empty result
            assert result == []
            
            # Verify all three sizes were tried
            assert mock_client.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_service_unavailable(self, image_fetcher, mock_settings):
        """Test handling of service unavailable (503) response."""
        mbid = "test-mbid-503"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # Service unavailable on first try
            mock_response = MagicMock(status_code=503)
            mock_client.get.return_value = mock_response
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify empty result and no further attempts
            assert result == []
            assert mock_client.get.call_count == 1  # Should stop after 503
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, image_fetcher, mock_settings):
        """Test handling of timeout errors with fallback."""
        mbid = "test-mbid-timeout"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # First call times out, second succeeds
            mock_client.get.side_effect = [
                httpx.TimeoutException("Request timed out"),
                MagicMock(status_code=200)  # 250px succeeds
            ]
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify fallback worked after timeout
            assert len(result) == 1
            assert result[0]["url"] == f"https://coverartarchive.org/release/{mbid}/front-250.jpg"
            assert mock_client.get.call_count == 2
    
    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self, image_fetcher, mock_settings):
        """Test handling of unexpected errors with fallback."""
        mbid = "test-mbid-error"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # First two calls fail with errors, third succeeds
            mock_client.get.side_effect = [
                Exception("Network error"),
                httpx.HTTPError("HTTP error"),
                MagicMock(status_code=200)  # 1000px succeeds
            ]
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify fallback worked after errors
            assert len(result) == 1
            assert result[0]["url"] == f"https://coverartarchive.org/release/{mbid}/front-1000.jpg"
            assert mock_client.get.call_count == 3
    
    @pytest.mark.asyncio
    async def test_backward_compatibility(self, image_fetcher, mock_settings):
        """Test that the response structure maintains backward compatibility."""
        mbid = "test-mbid-compat"
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock(status_code=200)
            mock_client.get.return_value = mock_response
            
            result = await image_fetcher._fetch_from_cover_art_archive(mbid)
            
            # Verify all expected fields are present
            assert len(result) == 1
            image = result[0]
            
            # Check all fields that were in the original implementation
            assert "url" in image
            assert "thumbnail_500" in image
            assert "thumbnail_250" in image
            assert "thumbnail_large" in image
            assert "thumbnail_small" in image
            assert "is_front" in image
            assert "is_back" in image
            assert "comment" in image
            assert "types" in image
            assert "approved" in image
            assert "source" in image
            assert "ebay_url" in image
            
            # Verify correct values
            assert image["source"] == "cover_art_archive"
            assert image["is_front"] is True
            assert image["is_back"] is False
            assert image["approved"] is True
    
    @pytest.mark.asyncio
    async def test_integration_with_fetch_images(self, image_fetcher, mock_settings):
        """Test integration with the main fetch_images method."""
        metadata = {
            "upc": "123456789012",
            "mbid": "test-mbid-integration",
            "title": "Test Album",
            "artist_name": "Test Artist"
        }
        
        with patch('httpx.AsyncClient') as MockClient:
            mock_client = AsyncMock()
            MockClient.return_value.__aenter__.return_value = mock_client
            
            # Mock successful 500px response for Cover Art Archive
            mock_response = MagicMock(status_code=200)
            mock_client.get.return_value = mock_response
            
            # Mock the token manager for Spotify (not used in this test)
            with patch.object(image_fetcher.token_manager, 'get_spotify_token', 
                            new_callable=AsyncMock) as mock_token:
                mock_token.return_value = "test_token"
                
                result = await image_fetcher.fetch_images(metadata)
                
                # Verify the result structure
                assert result["upc"] == metadata["upc"]
                assert result["mbid"] == metadata["mbid"]
                assert len(result["images"]) == 1
                assert result["primary_image"] is not None
                assert "cover_art_archive" in result["sources"]
                
                # Verify the image was fetched using the optimized method
                expected_url = f"https://coverartarchive.org/release/{metadata['mbid']}/front-500.jpg"
                assert result["primary_image"] == expected_url
