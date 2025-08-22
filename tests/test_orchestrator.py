"""Tests for the orchestrator component."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.orchestrator import ListingOrchestrator


class TestOrchestrator:
    """Test suite for the orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create an orchestrator instance with mocked components."""
        with patch("src.orchestrator.get_upc_processor") as mock_upc:
            with patch("src.orchestrator.get_metadata_fetcher") as mock_meta:
                with patch("src.orchestrator.get_pricing_fetcher") as mock_price:
                    with patch("src.orchestrator.get_image_fetcher") as mock_image:
                        with patch("src.orchestrator.get_draft_composer") as mock_draft:
                            orchestrator = ListingOrchestrator()

                            # Set up mocked components
                            orchestrator.upc_processor = Mock()
                            orchestrator.metadata_fetcher = AsyncMock()
                            orchestrator.pricing_fetcher = AsyncMock()
                            orchestrator.image_fetcher = AsyncMock()
                            orchestrator.draft_composer = AsyncMock()

                            return orchestrator

    @pytest.mark.asyncio
    async def test_process_single_upc_success(self, orchestrator):
        """Test successful processing of a single UPC."""
        # Mock responses
        orchestrator.metadata_fetcher.fetch_metadata.return_value = {
            "found": True,
            "upc": "123456789012",
            "title": "Test Album",
            "artist_name": "Test Artist",
            "year": 2020,
            "mbid": "test-mbid",
        }

        orchestrator.pricing_fetcher.fetch_pricing.return_value = {
            "recommended_price": 12.99,
            "min_price": 9.99,
            "max_price": 15.99,
            "confidence": "high",
            "sample_size": 10,
        }

        orchestrator.image_fetcher.fetch_images.return_value = {
            "primary_image": "https://example.com/image.jpg",
            "images": [{"url": "https://example.com/image.jpg", "type": "front"}],
        }

        orchestrator.draft_composer.create_draft_listing.return_value = {
            "success": True,
            "sku": "CD_123456789012_20240101120000",
            "offer_id": "offer-123",
            "listing_id": None,
        }

        result = await orchestrator.process_single_upc(
            "123456789012", create_draft=True
        )

        assert result["success"] == True
        assert result["upc"] == "123456789012"
        assert result["metadata"]["title"] == "Test Album"
        assert result["pricing"]["recommended_price"] == 12.99
        assert result["images"]["primary_image"] == "https://example.com/image.jpg"
        assert result["draft"]["offer_id"] == "offer-123"

    @pytest.mark.asyncio
    async def test_process_single_upc_no_metadata(self, orchestrator):
        """Test processing when no metadata is found."""
        orchestrator.metadata_fetcher.fetch_metadata.return_value = {
            "found": False,
            "upc": "000000000000",
        }

        result = await orchestrator.process_single_upc(
            "000000000000", create_draft=True
        )

        assert result["success"] == False
        assert result["error"] == "No metadata found"
        assert result["metadata"]["found"] == False

        # Should not call other components if metadata not found
        orchestrator.pricing_fetcher.fetch_pricing.assert_not_called()
        orchestrator.image_fetcher.fetch_images.assert_not_called()
        orchestrator.draft_composer.create_draft_listing.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_single_upc_default_pricing(self, orchestrator):
        """Test using default pricing when pricing fetch fails."""
        orchestrator.metadata_fetcher.fetch_metadata.return_value = {
            "found": True,
            "upc": "123456789012",
            "title": "Test Album",
            "artist_name": "Test Artist",
        }

        orchestrator.pricing_fetcher.fetch_pricing.return_value = None

        orchestrator.image_fetcher.fetch_images.return_value = {
            "primary_image": None,
            "images": [],
        }

        orchestrator.draft_composer.create_draft_listing.return_value = {
            "success": True,
            "sku": "CD_123456789012_20240101120000",
            "offer_id": "offer-123",
        }

        result = await orchestrator.process_single_upc(
            "123456789012", create_draft=True
        )

        assert result["success"] == True
        assert result["pricing"]["recommended_price"] == 9.99  # Default price
        assert result["pricing"]["confidence"] == "none"
        assert result["pricing"]["source"] == "default"

    @pytest.mark.asyncio
    async def test_process_single_upc_test_mode(self, orchestrator):
        """Test processing in test mode (no draft creation)."""
        orchestrator.metadata_fetcher.fetch_metadata.return_value = {
            "found": True,
            "upc": "123456789012",
            "title": "Test Album",
        }

        orchestrator.pricing_fetcher.fetch_pricing.return_value = {
            "recommended_price": 10.99
        }

        orchestrator.image_fetcher.fetch_images.return_value = {
            "primary_image": "https://example.com/image.jpg"
        }

        result = await orchestrator.process_single_upc(
            "123456789012", create_draft=False
        )

        assert result["success"] == True
        assert result["draft"] is None

        # Should not call draft composer in test mode
        orchestrator.draft_composer.create_draft_listing.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_batch_gcs_success(self, orchestrator):
        """Test successful batch processing from GCS."""
        orchestrator.upc_processor.load_upcs_from_gcs.return_value = [
            "123456789012",
            "987654321098",
        ]

        # Mock process_single_upc to return success
        with patch.object(
            orchestrator, "process_single_upc", new_callable=AsyncMock
        ) as mock_process:
            mock_process.side_effect = [
                {"upc": "123456789012", "success": True},
                {"upc": "987654321098", "success": True},
            ]

            with patch.object(orchestrator, "_save_results", new_callable=AsyncMock):
                result = await orchestrator.process_batch(
                    "gs://test-bucket/upcs.txt",
                    create_drafts=True,
                    save_results=True,
                    is_gcs=True,
                )

        assert result["total_upcs"] == 2
        assert result["successful"] == 2
        assert result["failed"] == 0
        assert result["success_rate"] == 100.0
        assert result["source_type"] == "gcs"

        orchestrator.upc_processor.load_upcs_from_gcs.assert_called_with(
            "test-bucket", "upcs.txt"
        )

    @pytest.mark.asyncio
    async def test_process_batch_local_file(self, orchestrator):
        """Test batch processing from local file."""
        orchestrator.upc_processor.load_upcs_from_local_txt.return_value = [
            "111111111111"
        ]

        with patch.object(
            orchestrator, "process_single_upc", new_callable=AsyncMock
        ) as mock_process:
            mock_process.return_value = {"upc": "111111111111", "success": True}

            with patch.object(orchestrator, "_save_results", new_callable=AsyncMock):
                result = await orchestrator.process_batch(
                    "data/test.txt",
                    create_drafts=False,
                    save_results=True,
                    is_gcs=False,
                )

        assert result["total_upcs"] == 1
        assert result["successful"] == 1
        assert result["source_type"] == "local"

        orchestrator.upc_processor.load_upcs_from_local_txt.assert_called_with(
            "data/test.txt"
        )

    @pytest.mark.asyncio
    async def test_process_batch_invalid_gcs_path(self, orchestrator):
        """Test handling of invalid GCS path format."""
        result = await orchestrator.process_batch(
            "invalid-path", create_drafts=True, save_results=False, is_gcs=True
        )

        assert result["success"] == False
        assert "GCS path must start with gs://" in result["error"]
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_process_batch_no_upcs_found(self, orchestrator):
        """Test handling when no valid UPCs are found."""
        orchestrator.upc_processor.load_upcs_from_gcs.return_value = []

        result = await orchestrator.process_batch(
            "gs://test-bucket/empty.txt",
            create_drafts=True,
            save_results=False,
            is_gcs=True,
        )

        assert result["success"] == False
        assert result["error"] == "No valid UPCs found"
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_process_batch_mixed_results(self, orchestrator):
        """Test batch processing with mixed success/failure results."""
        orchestrator.upc_processor.load_upcs_from_gcs.return_value = [
            "111111111111",
            "222222222222",
            "333333333333",
        ]

        with patch.object(
            orchestrator, "process_single_upc", new_callable=AsyncMock
        ) as mock_process:
            mock_process.side_effect = [
                {"upc": "111111111111", "success": True},
                {"upc": "222222222222", "success": False, "error": "No metadata"},
                {"upc": "333333333333", "success": True},
            ]

            with patch.object(orchestrator, "_save_results", new_callable=AsyncMock):
                result = await orchestrator.process_batch(
                    "gs://test-bucket/upcs.txt",
                    create_drafts=True,
                    save_results=True,
                    is_gcs=True,
                )

        assert result["total_upcs"] == 3
        assert result["successful"] == 2
        assert result["failed"] == 1
        assert result["success_rate"] == pytest.approx(66.67, rel=0.01)

    @pytest.mark.asyncio
    async def test_save_results(self, orchestrator):
        """Test saving results to files."""
        summary = {
            "input_source": "gs://test/upcs.txt",
            "source_type": "gcs",
            "total_upcs": 1,
            "successful": 1,
            "failed": 0,
            "success_rate": 100.0,
            "processing_time_seconds": 5.0,
            "start_time": datetime.utcnow().isoformat(),
            "end_time": datetime.utcnow().isoformat(),
            "results": [
                {
                    "upc": "123456789012",
                    "success": True,
                    "metadata": {
                        "artist_name": "Artist",
                        "title": "Album",
                        "year": 2020,
                    },
                    "pricing": {"recommended_price": 10.99},
                    "draft": {
                        "sku": "CD_123456789012_20240101",
                        "offer_id": "offer-123",
                    },
                }
            ],
        }

        with patch("builtins.open", create=True) as mock_open:
            with patch("json.dump") as mock_json_dump:
                await orchestrator._save_results(summary)

        # Should create both JSON and CSV files
        assert mock_open.call_count == 2  # One for JSON, one for CSV
