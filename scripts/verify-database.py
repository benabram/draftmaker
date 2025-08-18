#!/usr/bin/env python3
"""
Database Verification Script for Draft Maker
This script verifies database connectivity and schema for all environments.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from google.cloud import firestore
from google.api_core import exceptions
import argparse
from dotenv import load_dotenv

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Terminal colors
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'

def print_colored(message: str, color: str = Colors.WHITE):
    """Print colored message to terminal."""
    print(f"{color}{message}{Colors.RESET}")

def print_header(title: str):
    """Print a formatted header."""
    print()
    print_colored("=" * 80, Colors.CYAN)
    print_colored(f"  {title}", Colors.CYAN + Colors.BOLD)
    print_colored("=" * 80, Colors.CYAN)
    print()

def print_section(title: str):
    """Print a section header."""
    print()
    print_colored(f">>> {title}", Colors.YELLOW + Colors.BOLD)
    print_colored("-" * 40, Colors.YELLOW)

def load_environment(env_file: str = ".env") -> Dict[str, str]:
    """Load environment variables from specified file."""
    env_path = Path(__file__).parent.parent / env_file
    if env_path.exists():
        load_dotenv(env_path)
        print_colored(f"✓ Loaded environment from: {env_file}", Colors.GREEN)
        return {
            "ENVIRONMENT": os.getenv("ENVIRONMENT", "unknown"),
            "GCP_PROJECT_ID": os.getenv("GCP_PROJECT_ID", ""),
            "FIRESTORE_DATABASE_ID": os.getenv("FIRESTORE_DATABASE_ID", ""),
            "FIRESTORE_DATABASE_NAME": os.getenv("FIRESTORE_DATABASE_NAME", ""),
            "STORAGE_BUCKET_NAME": os.getenv("STORAGE_BUCKET_NAME", ""),
        }
    else:
        print_colored(f"✗ Environment file not found: {env_file}", Colors.RED)
        return {}

def test_database_connection(project_id: str, database_id: str) -> Tuple[bool, Optional[firestore.Client]]:
    """Test connection to Firestore database."""
    try:
        # Check for service account credentials
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            print_colored(f"  Using service account: {creds_path}", Colors.BLUE)
        else:
            print_colored("  Using default credentials", Colors.BLUE)
        
        # Connect to Firestore
        # Use default database if specified or database_id is "(default)"
        if database_id == "(default)" or not database_id:
            db = firestore.Client(project=project_id)
            database_id = "(default)"
        else:
            db = firestore.Client(project=project_id, database=database_id)
        
        # Test connection by trying to list collections
        collections = list(db.collections())
        print_colored(f"✓ Successfully connected to database: {database_id}", Colors.GREEN)
        print_colored(f"  Project: {project_id}", Colors.BLUE)
        print_colored(f"  Found {len(collections)} collections", Colors.BLUE)
        
        return True, db
    except exceptions.PermissionDenied as e:
        print_colored(f"✗ Permission denied: {str(e)}", Colors.RED)
        return False, None
    except Exception as e:
        print_colored(f"✗ Connection failed: {str(e)}", Colors.RED)
        return False, None

def load_schema_definition() -> Dict:
    """Load the expected schema from firestore-schema.json."""
    schema_path = Path(__file__).parent.parent / "firestore-schema.json"
    if schema_path.exists():
        with open(schema_path, 'r') as f:
            return json.load(f)
    return {}

def verify_collections(db: firestore.Client, expected_schema: Dict) -> Dict[str, Dict]:
    """Verify that expected collections exist and check their structure."""
    results = {}
    expected_collections = expected_schema.get("collections", {})
    
    # Get actual collections
    actual_collections = {col.id for col in db.collections()}
    
    print_colored(f"\nExpected collections: {len(expected_collections)}", Colors.CYAN)
    print_colored(f"Actual collections: {len(actual_collections)}", Colors.CYAN)
    
    for collection_name, collection_schema in expected_collections.items():
        print(f"\n  Checking collection: {collection_name}")
        
        if collection_name in actual_collections:
            # Collection exists
            print_colored(f"    ✓ Collection exists", Colors.GREEN)
            
            # Get sample document to check structure
            col_ref = db.collection(collection_name)
            docs = col_ref.limit(1).get()
            
            if docs:
                sample_doc = docs[0].to_dict()
                expected_fields = collection_schema.get("fields", {})
                
                # Check required fields
                missing_fields = []
                for field_name, field_config in expected_fields.items():
                    if field_config.get("required", False) and field_name not in sample_doc:
                        missing_fields.append(field_name)
                
                doc_count = len(list(col_ref.limit(1000).stream()))
                
                results[collection_name] = {
                    "exists": True,
                    "document_count": doc_count,
                    "has_documents": True,
                    "missing_required_fields": missing_fields,
                    "sample_fields": list(sample_doc.keys())[:10]  # First 10 fields
                }
                
                print_colored(f"    ✓ Documents found: {doc_count}", Colors.GREEN)
                if missing_fields:
                    print_colored(f"    ⚠ Missing required fields: {missing_fields}", Colors.YELLOW)
            else:
                results[collection_name] = {
                    "exists": True,
                    "document_count": 0,
                    "has_documents": False
                }
                print_colored(f"    ⚠ Collection is empty", Colors.YELLOW)
        else:
            # Collection doesn't exist
            results[collection_name] = {
                "exists": False,
                "document_count": 0,
                "has_documents": False
            }
            print_colored(f"    ✗ Collection does not exist", Colors.RED)
    
    # Check for unexpected collections
    unexpected = actual_collections - set(expected_collections.keys())
    if unexpected:
        print_colored(f"\n⚠ Unexpected collections found: {unexpected}", Colors.YELLOW)
        for col_name in unexpected:
            col_ref = db.collection(col_name)
            doc_count = len(list(col_ref.limit(1000).stream()))
            results[col_name] = {
                "exists": True,
                "document_count": doc_count,
                "unexpected": True
            }
    
    return results

def test_write_permissions(db: firestore.Client) -> bool:
    """Test write permissions by creating and deleting a test document."""
    try:
        test_collection = "test_write_permissions"
        test_doc_id = f"test_{datetime.now().isoformat()}"
        
        # Try to write a document
        doc_ref = db.collection(test_collection).document(test_doc_id)
        doc_ref.set({
            "test": True,
            "timestamp": datetime.now(),
            "message": "Testing write permissions"
        })
        
        # Try to read it back
        doc = doc_ref.get()
        if doc.exists:
            print_colored("    ✓ Write test: Successfully created document", Colors.GREEN)
            
            # Clean up - delete the test document
            doc_ref.delete()
            print_colored("    ✓ Delete test: Successfully deleted document", Colors.GREEN)
            return True
        else:
            print_colored("    ✗ Write test: Document not found after creation", Colors.RED)
            return False
            
    except exceptions.PermissionDenied:
        print_colored("    ✗ Write test: Permission denied", Colors.RED)
        return False
    except Exception as e:
        print_colored(f"    ✗ Write test failed: {str(e)}", Colors.RED)
        return False

def verify_environment(env_name: str, env_file: str):
    """Verify database connectivity and schema for a specific environment."""
    print_header(f"Verifying {env_name} Environment")
    
    # Load environment variables
    env_vars = load_environment(env_file)
    if not env_vars:
        return
    
    # Display configuration
    print_section("Configuration")
    for key, value in env_vars.items():
        if value:
            display_value = value if "SECRET" not in key else "***"
            print(f"  {key}: {display_value}")
        else:
            print_colored(f"  {key}: NOT SET", Colors.RED)
    
    # Check required variables
    project_id = env_vars.get("GCP_PROJECT_ID")
    database_id = env_vars.get("FIRESTORE_DATABASE_ID") or env_vars.get("FIRESTORE_DATABASE_NAME")
    
    if not project_id or not database_id:
        print_colored("\n✗ Missing required configuration", Colors.RED)
        return
    
    # Test database connection
    print_section("Database Connection")
    connected, db = test_database_connection(project_id, database_id)
    
    if not connected:
        return
    
    # Load and verify schema
    print_section("Schema Verification")
    schema = load_schema_definition()
    if schema:
        collection_results = verify_collections(db, schema)
        
        # Summary
        print_section("Summary")
        total_collections = len(collection_results)
        existing_collections = sum(1 for r in collection_results.values() if r.get("exists"))
        collections_with_data = sum(1 for r in collection_results.values() if r.get("has_documents"))
        
        print(f"  Total expected collections: {len(schema.get('collections', {}))}")
        print(f"  Collections found: {existing_collections}")
        print(f"  Collections with data: {collections_with_data}")
        
        # Test write permissions
        print_section("Permission Tests")
        write_success = test_write_permissions(db)
        
        if write_success:
            print_colored("\n✓ All permission tests passed", Colors.GREEN)
        else:
            print_colored("\n⚠ Some permission tests failed", Colors.YELLOW)
    else:
        print_colored("✗ Schema definition not found", Colors.RED)

def main():
    """Main function to verify database connectivity and schema."""
    parser = argparse.ArgumentParser(description="Verify Draft Maker database connectivity and schema")
    parser.add_argument(
        "--env",
        choices=["all", "local", "staging", "production"],
        default="all",
        help="Which environment to verify"
    )
    parser.add_argument(
        "--service-account",
        help="Path to service account key file"
    )
    
    args = parser.parse_args()
    
    # Set service account if provided
    if args.service_account:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = args.service_account
        print_colored(f"Using service account: {args.service_account}", Colors.BLUE)
    
    print_colored("\n" + "=" * 80, Colors.MAGENTA)
    print_colored("  DRAFT MAKER DATABASE VERIFICATION", Colors.MAGENTA + Colors.BOLD)
    print_colored("=" * 80, Colors.MAGENTA)
    
    environments = []
    if args.env == "all":
        environments = [
            ("Local Development", ".env"),
            ("Staging", ".env.staging"),
            ("Production", ".env.production")
        ]
    elif args.env == "local":
        environments = [("Local Development", ".env")]
    elif args.env == "staging":
        environments = [("Staging", ".env.staging")]
    elif args.env == "production":
        environments = [("Production", ".env.production")]
    
    for env_name, env_file in environments:
        verify_environment(env_name, env_file)
    
    print_colored("\n" + "=" * 80, Colors.MAGENTA)
    print_colored("  VERIFICATION COMPLETE", Colors.MAGENTA + Colors.BOLD)
    print_colored("=" * 80, Colors.MAGENTA)
    print()

if __name__ == "__main__":
    main()
