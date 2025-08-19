#!/usr/bin/env python3
"""
Migrate OAuth tokens from local storage to Firestore for production deployment.
This script uploads the locally stored tokens to Firestore.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import firestore
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

class TokenMigrator:
    """Migrate tokens from local storage to Firestore."""
    
    def __init__(self):
        """Initialize the migrator."""
        self.local_token_dir = Path.home() / "draftmaker" / ".tokens"
        self.db = firestore.Client(project=settings.gcp_project_id)
        self.collection = settings.firestore_collection_tokens
        
    async def migrate_ebay_token(self):
        """Migrate eBay token to Firestore."""
        ebay_token_file = self.local_token_dir / "ebay_token.json"
        
        if not ebay_token_file.exists():
            logger.warning("No local eBay token file found")
            return False
            
        try:
            # Load local token
            with open(ebay_token_file, 'r') as f:
                token_data = json.load(f)
            
            # Convert datetime strings to datetime objects for Firestore
            if 'expires_at' in token_data and isinstance(token_data['expires_at'], str):
                token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])
            if 'created_at' in token_data and isinstance(token_data['created_at'], str):
                token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
            if 'updated_at' in token_data and isinstance(token_data['updated_at'], str):
                token_data['updated_at'] = datetime.fromisoformat(token_data['updated_at'])
            
            # Upload to Firestore
            doc_ref = self.db.collection(self.collection).document('ebay')
            doc_ref.set(token_data, merge=True)
            
            logger.info("✅ eBay token successfully migrated to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate eBay token: {e}")
            return False
    
    async def migrate_spotify_token(self):
        """Migrate Spotify token to Firestore."""
        spotify_token_file = self.local_token_dir / "spotify_token.json"
        
        if not spotify_token_file.exists():
            logger.warning("No local Spotify token file found")
            return False
            
        try:
            # Load local token
            with open(spotify_token_file, 'r') as f:
                token_data = json.load(f)
            
            # Convert datetime strings to datetime objects for Firestore
            if 'expires_at' in token_data and isinstance(token_data['expires_at'], str):
                token_data['expires_at'] = datetime.fromisoformat(token_data['expires_at'])
            if 'created_at' in token_data and isinstance(token_data['created_at'], str):
                token_data['created_at'] = datetime.fromisoformat(token_data['created_at'])
            if 'updated_at' in token_data and isinstance(token_data['updated_at'], str):
                token_data['updated_at'] = datetime.fromisoformat(token_data['updated_at'])
            
            # Upload to Firestore
            doc_ref = self.db.collection(self.collection).document('spotify')
            doc_ref.set(token_data, merge=True)
            
            logger.info("✅ Spotify token successfully migrated to Firestore")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate Spotify token: {e}")
            return False
    
    async def verify_migration(self):
        """Verify tokens are accessible in Firestore."""
        try:
            # Check eBay token
            ebay_doc = self.db.collection(self.collection).document('ebay').get()
            if ebay_doc.exists:
                ebay_data = ebay_doc.to_dict()
                if 'access_token' in ebay_data and 'refresh_token' in ebay_data:
                    logger.info("✅ eBay token verified in Firestore")
                else:
                    logger.warning("⚠️ eBay token exists but missing required fields")
            else:
                logger.warning("❌ eBay token not found in Firestore")
            
            # Check Spotify token
            spotify_doc = self.db.collection(self.collection).document('spotify').get()
            if spotify_doc.exists:
                spotify_data = spotify_doc.to_dict()
                if 'access_token' in spotify_data:
                    logger.info("✅ Spotify token verified in Firestore")
                else:
                    logger.warning("⚠️ Spotify token exists but missing access_token")
            else:
                logger.warning("❌ Spotify token not found in Firestore")
                
        except Exception as e:
            logger.error(f"Failed to verify migration: {e}")

async def main():
    """Main migration function."""
    print("\n" + "="*60)
    print("🔄 Token Migration to Firestore")
    print("="*60 + "\n")
    
    # Check if running in production environment
    if settings.environment.lower() != 'production':
        print("⚠️  WARNING: Not running in production environment")
        print(f"Current environment: {settings.environment}")
        proceed = input("\nDo you want to continue anyway? (yes/no): ").strip().lower()
        if proceed != 'yes':
            print("Migration cancelled.")
            return
    
    migrator = TokenMigrator()
    
    print("📤 Migrating tokens to Firestore...")
    print("-" * 40)
    
    # Migrate eBay token
    print("Migrating eBay token...")
    ebay_success = await migrator.migrate_ebay_token()
    
    # Migrate Spotify token
    print("Migrating Spotify token...")
    spotify_success = await migrator.migrate_spotify_token()
    
    # Verify migration
    print("\n🔍 Verifying migration...")
    print("-" * 40)
    await migrator.verify_migration()
    
    print("\n" + "="*60)
    if ebay_success and spotify_success:
        print("✅ Migration completed successfully!")
    elif ebay_success or spotify_success:
        print("⚠️ Partial migration completed")
    else:
        print("❌ Migration failed")
    print("="*60 + "\n")

if __name__ == "__main__":
    # Set up Google Cloud credentials if needed
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        print("⚠️ GOOGLE_APPLICATION_CREDENTIALS not set")
        print("Please set it to your service account key file path:")
        print("export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
