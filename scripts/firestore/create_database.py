#!/usr/bin/env python3
"""
Create and configure Firestore database in Google Cloud.

This script creates the Firestore database with the correct settings
before initializing collections.
"""

import sys
from pathlib import Path
from google.cloud import firestore_admin_v1
from google.api_core import exceptions
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import settings


def create_firestore_database():
    """Create Firestore database in Native mode."""
    
    # Initialize the Firestore Admin client
    client = firestore_admin_v1.FirestoreAdminClient()
    
    # Project and database configuration
    project_id = settings.gcp_project_id
    database_id = "draft-maker-database"  # Your specified database ID
    location_id = "us-west1"  # Your specified region
    
    # Construct the parent path
    parent = f"projects/{project_id}"
    
    # Construct the database name
    database_name = f"{parent}/databases/{database_id}"
    
    print(f"Creating Firestore database...")
    print(f"Project: {project_id}")
    print(f"Database ID: {database_id}")
    print(f"Location: {location_id}")
    print()
    
    try:
        # Check if database already exists
        try:
            existing_db = client.get_database(name=database_name)
            print(f"✓ Database '{database_id}' already exists in {location_id}")
            print(f"  Type: {existing_db.type_.name}")
            print(f"  Concurrency Mode: {existing_db.concurrency_mode.name}")
            return True
        except exceptions.NotFound:
            print(f"Database '{database_id}' not found. Creating...")
        
        # Create the database
        database = firestore_admin_v1.Database(
            name=database_name,
            location_id=location_id,
            type_=firestore_admin_v1.Database.DatabaseType.FIRESTORE_NATIVE,
            concurrency_mode=firestore_admin_v1.Database.ConcurrencyMode.OPTIMISTIC,
        )
        
        # Create the database
        operation = client.create_database(
            parent=parent,
            database=database,
            database_id=database_id
        )
        
        print(f"Creating database... This may take a few minutes...")
        
        # Wait for the operation to complete
        response = operation.result(timeout=300)  # 5 minute timeout
        
        print(f"✓ Successfully created Firestore database '{database_id}'")
        print(f"  Location: {response.location_id}")
        print(f"  Type: {response.type_.name}")
        print(f"  Name: {response.name}")
        
        return True
        
    except exceptions.AlreadyExists:
        print(f"✓ Database '{database_id}' already exists")
        return True
    except Exception as e:
        print(f"✗ Error creating database: {e}")
        return False


def create_default_database_if_needed():
    """Create default database if it doesn't exist (for backwards compatibility)."""
    
    client = firestore_admin_v1.FirestoreAdminClient()
    project_id = settings.gcp_project_id
    parent = f"projects/{project_id}"
    default_db_name = f"{parent}/databases/(default)"
    
    try:
        # Check if default database exists
        try:
            client.get_database(name=default_db_name)
            print(f"✓ Default database already exists")
            return True
        except exceptions.NotFound:
            print(f"Default database not found. Creating...")
        
        # Create default database
        database = firestore_admin_v1.Database(
            name=default_db_name,
            location_id="us-west1",
            type_=firestore_admin_v1.Database.DatabaseType.FIRESTORE_NATIVE,
            concurrency_mode=firestore_admin_v1.Database.ConcurrencyMode.OPTIMISTIC,
        )
        
        operation = client.create_database(
            parent=parent,
            database=database,
            database_id="(default)"
        )
        
        print(f"Creating default database...")
        response = operation.result(timeout=300)
        print(f"✓ Successfully created default Firestore database")
        
        return True
        
    except exceptions.AlreadyExists:
        print(f"✓ Default database already exists")
        return True
    except Exception as e:
        print(f"Note: Could not create default database: {e}")
        return False


def main():
    """Main function to create Firestore database."""
    print("=" * 60)
    print("Firestore Database Creation")
    print("=" * 60)
    print()
    
    # Try to create the named database
    success = create_firestore_database()
    
    if not success:
        print("\nAttempting to create default database as fallback...")
        create_default_database_if_needed()
    
    print()
    print("-" * 60)
    print()
    
    if success:
        print("✅ Database setup complete!")
        print()
        print("Next steps:")
        print("1. Run the initialization script:")
        print("   python scripts/firestore/initialize_database.py")
        print()
        print("2. Deploy security rules:")
        print("   firebase deploy --only firestore:rules")
        print()
        print("3. Deploy indexes:")
        print("   firebase deploy --only firestore:indexes")
    else:
        print("⚠️  Database creation encountered issues.")
        print()
        print("Please check:")
        print("1. You have the necessary permissions in the GCP project")
        print("2. The Firestore API is enabled")
        print("3. Your service account has the 'Cloud Datastore User' role")
        print()
        print("You can also create the database manually at:")
        print(f"https://console.cloud.google.com/firestore/databases?project={settings.gcp_project_id}")


if __name__ == "__main__":
    main()
