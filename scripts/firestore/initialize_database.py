#!/usr/bin/env python3
"""
Initialize Firestore database with collections and sample documents.

This script creates all collections defined in firestore-schema.json
and adds sample documents for testing and validation.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from google.cloud import firestore
from src.config import settings

# Initialize Firestore client
db = firestore.Client(project=settings.gcp_project_id)


def load_schema():
    """Load the Firestore schema definition."""
    schema_path = project_root / "firestore-schema.json"
    with open(schema_path, "r") as f:
        return json.load(f)


def create_sample_upc_mapping():
    """Create a sample UPC mapping document."""
    return {
        "upc": "722975007524",
        "mbid": "a84d91d4-3e03-4e7e-b760-2c316f5b6d78",
        "discogs_id": "1234567",
        "created_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "source": "musicbrainz"
    }


def create_sample_album_metadata():
    """Create a sample album metadata document."""
    now = datetime.utcnow()
    ttl = now + timedelta(days=30)
    
    return {
        "mbid": "a84d91d4-3e03-4e7e-b760-2c316f5b6d78",
        "upc": "722975007524",
        "artist_name": "The Beatles",
        "title": "Abbey Road",
        "release_date": "1969-09-26",
        "year": "1969",
        "label_name": "Apple Records",
        "catalog_number": "PCS 7088",
        "format": "CD",
        "country": "US",
        "genres": ["Rock", "Pop"],
        "styles": ["Psychedelic Rock", "Pop Rock"],
        "track_count": 17,
        "tracks": [
            {"position": "1", "title": "Come Together", "duration": "4:19"},
            {"position": "2", "title": "Something", "duration": "3:03"},
            {"position": "3", "title": "Maxwell's Silver Hammer", "duration": "3:27"}
        ],
        "metadata_sources": ["musicbrainz", "discogs"],
        "is_complete": True,
        "cached_at": now,
        "ttl": ttl
    }


def create_sample_album_images():
    """Create a sample album images document."""
    now = datetime.utcnow()
    ttl = now + timedelta(days=30)
    
    return {
        "identifier": "a84d91d4-3e03-4e7e-b760-2c316f5b6d78",
        "identifier_type": "mbid",
        "cover_art_archive": [
            {
                "url": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678.jpg",
                "thumbnail_500": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678-500.jpg",
                "thumbnail_250": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678-250.jpg",
                "width": 1000,
                "height": 1000,
                "is_front": True,
                "is_back": False,
                "types": ["Front"],
                "approved": True
            }
        ],
        "spotify_images": [
            {
                "url": "https://i.scdn.co/image/ab67616d0000b273dc30583ba717007b00cceb25",
                "width": 640,
                "height": 640,
                "size_category": "large"
            }
        ],
        "primary_image_url": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678.jpg",
        "thumbnail_url": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678-500.jpg",
        "ebay_url": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678-500.jpg",
        "sources": ["cover_art_archive", "spotify"],
        "cached_at": now,
        "ttl": ttl
    }


def create_sample_pricing_data():
    """Create a sample pricing data document."""
    now = datetime.utcnow()
    ttl = now + timedelta(days=7)
    date_range_start = now - timedelta(days=90)
    
    return {
        "upc": "722975007524",
        "title": "Abbey Road",
        "artist": "The Beatles",
        "condition": "Very Good",
        "average_price": 12.99,
        "median_price": 11.99,
        "min_price": 8.99,
        "max_price": 19.99,
        "recommended_price": 11.49,
        "sample_size": 25,
        "confidence": "high",
        "price_strategy": "competitive",
        "currency": "USD",
        "search_method": "upc",
        "date_range_start": date_range_start,
        "date_range_end": now,
        "sample_listings": [
            {
                "title": "The Beatles - Abbey Road CD",
                "price": 12.99,
                "condition": "Very Good",
                "end_time": "2025-08-15T10:30:00Z",
                "url": "https://www.ebay.com/itm/123456789"
            }
        ],
        "cached_at": now,
        "ttl": ttl
    }


def create_sample_draft_listing():
    """Create a sample draft listing document."""
    now = datetime.utcnow()
    
    return {
        "offer_id": "offer_123456",
        "sku": f"CD_722975007524_{now.strftime('%Y%m%d%H%M%S')}",
        "upc": "722975007524",
        "title": "The Beatles - Abbey Road (1969) CD Apple Records PCS 7088",
        "artist": "The Beatles",
        "album": "Abbey Road",
        "condition": "USED_VERY_GOOD",
        "price": 11.49,
        "currency": "USD",
        "quantity": 1,
        "category_id": "176984",
        "listing_format": "FIXED_PRICE",
        "status": "draft",
        "primary_image_url": "https://coverartarchive.org/release/a84d91d4-3e03-4e7e-b760-2c316f5b6d78/12345678-500.jpg",
        "fulfillment_policy_id": settings.ebay_fulfillment_policy_id,
        "payment_policy_id": settings.ebay_payment_policy_id,
        "return_policy_id": settings.ebay_return_policy_id,
        "created_at": now,
        "updated_at": now
    }


def create_sample_batch_job():
    """Create a sample batch job document."""
    now = datetime.utcnow()
    
    return {
        "job_id": f"batch_{now.strftime('%Y%m%d%H%M%S')}",
        "type": "full_pipeline",
        "status": "completed",
        "total_items": 10,
        "processed_items": 10,
        "successful_items": 8,
        "failed_items": 2,
        "input_source": "gs://draft-maker-bucket/upcs/test_batch.txt",
        "input_data": settings.test_upc_codes[:10],
        "results_summary": {
            "metadata_fetched": 10,
            "images_fetched": 8,
            "pricing_fetched": 9,
            "drafts_created": 8
        },
        "processing_time_seconds": 45.3,
        "started_at": now - timedelta(minutes=1),
        "completed_at": now,
        "created_at": now - timedelta(minutes=2),
        "created_by": "system"
    }


def create_sample_api_log():
    """Create a sample API log document."""
    now = datetime.utcnow()
    ttl = now + timedelta(days=7)
    
    return {
        "api_name": "musicbrainz",
        "endpoint": "/ws/2/release",
        "method": "GET",
        "request_params": {
            "query": "barcode:722975007524",
            "fmt": "json",
            "inc": "artists+labels+recordings"
        },
        "response_status": 200,
        "response_time_ms": 234,
        "response_size_bytes": 4567,
        "success": True,
        "batch_job_id": f"batch_{now.strftime('%Y%m%d%H%M%S')}",
        "upc": "722975007524",
        "timestamp": now,
        "ttl": ttl
    }


def create_sample_processed_file():
    """Create a sample processed file document."""
    now = datetime.utcnow()
    
    return {
        "file_path": "gs://draft-maker-bucket/upcs/test_batch.txt",
        "file_name": "test_batch.txt",
        "source_type": "gcs",
        "total_upcs": 10,
        "valid_upcs": 10,
        "processed_upcs": 8,
        "batch_job_id": f"batch_{now.strftime('%Y%m%d%H%M%S')}",
        "processed_at": now,
        "processing_time_seconds": 45.3,
        "status": "completed"
    }


def initialize_collection(collection_name, sample_data, doc_id=None):
    """Initialize a collection with sample data."""
    try:
        collection_ref = db.collection(collection_name)
        
        if doc_id:
            # Use specific document ID
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(sample_data)
            print(f"✓ Created document in {collection_name} with ID: {doc_id}")
        else:
            # Let Firestore generate ID
            doc_ref = collection_ref.add(sample_data)
            print(f"✓ Created document in {collection_name} with auto-generated ID")
        
        return True
    except Exception as e:
        print(f"✗ Error creating document in {collection_name}: {e}")
        return False


def main():
    """Main initialization function."""
    print("=" * 60)
    print("Firestore Database Initialization")
    print("=" * 60)
    print(f"Project: {settings.gcp_project_id}")
    print(f"Environment: {settings.environment}")
    print()
    
    # Load schema
    schema = load_schema()
    print(f"Loaded schema with {len(schema['collections'])} collections")
    print()
    
    # Initialize collections with sample data
    collections_to_init = [
        ("upc_mappings", create_sample_upc_mapping(), "722975007524"),
        ("album_metadata", create_sample_album_metadata(), "a84d91d4-3e03-4e7e-b760-2c316f5b6d78"),
        ("album_images", create_sample_album_images(), "a84d91d4-3e03-4e7e-b760-2c316f5b6d78"),
        ("pricing_data", create_sample_pricing_data(), None),  # Auto-generated ID
        ("draft_listings", create_sample_draft_listing(), None),  # Auto-generated ID
        ("batch_jobs", create_sample_batch_job(), None),  # Auto-generated ID
        ("api_logs", create_sample_api_log(), None),  # Auto-generated ID
        ("processed_files", create_sample_processed_file(), "draft-maker-bucket_upcs_test_batch.txt")  # Use underscore instead of slashes
    ]
    
    print("Initializing collections with sample data...")
    print("-" * 40)
    
    success_count = 0
    for collection_name, sample_data, doc_id in collections_to_init:
        if initialize_collection(collection_name, sample_data, doc_id):
            success_count += 1
    
    print("-" * 40)
    print(f"Initialization complete: {success_count}/{len(collections_to_init)} collections initialized")
    
    # Create health check documents
    print()
    print("Creating health check documents...")
    print("-" * 40)
    
    health_check_data = {
        "type": "health_check",
        "status": "healthy",
        "created_at": firestore.SERVER_TIMESTAMP,
        "environment": settings.environment
    }
    
    for collection_name in schema["collections"].keys():
        try:
            collection_ref = db.collection(collection_name)
            doc_ref = collection_ref.document("_health_check")
            doc_ref.set(health_check_data)
            print(f"✓ Created health check for {collection_name}")
        except Exception as e:
            print(f"✗ Error creating health check for {collection_name}: {e}")
    
    print("-" * 40)
    print()
    print("Database initialization complete!")
    print()
    
    # Print deployment instructions
    print("Next steps:")
    print("1. Deploy security rules: firebase deploy --only firestore:rules")
    print("2. Deploy indexes: firebase deploy --only firestore:indexes")
    print("3. Or deploy both: firebase deploy --only firestore")
    print()
    print("Note: Make sure you have Firebase CLI installed and configured")
    print("Installation: npm install -g firebase-tools")
    print("Login: firebase login")
    print("Initialize: firebase init firestore")


if __name__ == "__main__":
    main()
