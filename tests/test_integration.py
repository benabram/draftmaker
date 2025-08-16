"""Integration tests for the complete pipeline."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import json

from src.orchestrator import ListingOrchestrator


class TestIntegration:
    """Integration tests for the complete listing creation pipeline."""
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_success(self, sample_metadata, sample_pricing, sample_images, sample_draft_result):
        """Test the complete pipeline from UPC to draft listing."""
        
        # Create orchestrator with partially mocked components
        with patch('src.orchestrator.get_upc_processor') as mock_upc_getter:
            with patch('src.orchestrator.get_metadata_fetcher') as mock_meta_getter:
                with patch('src.orchestrator.get_pricing_fetcher') as mock_price_getter:
                    with patch('src.orchestrator.get_image_fetcher') as mock_image_getter:
                        with patch('src.orchestrator.get_draft_composer') as mock_draft_getter:
                            
                            # Set up mock components
                            mock_upc = Mock()
                            mock_upc.load_upcs_from_gcs.return_value = ["123456789012"]
                            mock_upc_getter.return_value = mock_upc
                            
                            mock_meta = AsyncMock()
                            mock_meta.fetch_metadata.return_value = sample_metadata
                            mock_meta_getter.return_value = mock_meta
                            
                            mock_price = AsyncMock()
                            mock_price.fetch_pricing.return_value = sample_pricing
                            mock_price_getter.return_value = mock_price
                            
                            mock_image = AsyncMock()
                            mock_image.fetch_images.return_value = sample_images
                            mock_image_getter.return_value = mock_image
                            
                            mock_draft = AsyncMock()
                            mock_draft.create_draft_listing.return_value = sample_draft_result
                            mock_draft_getter.return_value = mock_draft
                            
                            orchestrator = ListingOrchestrator()
                            
                            # Mock save results to avoid file I/O
                            with patch.object(orchestrator, '_save_results', new_callable=AsyncMock):
                                # Process batch
                                result = await orchestrator.process_batch(
                                    "gs://test-bucket/upcs.txt",
                                    create_drafts=True,
                                    save_results=True,
                                    is_gcs=True
                                )
        
        # Verify the result
        assert result["total_upcs"] == 1
        assert result["successful"] == 1
        assert result["failed"] == 0
        assert result["success_rate"] == 100.0
        
        # Verify all components were called
        mock_upc.load_upcs_from_gcs.assert_called_once_with("test-bucket", "upcs.txt")
        mock_meta.fetch_metadata.assert_called_once_with("123456789012")
        mock_price.fetch_pricing.assert_called_once()
        mock_image.fetch_images.assert_called_once()
        mock_draft.create_draft_listing.assert_called_once()
        
        # Check the result contains expected data
        listing_result = result["results"][0]
        assert listing_result["upc"] == "123456789012"
        assert listing_result["success"] == True
        assert listing_result["metadata"]["title"] == "Test Album"
        assert listing_result["pricing"]["recommended_price"] == 12.99
        assert listing_result["draft"]["offer_id"] == "offer-12345"
    
    @pytest.mark.asyncio
    async def test_pipeline_with_failures(self):
        """Test pipeline handling partial failures."""
        
        with patch('src.orchestrator.get_upc_processor') as mock_upc_getter:
            with patch('src.orchestrator.get_metadata_fetcher') as mock_meta_getter:
                with patch('src.orchestrator.get_pricing_fetcher') as mock_price_getter:
                    with patch('src.orchestrator.get_image_fetcher') as mock_image_getter:
                        with patch('src.orchestrator.get_draft_composer') as mock_draft_getter:
                            
                            # Set up mock components
                            mock_upc = Mock()
                            mock_upc.load_upcs_from_gcs.return_value = [
                                "111111111111",
                                "222222222222",
                                "333333333333"
                            ]
                            mock_upc_getter.return_value = mock_upc
                            
                            mock_meta = AsyncMock()
                            mock_meta.fetch_metadata.side_effect = [
                                {"found": True, "upc": "111111111111", "title": "Album 1", "artist_name": "Artist 1"},
                                {"found": False, "upc": "222222222222"},  # No metadata found
                                {"found": True, "upc": "333333333333", "title": "Album 3", "artist_name": "Artist 3"}
                            ]
                            mock_meta_getter.return_value = mock_meta
                            
                            mock_price = AsyncMock()
                            mock_price.fetch_pricing.return_value = {"recommended_price": 9.99}
                            mock_price_getter.return_value = mock_price
                            
                            mock_image = AsyncMock()
                            mock_image.fetch_images.return_value = {"primary_image": None, "images": []}
                            mock_image_getter.return_value = mock_image
                            
                            mock_draft = AsyncMock()
                            mock_draft.create_draft_listing.side_effect = [
                                {"success": True, "offer_id": "offer-1"},
                                {"success": False, "error": "Draft creation failed"}
                            ]
                            mock_draft_getter.return_value = mock_draft
                            
                            orchestrator = ListingOrchestrator()
                            
                            with patch.object(orchestrator, '_save_results', new_callable=AsyncMock):
                                result = await orchestrator.process_batch(
                                    "gs://test-bucket/upcs.txt",
                                    create_drafts=True,
                                    save_results=True,
                                    is_gcs=True
                                )
        
        # Verify mixed results
        assert result["total_upcs"] == 3
        assert result["successful"] == 1  # Only first one succeeded
        assert result["failed"] == 2  # Second had no metadata, third failed draft creation
        assert result["success_rate"] == pytest.approx(33.33, rel=0.01)
        
        # Check individual results
        assert result["results"][0]["success"] == True
        assert result["results"][1]["success"] == False
        assert result["results"][2]["success"] == False
    
    @pytest.mark.asyncio
    async def test_local_file_processing(self, tmp_path):
        """Test processing UPCs from a local file."""
        
        # Create a temporary UPC file
        upc_file = tmp_path / "test_upcs.txt"
        upc_file.write_text("123456789012\n987654321098\ninvalid_upc\n")
        
        with patch('src.orchestrator.get_upc_processor') as mock_upc_getter:
            with patch('src.orchestrator.get_metadata_fetcher') as mock_meta_getter:
                with patch('src.orchestrator.get_pricing_fetcher') as mock_price_getter:
                    with patch('src.orchestrator.get_image_fetcher') as mock_image_getter:
                        with patch('src.orchestrator.get_draft_composer') as mock_draft_getter:
                            
                            # Set up mock components
                            mock_upc = Mock()
                            mock_upc.load_upcs_from_local_txt.return_value = [
                                "123456789012",
                                "987654321098"
                            ]  # Invalid UPC should be filtered
                            mock_upc_getter.return_value = mock_upc
                            
                            # Set up other mocks to return success
                            mock_meta = AsyncMock()
                            mock_meta.fetch_metadata.return_value = {
                                "found": True,
                                "title": "Test Album",
                                "artist_name": "Test Artist"
                            }
                            mock_meta_getter.return_value = mock_meta
                            
                            mock_price = AsyncMock()
                            mock_price.fetch_pricing.return_value = {"recommended_price": 10.99}
                            mock_price_getter.return_value = mock_price
                            
                            mock_image = AsyncMock()
                            mock_image.fetch_images.return_value = {"primary_image": "test.jpg"}
                            mock_image_getter.return_value = mock_image
                            
                            mock_draft = AsyncMock()
                            mock_draft.create_draft_listing.return_value = {"success": True}
                            mock_draft_getter.return_value = mock_draft
                            
                            orchestrator = ListingOrchestrator()
                            
                            with patch.object(orchestrator, '_save_results', new_callable=AsyncMock):
                                result = await orchestrator.process_batch(
                                    str(upc_file),
                                    create_drafts=True,
                                    save_results=False,
                                    is_gcs=False
                                )
        
        assert result["total_upcs"] == 2
        assert result["source_type"] == "local"
        mock_upc.load_upcs_from_local_txt.assert_called_once_with(str(upc_file))
    
    @pytest.mark.asyncio
    async def test_test_mode_no_drafts(self):
        """Test that test mode doesn't create drafts."""
        
        with patch('src.orchestrator.get_upc_processor') as mock_upc_getter:
            with patch('src.orchestrator.get_metadata_fetcher') as mock_meta_getter:
                with patch('src.orchestrator.get_pricing_fetcher') as mock_price_getter:
                    with patch('src.orchestrator.get_image_fetcher') as mock_image_getter:
                        with patch('src.orchestrator.get_draft_composer') as mock_draft_getter:
                            
                            mock_upc = Mock()
                            mock_upc.load_upcs_from_gcs.return_value = ["123456789012"]
                            mock_upc_getter.return_value = mock_upc
                            
                            mock_meta = AsyncMock()
                            mock_meta.fetch_metadata.return_value = {
                                "found": True,
                                "title": "Test"
                            }
                            mock_meta_getter.return_value = mock_meta
                            
                            mock_price = AsyncMock()
                            mock_price.fetch_pricing.return_value = {"recommended_price": 9.99}
                            mock_price_getter.return_value = mock_price
                            
                            mock_image = AsyncMock()
                            mock_image.fetch_images.return_value = {}
                            mock_image_getter.return_value = mock_image
                            
                            mock_draft = AsyncMock()
                            mock_draft_getter.return_value = mock_draft
                            
                            orchestrator = ListingOrchestrator()
                            
                            with patch.object(orchestrator, '_save_results', new_callable=AsyncMock):
                                result = await orchestrator.process_batch(
                                    "gs://test-bucket/upcs.txt",
                                    create_drafts=False,  # Test mode
                                    save_results=False,
                                    is_gcs=True
                                )
        
        # Should fetch data but not create drafts
        assert result["successful"] == 1
        mock_meta.fetch_metadata.assert_called_once()
        mock_price.fetch_pricing.assert_called_once()
        mock_image.fetch_images.assert_called_once()
        mock_draft.create_draft_listing.assert_not_called()  # No drafts in test mode
