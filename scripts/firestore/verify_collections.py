#!/usr/bin/env python3
"""
Verify that all Firestore collections have been created and show document counts.
"""

import sys
from pathlib import Path
from google.cloud import firestore
from tabulate import tabulate

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings


def verify_collections():
    """Verify all collections exist and count documents."""
    
    # Initialize Firestore client (using default database)
    db = firestore.Client(project=settings.gcp_project_id)
    
    print("=" * 60)
    print("Firestore Collections Verification")
    print("=" * 60)
    print(f"Project: {settings.gcp_project_id}")
    print(f"Database: (default)")
    print()
    
    # Expected collections from schema
    expected_collections = [
        "upc_mappings",
        "album_metadata",
        "album_images",
        "pricing_data",
        "oauth_tokens",
        "draft_listings",
        "batch_jobs",
        "api_logs",
        "processed_files"
    ]
    
    # Existing collections from config (might be in use)
    existing_collections = [
        settings.firestore_collection_mbid,  # mbid_cache
        settings.firestore_collection_logs,  # function_logs
        settings.firestore_collection_tokens,  # api_tokens
        settings.firestore_collection_processed_files,  # processed_files
        settings.firestore_collection_draft_listings  # draft_listings
    ]
    
    print("Checking Collections...")
    print("-" * 40)
    
    results = []
    
    # Check expected collections
    for collection_name in expected_collections:
        try:
            collection_ref = db.collection(collection_name)
            # Count documents (limit to avoid performance issues)
            docs = collection_ref.limit(1000).stream()
            doc_count = sum(1 for _ in docs)
            
            # Check if health check exists
            health_check = collection_ref.document("_health_check").get()
            has_health_check = health_check.exists
            
            results.append([
                collection_name,
                "✓",
                doc_count,
                "✓" if has_health_check else "✗",
                "Active"
            ])
            
        except Exception as e:
            results.append([
                collection_name,
                "✗",
                0,
                "✗",
                f"Error: {str(e)[:30]}"
            ])
    
    # Display results in a table
    headers = ["Collection", "Exists", "Doc Count", "Health Check", "Status"]
    print(tabulate(results, headers=headers, tablefmt="simple"))
    
    print()
    print("-" * 40)
    
    # Summary
    total_collections = len(results)
    existing = sum(1 for r in results if r[1] == "✓")
    total_docs = sum(r[2] for r in results if isinstance(r[2], int))
    
    print(f"Summary:")
    print(f"  Collections Found: {existing}/{total_collections}")
    print(f"  Total Documents: {total_docs}")
    print(f"  Health Checks: {sum(1 for r in results if r[3] == '✓')}/{total_collections}")
    
    # Check for additional collections from config
    print()
    print("Additional Collections from Config:")
    print("-" * 40)
    
    for collection_name in set(existing_collections) - set(expected_collections):
        if collection_name:  # Skip empty strings
            try:
                collection_ref = db.collection(collection_name)
                docs = collection_ref.limit(10).stream()
                doc_count = sum(1 for _ in docs)
                print(f"  • {collection_name}: {doc_count} documents")
            except Exception as e:
                print(f"  • {collection_name}: Not found")
    
    print()
    print("=" * 60)
    
    # Return success status
    return existing == total_collections


def list_sample_documents():
    """List sample documents from each collection."""
    
    db = firestore.Client(project=settings.gcp_project_id)
    
    print()
    print("Sample Documents Preview")
    print("=" * 60)
    
    collections_to_preview = [
        "upc_mappings",
        "album_metadata",
        "pricing_data",
        "draft_listings"
    ]
    
    for collection_name in collections_to_preview:
        print(f"\n{collection_name}:")
        print("-" * 40)
        
        try:
            collection_ref = db.collection(collection_name)
            # Get first non-health-check document
            docs = collection_ref.where("type", "!=", "health_check").limit(1).stream()
            
            for doc in docs:
                doc_data = doc.to_dict()
                # Show key fields only
                if collection_name == "upc_mappings":
                    print(f"  UPC: {doc_data.get('upc')}")
                    print(f"  MBID: {doc_data.get('mbid')}")
                    print(f"  Source: {doc_data.get('source')}")
                elif collection_name == "album_metadata":
                    print(f"  Artist: {doc_data.get('artist_name')}")
                    print(f"  Title: {doc_data.get('title')}")
                    print(f"  Year: {doc_data.get('year')}")
                    print(f"  Complete: {doc_data.get('is_complete')}")
                elif collection_name == "pricing_data":
                    print(f"  UPC: {doc_data.get('upc')}")
                    print(f"  Condition: {doc_data.get('condition')}")
                    print(f"  Avg Price: ${doc_data.get('average_price', 0):.2f}")
                    print(f"  Confidence: {doc_data.get('confidence')}")
                elif collection_name == "draft_listings":
                    print(f"  SKU: {doc_data.get('sku')}")
                    print(f"  Title: {doc_data.get('title', '')[:50]}...")
                    print(f"  Price: ${doc_data.get('price', 0):.2f}")
                    print(f"  Status: {doc_data.get('status')}")
                
                if not docs:
                    # Try without filter
                    docs = collection_ref.limit(1).stream()
                    for doc in docs:
                        if doc.id != "_health_check":
                            print(f"  Document ID: {doc.id}")
                            print(f"  Fields: {', '.join(list(doc.to_dict().keys())[:5])}...")
                        
        except Exception as e:
            print(f"  Error: {e}")


def main():
    """Main verification function."""
    
    # Verify collections exist
    success = verify_collections()
    
    # Show sample documents
    list_sample_documents()
    
    if success:
        print("\n✅ All collections have been successfully created!")
    else:
        print("\n⚠️ Some collections may be missing. Run initialize_database.py to create them.")
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
