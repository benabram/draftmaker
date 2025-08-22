"""Pytest configuration and fixtures."""

import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import patch

# Add project root to Python path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def mock_environment():
    """Mock environment variables for testing."""
    env_vars = {
        "EBAY_CLIENT_ID": "test_client_id",
        "EBAY_CLIENT_SECRET": "test_client_secret",
        "EBAY_REFRESH_TOKEN": "test_refresh_token",
        "EBAY_MARKETPLACE_ID": "EBAY_US",
        "EBAY_FULFILLMENT_POLICY_ID": "test_fulfillment",
        "EBAY_PAYMENT_POLICY_ID": "test_payment",
        "EBAY_RETURN_POLICY_ID": "test_return",
        "EBAY_CATEGORY_ID": "176984",
        "DISCOGS_PERSONAL_ACCESS_TOKEN": "test_discogs_personal_token",
        "DISCOGS_CONSUMER_KEY": "test_consumer_key",
        "DISCOGS_CONSUMER_SECRET": "test_consumer_secret",
        "SPOTIFY_CLIENT_ID": "test_spotify_id",
        "SPOTIFY_CLIENT_SECRET": "test_spotify_secret",
        "GOOGLE_APPLICATION_CREDENTIALS": "test_credentials.json",
    }

    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def sample_metadata():
    """Sample metadata response for testing."""
    return {
        "found": True,
        "upc": "123456789012",
        "title": "Test Album",
        "artist_name": "Test Artist",
        "year": 2020,
        "label_name": "Test Label",
        "catalog_number": "TEST001",
        "mbid": "test-mbid-123",
        "genres": ["Rock"],
        "styles": ["Alternative"],
        "track_count": 10,
        "tracks": [
            {"title": "Track 1", "position": "1", "duration": "3:45"},
            {"title": "Track 2", "position": "2", "duration": "4:20"},
        ],
    }


@pytest.fixture
def sample_pricing():
    """Sample pricing response for testing."""
    return {
        "recommended_price": 12.99,
        "min_price": 9.99,
        "max_price": 15.99,
        "average_price": 12.50,
        "median_price": 12.00,
        "confidence": "high",
        "sample_size": 15,
        "source": "ebay_completed",
    }


@pytest.fixture
def sample_images():
    """Sample images response for testing."""
    return {
        "upc": "123456789012",
        "primary_image": "https://example.com/primary.jpg",
        "images": [
            {
                "url": "https://example.com/front.jpg",
                "type": "front",
                "width": 500,
                "height": 500,
                "source": "coverartarchive",
            },
            {
                "url": "https://example.com/back.jpg",
                "type": "back",
                "width": 500,
                "height": 500,
                "source": "coverartarchive",
            },
        ],
        "source": "coverartarchive",
    }


@pytest.fixture
def sample_draft_result():
    """Sample draft creation result for testing."""
    return {
        "upc": "123456789012",
        "success": True,
        "sku": "CD_123456789012_20240101120000",
        "offer_id": "offer-12345",
        "listing_id": None,
        "error": None,
        "created_at": "2024-01-01T12:00:00",
    }
